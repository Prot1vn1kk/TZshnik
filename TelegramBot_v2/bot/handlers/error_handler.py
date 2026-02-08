"""
Глобальная обработка ошибок бота.

Модуль обеспечивает:
- Централизованную обработку исключений
- Генерацию уникальных ID ошибок для отслеживания
- Уведомление пользователей с кнопкой "Сообщить администратору"
- Расширенные уведомления администраторов с полным traceback
- Логирование на уровнях INFO, DEBUG, ERROR, CRITICAL
"""

import traceback
import uuid
from datetime import datetime
from typing import Any, Callable, Awaitable, Dict, Optional
import html

from aiogram import Bot, Router
from aiogram.types import Update, ErrorEvent, Message, CallbackQuery
import structlog

from bot.config import settings
from bot.keyboards import (
    get_error_report_keyboard,
    get_admin_error_keyboard,
    get_main_menu_keyboard,
)
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


# ============================================================
# СОЗДАНИЕ РОУТЕРА (для поддержки нескольких ботов)
# ============================================================

def get_error_router() -> Router:
    """
    Создаёт новый экземпляр роутера обработки ошибок.

    Нужен для поддержки нескольких ботов (основной + поддержки),
    так как роутер может быть прикреплён только к одному диспетчеру.
    """
    return Router(name="errors")


# Глобальный роутер для основного бота (для обратной совместимости)
router = get_error_router()


# ============================================================
# ХРАНИЛИЩЕ ОШИБОК (для отложенной обработки)
# ============================================================

# Хранилище последних ошибок (error_id -> error_details)
# В продакшене использовать Redis/DB
_error_storage: Dict[str, dict] = {}


def store_error(error_id: str, details: dict) -> None:
    """Сохранить детали ошибки для последующего доступа."""
    _error_storage[error_id] = details
    # Очищаем старые записи (храним максимум 100)
    if len(_error_storage) > 100:
        oldest_keys = list(_error_storage.keys())[:-100]
        for key in oldest_keys:
            _error_storage.pop(key, None)


def get_error(error_id: str) -> Optional[dict]:
    """Получить детали ошибки по ID."""
    return _error_storage.get(error_id)


# ============================================================
# СООБЩЕНИЯ ОБ ОШИБКАХ
# ============================================================

ERROR_MESSAGES = {
    "generic": (
        "😔 <b>Упс! Что-то пошло не так</b>\n\n"
        "Мы уже знаем о проблеме и работаем над её решением.\n\n"
        "Попробуйте ещё раз через несколько минут."
    ),
    "ai_provider": (
        "🤖 <b>AI сервис временно недоступен</b>\n\n"
        "Наш AI-помощник сейчас перегружен.\n"
        "Попробуйте через 1-2 минуты."
    ),
    "vision": (
        "📷 <b>Не удалось проанализировать фото</b>\n\n"
        "Попробуйте загрузить другое фото с лучшим качеством.\n"
        "Убедитесь, что товар хорошо виден."
    ),
    "generation": (
        "📝 <b>Ошибка при создании ТЗ</b>\n\n"
        "Не удалось сгенерировать техническое задание.\n"
        "Попробуйте ещё раз или измените фото."
    ),
    "validation": (
        "⚠️ <b>Некорректные данные</b>\n\n"
        "Проверьте введённую информацию и попробуйте снова."
    ),
    "balance": (
        "💰 <b>Недостаточно кредитов</b>\n\n"
        "Пополните баланс для продолжения работы."
    ),
    "rate_limit": (
        "⏳ <b>Слишком много запросов</b>\n\n"
        "Вы слишком часто отправляете запросы.\n"
        "Подождите немного и попробуйте снова."
    ),
    "timeout": (
        "⏱ <b>Превышено время ожидания</b>\n\n"
        "Сервер слишком долго отвечает.\n"
        "Попробуйте позже."
    ),
    "network": (
        "🌐 <b>Проблемы с сетью</b>\n\n"
        "Не удалось связаться с сервером.\n"
        "Проверьте подключение и попробуйте снова."
    ),
}


# ============================================================
# ГЕНЕРАЦИЯ ID ОШИБКИ
# ============================================================

def generate_error_id() -> str:
    """
    Генерация уникального ID ошибки.
    
    Формат: ERR-YYYYMMDD-XXXX (например ERR-20260204-a1b2)
    """
    date_part = datetime.now().strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:4].upper()
    return f"ERR-{date_part}-{unique_part}"


