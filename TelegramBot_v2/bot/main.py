"""
Точка входа Telegram-бота "ТЗшник v2.0".

Этот модуль инициализирует и запускает бота:
- Настраивает расширенное логирование
- Создаёт необходимые директории
- Инициализирует бота и диспетчер aiogram
- Регистрирует middleware (включая throttling)
- Запускает мониторинг и backup scheduler
- Запускает polling
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

from bot.config import settings
from database import close_db, init_db


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
        level=logging.DEBUG if settings.debug else logging.INFO,
    )
    
    # Выбор рендерера в зависимости от режима
    if settings.debug:
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


def create_directories() -> None:
    """
    Создание необходимых директорий для работы бота.
    
    Создаёт папки:
    - data/ - для SQLite базы данных
    - exports/ - для PDF файлов
    """
    settings.data_dir.mkdir(exist_ok=True)
    settings.exports_dir.mkdir(exist_ok=True)
    
    logger.debug(
        "directories_created",
        data_dir=str(settings.data_dir),
        exports_dir=str(settings.exports_dir),
    )


async def on_startup(bot: Bot) -> None:
    """
    Callback при старте бота.
    
    Выполняется один раз при запуске:
    - Создаёт индексы БД
    - Запускает backup scheduler
    - Логирует информацию о боте
    - Уведомляет админа о запуске
    
    Args:
        bot: Экземпляр бота
    """
    # Создание индексов БД
    try:
        from database.indexes import ensure_indexes
        await ensure_indexes()
    except Exception as e:
        logger.warning("failed_to_create_indexes", error=str(e))
    
    # Запуск планировщика бэкапов (только в production)
    if not settings.debug:
        try:
            from utils.backup import backup_scheduler
            await backup_scheduler.start()
        except Exception as e:
            logger.warning("failed_to_start_backup_scheduler", error=str(e))
    
    bot_info = await bot.get_me()
    
    logger.info(
        "bot_started",
        bot_username=bot_info.username,
        bot_id=bot_info.id,
        debug_mode=settings.debug,
    )
    
    # Уведомление админа о запуске
    if settings.admin_user_id:
        try:
            mode = "🔧 DEBUG" if settings.debug else "🚀 PRODUCTION"
            await bot.send_message(
                chat_id=settings.admin_user_id,
                text=f"🤖 Бот запущен\n\nРежим: {mode}\nВерсия: 2.0",
            )
        except Exception as e:
            logger.warning("failed_to_notify_admin", error=str(e))


async def on_shutdown(bot: Bot) -> None:
    """
    Callback при остановке бота.
    
    Выполняется при graceful shutdown:
    - Останавливает backup scheduler
    - Логирует остановку
    - Закрывает сессии
    
    Args:
        bot: Экземпляр бота
    """
    logger.info("bot_stopping")
    
    # Остановка планировщика бэкапов
    try:
        from utils.backup import backup_scheduler
        await backup_scheduler.stop()
    except Exception as e:
        logger.warning("failed_to_stop_backup_scheduler", error=str(e))
    
    # Закрытие соединения с БД
    await close_db()
    
    await bot.session.close()
    logger.info("bot_stopped")


async def main() -> None:
    """
    Главная функция запуска бота.
    
    Последовательность запуска:
    1. Настройка логирования
    2. Создание директорий
    3. Инициализация бота
    4. Регистрация handlers
    5. Запуск polling
    """
    # 1. Настройка логирования
    setup_logging()
    
    logger.info(
        "starting_bot",
        debug=settings.debug,
        admin_id=settings.admin_user_id,
    )
    
    # 2. Создание директорий
    create_directories()
    
    # 3. Инициализация бота с настройками по умолчанию
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    
    # 4. Инициализация диспетчера
    dp = Dispatcher()
    
    # Регистрация lifecycle callbacks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Инициализация БД
    await init_db()
    logger.info("database_ready")
    
    # Регистрация middleware (порядок важен!)
    from bot.middleware import DatabaseMiddleware, UserMiddleware, LoggingMiddleware
    from bot.middlewares.throttling import ThrottlingMiddleware
    
    # Throttling - первый для защиты от спама
    throttling_middleware = ThrottlingMiddleware()
    dp.message.middleware(throttling_middleware)
    dp.callback_query.middleware(throttling_middleware)
    
    # Логирование
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    # База данных
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # Пользователь
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    
    logger.info("middleware_registered")
    
    # Регистрация глобального обработчика ошибок
    from bot.handlers.error_handler import router as error_router
    dp.include_router(error_router)
    
    # Регистрация роутеров
    from bot.handlers import get_main_router
    
    main_router = get_main_router()
    dp.include_router(main_router)
    
    logger.info("routers_registered")
    
    # 5. Запуск polling
    try:
        # Удаляем webhook на случай если был установлен ранее
        await bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("polling_started")
        
        # Запуск long polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
        
    except Exception as e:
        logger.error("bot_error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
