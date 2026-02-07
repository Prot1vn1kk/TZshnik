"""
Support Bot Keyboards Package.

Клавиатуры для бота поддержки.
"""

from .support_keyboards import (
    get_support_main_keyboard,
    get_category_keyboard,
    get_tickets_list_keyboard,
    get_ticket_detail_keyboard,
)

__all__ = [
    "get_support_main_keyboard",
    "get_category_keyboard",
    "get_tickets_list_keyboard",
    "get_ticket_detail_keyboard",
]