# ============================================================
# ФОРМАТИРОВАНИЕ ОШИБКИ ДЛЯ АДМИНА
# ============================================================

def format_admin_error_message(
    error_id: str,
    exception: Exception,
    user_info: str,
    context: str = "",
) -> str:
    """
    Форматирует подробное сообщение об ошибке для администратора.
    
    Включает:
    - ID ошибки для отслеживания
    - Информацию о пользователе
    - Тип и текст ошибки
    - Краткий traceback (последние строки)
    - Путь и строку, где произошла ошибка
    """
    # Получаем полный traceback
    tb_str = traceback.format_exception(type(exception), exception, exception.__traceback__)
    full_traceback = "".join(tb_str)
    
    # Извлекаем последние строки traceback (самые важные)
    tb_lines = full_traceback.strip().split("\n")
    
    # Показываем последние 15 строк (где реально произошла ошибка)
    # Вместо первых 3500 символов, которые обычно не важны
    if len(tb_lines) > 15:
        # Берём последние 15 строк
        short_traceback = "\n".join(tb_lines[-15:])
        traceback_preview = f"... (показаны последние 15 строк)\n\n{short_traceback}"
    else:
        traceback_preview = full_traceback
    
    # Проверяем, не слишком ли длинный результат
    if len(traceback_preview) > 2500:
        traceback_preview = traceback_preview[-2500:] + "\n... (обрезано)"
    
    # Экранируем HTML-символы для безопасного отображения в Telegram
    traceback_preview = html.escape(traceback_preview)
    exception_message = html.escape(str(exception)[:500])
    
    message = (
        f"🚨 <b>ОШИБКА [{error_id}]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Пользователь:</b> {user_info}\n"
        f"🕐 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📍 <b>Контекст:</b> {context or 'N/A'}\n\n"
        f"❌ <b>Тип:</b> <code>{type(exception).__name__}</code>\n"
        f"💬 <b>Сообщение:</b> {exception_message}\n\n"
        f"📋 <b>Traceback (последние строки):</b>\n"
        f"<pre>{traceback_preview}</pre>"
    )
    
    return message


def format_user_error_message(error_key: str, error_id: str) -> str:
    """
    Форматирует сообщение об ошибке для пользователя.
    
    Добавляет ID ошибки для обращения в поддержку.
    """
    base_message = ERROR_MESSAGES.get(error_key, ERROR_MESSAGES["generic"])
    
    return (
        f"{base_message}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔖 Код ошибки: <code>{error_id}</code>\n\n"
        f"Если проблема повторяется — нажмите кнопку ниже."
    )


# ============================================================
# УВЕДОМЛЕНИЕ АДМИНИСТРАТОРОВ
# ============================================================

async def notify_admins_about_error(
    bot: Bot,
    error_id: str,
    exception: Exception,
    user_info: str,
    context: str = "",
) -> None:
    """
    Отправить уведомление всем администраторам о критической ошибке.
    
    Args:
        bot: Экземпляр бота
        error_id: Уникальный ID ошибки
        exception: Исключение
        user_info: Информация о пользователе
        context: Контекст, где произошла ошибка
    """
    if not settings.admin_ids:
        logger.warning("no_admin_ids_configured")
        return
    
    message = format_admin_error_message(error_id, exception, user_info, context)
    keyboard = get_admin_error_keyboard(error_id)
    
    # Сохраняем детали ошибки
    store_error(error_id, {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "traceback": traceback.format_exception(type(exception), exception, exception.__traceback__),
        "user_info": user_info,
        "context": context,
        "timestamp": datetime.now().isoformat(),
    })
    
    # Отправляем всем админам
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            logger.info(
                "admin_error_notification_sent",
                admin_id=admin_id,
                error_id=error_id,
            )
        except Exception as e:
            logger.error(
                "admin_notification_failed",
                admin_id=admin_id,
                error=str(e),
            )


# ============================================================
# ОТПРАВКА ОШИБКИ ПОЛЬЗОВАТЕЛЮ
# ============================================================

async def send_error_to_user(
    event: Message | CallbackQuery,
    error_key: str,
    error_id: str,
) -> None:
    """
    Отправить сообщение об ошибке пользователю с кнопкой сообщения админу.
    
    Args:
        event: Событие (Message или CallbackQuery)
        error_key: Ключ сообщения из ERROR_MESSAGES
        error_id: Уникальный ID ошибки
    """
    text = format_user_error_message(error_key, error_id)
    keyboard = get_error_report_keyboard(error_id)
    
    try:
        if isinstance(event, CallbackQuery):
            await event.answer(
                "⚠️ Произошла ошибка",
                show_alert=True,
            )
            if event.message:
                await event.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        elif isinstance(event, Message):
            await event.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        logger.warning("failed_to_send_error_to_user", error=str(e))


