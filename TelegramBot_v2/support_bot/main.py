"""
Точка входа бота поддержки TZshnik.

Этот модуль инициализирует и запускает бота поддержки:
- Настраивает логирование
- Инициализирует бота и диспетчер aiogram
- Регистрирует middleware
- Регистрирует обработчики
- Запускает polling

Бот поддержки использует ту же базу данных, что и основной бот.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from support_bot.config import support_settings
from database import init_db


def setup_logging() -> None:
    """
    Настройка structlog для логирования.

    В режиме debug использует ConsoleRenderer (цветной вывод),
    в production - JSONRenderer (структурированный JSON).
    """
    # Настройка стандартного логгера
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if support_settings.debug else logging.INFO,
    )

    # Выбор рендерера в зависимости от режима
    if support_settings.debug:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    # Конфигурация structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Получаем логгер после настройки
logger = structlog.get_logger()


async def on_startup(bot: Bot) -> None:
    """
    Callback при старте бота поддержки.

    Выполняется один раз при запуске:
    - Регистрирует команды бота
    - Логирует информацию о боте

    Args:
        bot: Экземпляр бота
    """
    from aiogram.types import BotCommand, BotCommandScopeDefault

    # Регистрация команд для всех пользователей
    user_commands = [
        BotCommand(command="start", description="🚀 Создать обращение"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="my_tickets", description="📋 Мои обращения"),
    ]

    try:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        logger.info("support_bot_commands_registered")
    except Exception as e:
        logger.warning("failed_to_register_support_commands", error=str(e))

    bot_info = await bot.get_me()

    logger.info(
        "support_bot_started",
        bot_username=bot_info.username,
        bot_id=bot_info.id,
    )


async def on_shutdown(bot: Bot) -> None:
    """
    Callback при остановке бота поддержки.

    Выполняется при graceful shutdown:
    - Логирует остановку
    - Закрывает сессию бота

    НЕ закрывает БД — это делает основной бот,
    т.к. оба бота используют один engine.

    Args:
        bot: Экземпляр бота
    """
    logger.info("support_bot_stopping")

    await bot.session.close()
    logger.info("support_bot_stopped")


async def main() -> None:
    """
    Главная функция запуска бота поддержки.

    Последовательность запуска:
    1. Настройка логирования
    2. Инициализация бота
    3. Регистрация handlers
    4. Запуск polling
    """
    # 1. Настройка логирования
    setup_logging()

    logger.info(
        "starting_support_bot",
        debug=support_settings.debug,
    )

    # 2. Инициализация бота с настройками по умолчанию
    bot = Bot(
        token=support_settings.support_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )

    # 3. Инициализация диспетчера
    dp = Dispatcher()

    # Регистрация lifecycle callbacks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Инициализация БД
    await init_db()
    logger.info("support_bot_database_ready")

    # Регистрация middleware (упрощённая версия без throttling и album)
    from bot.middleware import DatabaseMiddleware, UserMiddleware, LoggingMiddleware

    # Логирование
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    # База данных
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Пользователь
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    logger.info("support_bot_middleware_registered")

    # Регистрация глобального обработчика ошибок
    from bot.handlers.error_handler import router as error_router
    dp.include_router(error_router)

    # Регистрация роутеров бота поддержки
    from support_bot.handlers import get_support_router

    support_router = get_support_router()
    dp.include_router(support_router)

    logger.info("support_bot_routers_registered")

    # 4. Запуск polling
    try:
        # Удаляем webhook на случай если был установлен ранее
        await bot.delete_webhook(drop_pending_updates=True)

        logger.info("support_bot_polling_started")

        # Запуск long polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except Exception as e:
        logger.error("support_bot_error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот поддержки остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
