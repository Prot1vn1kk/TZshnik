"""
Глобальная обработка ошибок бота.

Модуль обеспечивает:
- Централизованную обработку исключений
- Уведомление пользователей о проблемах
- Логирование ошибок для мониторинга
- Уведомление администраторов о критических ошибках
"""

from typing import Any, Callable, Awaitable

from aiogram import Bot, Router
from aiogram.types import Update, ErrorEvent, Message, CallbackQuery
import structlog

from bot.config import settings
from core.exceptions import (
    TZGeneratorError,
    AIProviderError,
    VisionAnalysisError,
    TextGenerationError,
    GenerationError,
    ValidationError,
    InsufficientBalanceError,
)


logger = structlog.get_logger()
router = Router(name="errors")


# ============================================================
# СООБЩЕНИЯ ОБ ОШИБКАХ
# ============================================================

ERROR_MESSAGES = {
    "generic": (
        "😔 <b>Произошла ошибка</b>\n\n"
        "Попробуйте ещё раз или обратитесь в поддержку."
    ),
    "ai_provider": (
        "🤖 <b>Ошибка AI сервиса</b>\n\n"
        "AI провайдер временно недоступен.\n"
        "Попробуйте через несколько минут."
    ),
    "vision": (
        "📷 <b>Ошибка анализа фото</b>\n\n"
        "Не удалось проанализировать изображение.\n"
        "Попробуйте загрузить другое фото."
    ),
    "generation": (
        "📝 <b>Ошибка генерации</b>\n\n"
        "Не удалось создать ТЗ.\n"
        "Попробуйте ещё раз или измените фото."
    ),
    "validation": (
        "⚠️ <b>Ошибка валидации</b>\n\n"
        "Данные не прошли проверку.\n"
        "Проверьте введённую информацию."
    ),
    "balance": (
        "💰 <b>Недостаточно кредитов</b>\n\n"
        "Пополните баланс для продолжения работы."
    ),
    "rate_limit": (
        "⏳ <b>Слишком много запросов</b>\n\n"
        "Подождите немного перед следующим запросом."
    ),
    "timeout": (
        "⏱ <b>Превышено время ожидания</b>\n\n"
        "Сервер слишком долго отвечает.\n"
        "Попробуйте позже."
    ),
}


# ============================================================
# УТИЛИТЫ
# ============================================================

async def notify_admins_about_error(
    bot: Bot,
    error: Exception,
    update: Update | None = None,
) -> None:
    """
    Уведомить администраторов о критической ошибке.
    
    Args:
        bot: Экземпляр бота
        error: Исключение
        update: Обновление (если есть)
    """
    if not settings.admin_ids:
        return
    
    # Формируем текст уведомления
    error_type = type(error).__name__
    error_msg = str(error)[:500]  # Ограничиваем длину
    
    user_info = "N/A"
    if update:
        if update.message and update.message.from_user:
            user = update.message.from_user
            user_info = f"ID: {user.id}, @{user.username or 'N/A'}"
        elif update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
            user_info = f"ID: {user.id}, @{user.username or 'N/A'}"
    
    text = (
        f"🚨 <b>Критическая ошибка</b>\n\n"
        f"<b>Тип:</b> {error_type}\n"
        f"<b>Пользователь:</b> {user_info}\n"
        f"<b>Ошибка:</b>\n<code>{error_msg}</code>"
    )
    
    # Отправляем первому доступному админу
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
            )
            break  # Отправили одному - достаточно
        except Exception as e:
            logger.warning(
                "Failed to notify admin",
                admin_id=admin_id,
                error=str(e),
            )