# ============================================================
# ОБРАБОТЧИКИ CALLBACK'ОВ ОШИБОК
# ============================================================

@router.callback_query(lambda c: c.data and c.data.startswith("report_error:"))
async def callback_report_error(
    callback: CallbackQuery,
    bot: Bot,
) -> None:
    """
    Пользователь нажал "Сообщить администратору".
    """
    error_id = callback.data.split(":")[1]
    user = callback.from_user
    
    user_info = f"ID: {user.id}, @{user.username or 'N/A'}"
    
    # Получаем сохранённые детали ошибки
    error_details = get_error(error_id)
    
    if error_details:
        # Отправляем админу подробности
        message = (
            f"📩 <b>Пользователь сообщил об ошибке</b>\n\n"
            f"🔖 <b>ID:</b> <code>{error_id}</code>\n"
            f"👤 <b>От:</b> {user_info}\n"
            f"📅 <b>Время ошибки:</b> {error_details.get('timestamp', 'N/A')}\n\n"
            f"❌ <b>Тип:</b> <code>{error_details.get('exception_type', 'N/A')}</code>\n"
            f"💬 <b>Сообщение:</b> {error_details.get('exception_message', 'N/A')[:500]}"
        )
        
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=get_admin_error_keyboard(error_id),
                )
            except Exception:
                pass
    
    await callback.answer("✅ Администратор уведомлён. Спасибо!", show_alert=True)
    
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "✅ <b>Ваше сообщение отправлено</b>\n\n"
            "Мы изучим проблему и постараемся исправить её как можно скорее.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
    
    logger.info(
        "user_reported_error",
        user_id=user.id,
        error_id=error_id,
    )


@router.callback_query(lambda c: c.data and c.data.startswith("retry_action"))
async def callback_retry_action(callback: CallbackQuery) -> None:
    """Пользователь нажал "Попробовать снова"."""
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )


@router.callback_query(lambda c: c.data and c.data.startswith("error_details:"))
async def callback_error_details(callback: CallbackQuery, bot: Bot) -> None:
    """Показать полные детали ошибки администратору."""
    if not callback.data:
        return
        
    error_id = callback.data.split(":")[1]
    error_details = get_error(error_id)
    
    if not error_details:
        await callback.answer("❌ Детали ошибки не найдены", show_alert=True)
        return
    
    await callback.answer()
    
    traceback_lines = error_details.get("traceback", [])
    traceback_str = "".join(traceback_lines) if traceback_lines else "N/A"
    
    # Экранируем HTML-символы для безопасного отображения в Telegram
    traceback_str = html.escape(traceback_str)
    
    # Разбиваем длинный traceback на несколько сообщений
    max_length = 3800  # Оставляем запас для заголовков
    
    if len(traceback_str) <= max_length:
        # Помещается в одно сообщение
        await bot.send_message(
            chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
            text=f"📋 <b>Полный traceback [{error_id}]:</b>\n\n"
                 f"<pre>{traceback_str}</pre>",
            parse_mode="HTML",
        )
    else:
        # Разбиваем на части
        parts = []
        while traceback_str:
            if len(traceback_str) <= max_length:
                parts.append(traceback_str)
                break
            # Находим границу строки
            split_pos = traceback_str.rfind("\n", 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            parts.append(traceback_str[:split_pos])
            traceback_str = traceback_str[split_pos:].lstrip("\n")
        
        # Отправляем части
        for i, part in enumerate(parts, 1):
            header = f"📋 <b>Traceback [{error_id}] — Часть {i}/{len(parts)}:</b>\n\n"
            await bot.send_message(
                chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
                text=header + f"<pre>{part}</pre>",
                parse_mode="HTML",
            )


@router.callback_query(lambda c: c.data and c.data.startswith("error_resolved:"))
async def callback_error_resolved(callback: CallbackQuery) -> None:
    """Администратор отметил ошибку как решённую."""
    error_id = callback.data.split(":")[1]
    
    # Удаляем из хранилища
    _error_storage.pop(error_id, None)
    
    await callback.answer("✅ Ошибка отмечена как решённая", show_alert=True)
    
    if callback.message:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>РЕШЕНО</b>",
            parse_mode="HTML",
        )
    
    logger.info(
        "error_resolved",
        admin_id=callback.from_user.id if callback.from_user else 0,
        error_id=error_id,
    )


