"""
Утилита для работы с ботом поддержки.

Предоставляет общий Bot instance для cross-bot коммуникации,
избегая создания новых экземпляров при каждом уведомлении.
"""

import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


logger = structlog.get_logger()

# Глобальный экземпляр бота поддержки (lazy initialization)
_support_bot_instance: Bot | None = None


def get_support_bot() -> Bot | None:
    """
    Получить или создать общий экземпляр бота поддержки.

    Использует singleton pattern для переиспользования одного Bot instance
    вместо создания нового при каждом уведомлении.

    Returns:
        Bot instance или None, если токен не настроен
    """
    global _support_bot_instance

    # Если бот уже создан, возвращаем его
    if _support_bot_instance is not None:
        return _support_bot_instance

    # Импортируем настройки (lazy import)
    try:
        from support_bot.config import support_settings

        if not support_settings.support_bot_token:
            logger.warning("support_bot_token_not_configured")
            return None

        # Создаём экземпляр бота
        _support_bot_instance = Bot(
            token=support_settings.support_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        logger.info("support_bot_instance_created")
        return _support_bot_instance

    except Exception as e:
        logger.error("failed_to_create_support_bot_instance", error=str(e))
        return None


async def close_support_bot() -> None:
    """
    Закрыть сессию бота поддержки.

    Должен вызываться при graceful shutdown основного бота.
    """
    global _support_bot_instance

    if _support_bot_instance is not None:
        try:
            await _support_bot_instance.session.close()
            _support_bot_instance = None
            logger.info("support_bot_instance_closed")
        except Exception as e:
            logger.error("failed_to_close_support_bot_session", error=str(e))


async def notify_user_via_support_bot(
    telegram_id: int,
    text: str,
) -> bool:
    """
    Отправить уведомление пользователю через бота поддержки.

    Args:
        telegram_id: Telegram ID пользователя
        text: Текст сообщения

    Returns:
        True если сообщение отправлено успешно, False иначе
    """
    bot = get_support_bot()

    if bot is None:
        return False

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="HTML",
        )
        return True
    except Exception as e:
        logger.warning(
            "failed_to_send_notification_via_support_bot",
            telegram_id=telegram_id,
            error=str(e),
        )
        return False
