"""
Клавиатуры для бота поддержки.

Предоставляет inline клавиатуры для создания тикетов,
просмотра списка тикетов и детального просмотра.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_support_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура бота поддержки."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🚀 Создать обращение", callback_data="support:create"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои обращения", callback_data="support:my_tickets"),
    )
    builder.row(
        InlineKeyboardButton(text="❓ Помощь", callback_data="support:help"),
    )

    return builder.as_markup()


def get_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора категории проблемы."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Проблемы с оплатой", callback_data="support:category:payment"),
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Техническая проблема", callback_data="support:category:technical"),
    )
    builder.row(
        InlineKeyboardButton(text="❓ Другое", callback_data="support:category:other"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="support:main"),
    )

    return builder.as_markup()


def get_tickets_list_keyboard(
    tickets: List,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """
    Клавиатура для списка тикетов пользователя.

    Args:
        tickets: Список тикетов
        page: Текущая страница
        total_pages: Общее количество страниц
    """
    builder = InlineKeyboardBuilder()

    status_emoji = {
        "open": "🆕",
        "in_progress": "⏳",
        "resolved": "✅",
        "archived": "📁",
    }

    for ticket in tickets:
        emoji = status_emoji.get(ticket.status, "❓")
        date = ticket.created_at.strftime("%d.%m")

        category_emoji = {
            "payment": "💳",
            "technical": "🔧",
            "other": "❓",
        }.get(ticket.category, "")

        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} #{ticket.id} | {date} {category_emoji}",
                callback_data=f"support:ticket:{ticket.id}",
            )
        )

    # Пагинация
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️", callback_data=f"support:my_tickets_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="support:page_info")
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(text="▶️", callback_data=f"support:my_tickets_page:{page+1}")
            )

        if nav_buttons:
            builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="support:main"),
    )

    return builder.as_markup()


def get_ticket_detail_keyboard(
    ticket_id: int,
    status: str,
) -> InlineKeyboardMarkup:
    """
    Клавиатура для детального просмотра тикета.

    Args:
        ticket_id: ID тикета
        status: Статус тикета
    """
    builder = InlineKeyboardBuilder()

    if status == "resolved":
        builder.row(
            InlineKeyboardButton(text="🔄 Переоткрыть", callback_data=f"support:reopen:{ticket_id}"),
        )
    elif status != "archived":
        builder.row(
            InlineKeyboardButton(text="✅ Решено", callback_data=f"support:close_ticket:{ticket_id}"),
        )

    builder.row(
        InlineKeyboardButton(text="📋 К списку", callback_data="support:my_tickets"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="support:main"),
    )

    return builder.as_markup()