async def send_error_to_user(
    event: Message | CallbackQuery,
    error_key: str,
) -> None:
    """
    Отправить сообщение об ошибке пользователю.
    
    Args:
        event: Событие (Message или CallbackQuery)
        error_key: Ключ сообщения из ERROR_MESSAGES
    """
    text = ERROR_MESSAGES.get(error_key, ERROR_MESSAGES["generic"])
    
    try:
        if isinstance(event, CallbackQuery):
            await event.answer(
                "Произошла ошибка. Попробуйте ещё раз.",
                show_alert=True,
            )
            if event.message:
                await event.message.answer(text, parse_mode="HTML")
        elif isinstance(event, Message):
            await event.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.warning("Failed to send error to user", error=str(e))


# ============================================================
# ОБРАБОТЧИКИ ОШИБОК
# ============================================================

@router.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    """
    Глобальный обработчик всех ошибок бота.
    
    Классифицирует ошибки и отправляет соответствующие сообщения.
    
    Args:
        event: Событие ошибки
        
    Returns:
        True если ошибка обработана
    """
    exception = event.exception
    update = event.update
    
    # Получаем событие для ответа пользователю
    user_event = None
    if update:
        user_event = update.message or update.callback_query
    
    # Логируем ошибку
    log_data: dict = {
        "error_type": type(exception).__name__,
        "error_message": str(exception),
    }
    
    if update:
        if update.message and update.message.from_user:
            log_data["user_id"] = update.message.from_user.id
        elif update.callback_query and update.callback_query.from_user:
            log_data["user_id"] = update.callback_query.from_user.id
    
    # Классифицируем ошибку и определяем ключ сообщения
    error_key = "generic"
    should_notify_admin = False
    
    if isinstance(exception, InsufficientBalanceError):
        error_key = "balance"
        logger.info("insufficient_balance_error", **log_data)
        
    elif isinstance(exception, VisionAnalysisError):
        error_key = "vision"
        logger.warning("vision_analysis_error", **log_data)
        
    elif isinstance(exception, TextGenerationError):
        error_key = "generation"
        logger.warning("text_generation_error", **log_data)
        
    elif isinstance(exception, AIProviderError):
        error_key = "ai_provider"
        logger.error("ai_provider_error", **log_data, exc_info=True)
        should_notify_admin = True
        
    elif isinstance(exception, ValidationError):
        error_key = "validation"
        logger.warning("validation_error", **log_data)
        
    elif isinstance(exception, GenerationError):
        error_key = "generation"
        logger.warning("generation_error", **log_data)
        
    elif isinstance(exception, TZGeneratorError):
        error_key = "generic"
        logger.error("tz_generator_error", **log_data, exc_info=True)
        should_notify_admin = True
        
    elif isinstance(exception, TimeoutError):
        error_key = "timeout"
        logger.warning("timeout_error", **log_data)
        
    else:
        # Неизвестная ошибка - критическая
        logger.error("unhandled_error", **log_data, exc_info=True)
        should_notify_admin = True
    
    # Уведомляем пользователя
    if user_event:
        await send_error_to_user(user_event, error_key)
    
    # Уведомляем админов о критических ошибках
    if should_notify_admin and settings.debug is False:
        # Получаем bot из события
        bot = getattr(event, 'bot', None)
        if bot:
            await notify_admins_about_error(bot, exception, update)
    
    return True  # Ошибка обработана


# ============================================================
# ДЕКОРАТОР ДЛЯ ОБРАБОТКИ ОШИБОК В ХЕНДЛЕРАХ
# ============================================================

def handle_errors(error_message: str = "generic"):
    """
    Декоратор для обработки ошибок в хендлерах.
    
    Использование:
        @handle_errors(error_message="generation")
        async def my_handler(message: Message):
            ...
    
    Args:
        error_message: Ключ сообщения об ошибке
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Находим event для ответа
                event = None
                for arg in args:
                    if isinstance(arg, (Message, CallbackQuery)):
                        event = arg
                        break
                
                if event:
                    await send_error_to_user(event, error_message)
                
                logger.error(
                    f"handler_error_in_{func.__name__}",
                    error=str(e),
                    exc_info=True,
                )
                
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
