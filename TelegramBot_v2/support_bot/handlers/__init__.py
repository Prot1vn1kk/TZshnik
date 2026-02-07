"""
Support Bot Handlers Package.

Объединяет все обработчики бота поддержки.
"""

from aiogram import Router

from .start import router as start_router
from .tickets import router as tickets_router
from .messaging import router as messaging_router


def get_support_router() -> Router:
    """
    Создать и настроить роутер бота поддержки.

    Returns:
        Router: Настроенный роутер со всеми обработчиками
    """
    support_router = Router(name="support")

    # Порядок важен: более специфичные обработчики первыми
    support_router.include_router(messaging_router)  # Ответы на сообщения
    support_router.include_router(tickets_router)     # Создание тикетов
    support_router.include_router(start_router)       # Start/help

    return support_router


__all__ = [
    "get_support_router",
    "start_router",
    "tickets_router",
    "messaging_router",
]