# ============================================================
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК
# ============================================================

@router.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    """
    Глобальный обработчик всех ошибок бота.
    
    Классифицирует ошибки, генерирует уникальный ID,
    уведомляет пользователя и администраторов.
    
    Args:
        event: Событие ошибки
        
    Returns:
        True если ошибка обработана
    """
    exception = event.exception
    update = event.update
    
    # Генерируем уникальный ID ошибки
    error_id = generate_error_id()
    
    # Получаем событие для ответа пользователю
    user_event = None
    user_info = "N/A"
    context = "unknown"
    
    if update:
        if update.message:
            user_event = update.message
            if update.message.from_user:
                user = update.message.from_user
                user_info = f"ID: {user.id}, @{user.username or 'N/A'}, {user.first_name or ''}"
            context = f"message: {update.message.text[:50] if update.message.text else 'N/A'}"
        elif update.callback_query:
            user_event = update.callback_query
            if update.callback_query.from_user:
                user = update.callback_query.from_user
                user_info = f"ID: {user.id}, @{user.username or 'N/A'}, {user.first_name or ''}"
            context = f"callback: {update.callback_query.data or 'N/A'}"
    
    # Логируем ошибку с полным контекстом
    log_data: dict = {
        "error_id": error_id,
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        "user_info": user_info,
        "context": context,
    }
    
    # Классифицируем ошибку и определяем ключ сообщения
    error_key = "generic"
    should_notify_admin = False
    log_level = "error"
    
    if isinstance(exception, InsufficientBalanceError):
        error_key = "balance"
        log_level = "info"
        logger.info("insufficient_balance_error", **log_data)
        
    elif isinstance(exception, VisionAnalysisError):
        error_key = "vision"
        log_level = "warning"
        logger.warning("vision_analysis_error", **log_data)
        
    elif isinstance(exception, TextGenerationError):
        error_key = "generation"
        log_level = "warning"
        logger.warning("text_generation_error", **log_data)
        
    elif isinstance(exception, AIProviderError):
        error_key = "ai_provider"
        log_level = "error"
        should_notify_admin = True
        logger.error("ai_provider_error", **log_data, exc_info=True)
        
    elif isinstance(exception, ValidationError):
        error_key = "validation"
        log_level = "warning"
        logger.warning("validation_error", **log_data)
        
    elif isinstance(exception, GenerationError):
        error_key = "generation"
        log_level = "warning"
        logger.warning("generation_error", **log_data)
        
    elif isinstance(exception, TZGeneratorError):
        error_key = "generic"
        log_level = "error"
        should_notify_admin = True
        logger.error("tz_generator_error", **log_data, exc_info=True)
        
    elif isinstance(exception, TimeoutError):
        error_key = "timeout"
        log_level = "warning"
        logger.warning("timeout_error", **log_data)
        
    elif "NetworkError" in type(exception).__name__ or "network" in str(exception).lower():
        error_key = "network"
        log_level = "error"
        should_notify_admin = True
        logger.error("network_error", **log_data, exc_info=True)
        
    else:
        # Неизвестная ошибка - критическая
        log_level = "critical"
        should_notify_admin = True
        logger.critical("unhandled_critical_error", **log_data, exc_info=True)
    
    # Сохраняем детали ошибки
    store_error(error_id, {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "traceback": traceback.format_exception(type(exception), exception, exception.__traceback__),
        "user_info": user_info,
        "context": context,
        "timestamp": datetime.now().isoformat(),
        "log_level": log_level,
    })
    
    # Уведомляем пользователя
    if user_event:
        await send_error_to_user(user_event, error_key, error_id)
    
    # Уведомляем админов о критических ошибках
    if should_notify_admin:
        bot = getattr(event, 'bot', None)
        if bot:
            await notify_admins_about_error(
                bot=bot,
                error_id=error_id,
                exception=exception,
                user_info=user_info,
                context=context,
            )
    
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
                error_id = generate_error_id()
                
                # Находим event для ответа
                event = None
                for arg in args:
                    if isinstance(arg, (Message, CallbackQuery)):
                        event = arg
                        break
                
                if event:
                    await send_error_to_user(event, error_message, error_id)
                
                logger.error(
                    f"handler_error_in_{func.__name__}",
                    error_id=error_id,
                    error=str(e),
                    exc_info=True,
                )
                
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
