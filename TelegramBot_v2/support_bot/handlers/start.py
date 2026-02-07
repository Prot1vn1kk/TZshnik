"""
Обработчики команд бота поддержки.

Обрабатывает /start, /help, /my_tickets команды.
"""

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
import structlog

from database.models import User
from database.support_crud import get_user_tickets
from support_bot.states import TicketCreationStates
from support_bot.keyboards.support_keyboards import (
    get_support_main_keyboard,
    get_category_keyboard,
    get_tickets_list_keyboard,
)


logger = structlog.get_logger()
router = Router(name="support_start")


# Шаблоны сообщений
START_MESSAGE = """
🎯 <b>Служба поддержки ТЗшник</b>

Здесь ты можешь создать обращение в техническую поддержку.

━━━━━━━━━━━━━━━━━━━━━

<b>Что мы можем помочь:</b>
💳 <b>Проблемы с оплатой</b> — вопросы по платежам
🔧 <b>Технические проблемы</b> — ошибки, баги
❓ <b>Другое</b> — любые другие вопросы

━━━━━━━━━━━━━━━━━━━━━

👇 Нажми «Создать обращение» чтобы начать!
"""


HELP_MESSAGE = """
📖 <b>Справка службы поддержки</b>

<b>Команды:</b>
/start — Главное меню
/help — Эта справка
/my_tickets — Мои обращения

<b>Как создать обращение:</b>
1. Нажми «Создать обращение»
2. Выбери категорию проблемы
3. Опиши ситуацию подробно
4. Отправь сообщение

<b>Что дальше:</b>
• Мы ответим в течение 24 часов
• Уведомление придёт в этот бот
• Можно вести диалог в рамках обращения

<b>Категории:</b>
💳 Проблемы с оплатой — вопросы по платежам, пополнению баланса
🔧 Технические проблемы — ошибки при генерации, баги
❓ Другое — предложения, жалобы, вопросы
"""


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user: User,
) -> None:
    """
    Обработать команду /start.

    Показывает приветственное сообщение и главное меню.
    """
    await message.answer(
        START_MESSAGE,
        reply_markup=get_support_main_keyboard(),
    )

    logger.info(
        "support_bot_user_started",
        telegram_id=user.telegram_id,
        username=user.username,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработать команду /help."""
    await message.answer(
        HELP_MESSAGE,
        reply_markup=get_support_main_keyboard(),
    )


@router.message(Command("my_tickets"))
async def cmd_my_tickets(
    message: Message,
    user: User,
) -> None:
    """
    Обработать команду /my_tickets.

    Показывает тикеты пользователя.
    """
    tickets = await get_user_tickets(user.id, limit=10)

    if not tickets:
        await message.answer(
            "📋 <b>Мои обращения</b>\n\n"
            "У тебя пока нет обращений в поддержку.\n"
            "Нажми «Создать обращение» чтобы создать первое.",
            reply_markup=get_support_main_keyboard(),
        )
        return

    text = "📋 <b>Мои обращения:</b>\n\n"

    status_emoji = {
        "open": "🆕",
        "in_progress": "⏳",
        "resolved": "✅",
        "archived": "📁",
    }

    for ticket in tickets:
        status = ticket.status
        emoji = status_emoji.get(status, "❓")
        date = ticket.created_at.strftime("%d.%m %H:%M")
        category = {
            "payment": "💳 Оплата",
            "technical": "🔧 Техника",
            "other": "❓ Другое",
        }.get(ticket.category, ticket.category)

        text += f"{emoji} #{ticket.id} | {date} | {category}\n"

    await message.answer(
        text,
        reply_markup=get_tickets_list_keyboard(tickets),
    )


@router.callback_query(F.data == "support:create")
@router.message(F.text == "🚀 Создать обращение")
async def action_create_ticket(
    event: Message | CallbackQuery,
    state,
) -> None:
    """Обработать кнопку «Создать обращение»."""
    await state.set_state(TicketCreationStates.choosing_category)

    message = event.message if isinstance(event, CallbackQuery) else event
    await message.answer(
        "📋 <b>Выбери категорию проблемы:</b>",
        reply_markup=get_category_keyboard(),
    )

    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(F.data == "support:help")
async def callback_help(callback: CallbackQuery) -> None:
    """Показать справку."""
    await callback.answer()
    await callback.message.edit_text(
        HELP_MESSAGE,
        reply_markup=get_support_main_keyboard(),
    )


@router.callback_query(F.data == "support:main")
async def callback_main_menu(
    callback: CallbackQuery,
    state,
) -> None:
    """Вернуться в главное меню."""
    await state.clear()
    await callback.answer()

    await callback.message.edit_text(
        START_MESSAGE,
        reply_markup=get_support_main_keyboard(),
    )
