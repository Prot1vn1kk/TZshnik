"""
Обработчики создания и просмотра тикетов.

Обрабатывает flow создания тикета и просмотр детальной информации.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog

from database.models import User

# Условный импорт support_crud (техподдержка - опциональный модуль)
try:
    from database.support_crud import (
        create_support_ticket,
        get_ticket_with_messages,
        get_user_tickets,
        update_ticket_status,
    )
    _HAS_SUPPORT_CRUD = True
except ImportError:
    _HAS_SUPPORT_CRUD = False
    async def create_support_ticket(*args, **kwargs):
        return None
    async def get_ticket_with_messages(*args, **kwargs):
        return None
    async def get_user_tickets(*args, **kwargs):
        return []
    async def update_ticket_status(*args, **kwargs):
        return False

from support_bot.states import TicketCreationStates, TicketMessagingStates
from support_bot.keyboards.support_keyboards import (
    get_support_main_keyboard,
    get_ticket_detail_keyboard,
    get_tickets_list_keyboard,
)


logger = structlog.get_logger()
router = Router(name="support_tickets")


TICKET_CREATED_MESSAGE = """
✅ <b>Обращение создано!</b>

Номер: <b>#{ticket_id}</b>
Категория: {category}
Статус: 🆕 Открыто

━━━━━━━━━━━━━━━━━━━━━

Мы ответим в течение 24 часов.
Уведомление придёт в этот бот.

Можешь добавить информацию в любое время,
нажав «Мои обращения» → выбрав обращение.
"""


@router.callback_query(TicketCreationStates.choosing_category, F.data.startswith("support:category:"))
async def callback_category_selected(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработать выбор категории."""
    category = callback.data.split(":")[2]

    await state.update_data(category=category)
    await state.set_state(TicketCreationStates.entering_description)

    category_names = {
        "payment": "💳 Проблемы с оплатой",
        "technical": "🔧 Техническая проблема",
        "other": "❓ Другое",
    }

    await callback.answer()
    await callback.message.edit_text(
        f"📝 <b>Опиши проблему подробно</b>\n\n"
        f"Категория: {category_names.get(category, category)}\n\n"
        f"Пожалуйста, опиши:\n"
        f"• Что случилось?\n"
        f"• Когда это произошло?\n"
        f"• Что ты уже пробовал?\n\n"
        f"<i>Минимум 10 символов</i>",
        reply_markup=None,
    )


@router.message(TicketCreationStates.entering_description, F.text)
async def handle_description(
    message: Message,
    state: FSMContext,
    user: User,
) -> None:
    """Обработать описание проблемы и создать тикет."""
    # Проверка доступности support_crud
    if not _HAS_SUPPORT_CRUD:
        await message.answer(
            "⚠️ <b>Служба поддержки временно недоступна</b>\n\n"
            "Пожалуйста, попробуй позже или обратись к администратору.",
            reply_markup=get_support_main_keyboard(),
        )
        await state.clear()
        return

    description = message.text.strip()

    # Валидация длины
    if len(description) < 10:
        await message.answer(
            "❌ Слишком короткое описание.\n\n"
            "Пожалуйста, опиши проблему подробнее (минимум 10 символов).",
        )
        return

    if len(description) > 2000:
        await message.answer(
            "❌ Слишком длинное описание.\n\n"
            "Пожалуйста, сократи текст (максимум 2000 символов).",
        )
        return

    # Получаем категорию из состояния
    data = await state.get_data()
    category = data.get("category", "other")

    try:
        # Создаём тикет в БД
        ticket = await create_support_ticket(
            user_id=user.id,
            category=category,
            description=description,
            sender_telegram_id=user.telegram_id,
        )

        # Уведомляем админов
        from support_bot.utils import notify_admins_about_ticket
        await notify_admins_about_ticket(ticket, user, message.bot)

        # Очищаем состояние и показываем подтверждение
        await state.clear()

        category_names = {
            "payment": "💳 Оплата",
            "technical": "🔧 Техническая проблема",
            "other": "❓ Другое",
        }

        await message.answer(
            TICKET_CREATED_MESSAGE.format(
                ticket_id=ticket.id,
                category=category_names.get(category, category),
            ),
            reply_markup=get_support_main_keyboard(),
        )

        logger.info(
            "support_ticket_created",
            ticket_id=ticket.id,
            user_id=user.id,
            category=category,
        )

    except Exception as e:
        logger.error(
            "failed_to_create_ticket",
            error=str(e),
            user_id=user.id,
        )
        await message.answer(
            "❌ Произошла ошибка при создании обращения.\n"
            "Пожалуйста, попробуй позже.",
            reply_markup=get_support_main_keyboard(),
        )


@router.callback_query(F.data == "support:my_tickets")
async def callback_my_tickets(
    callback: CallbackQuery,
    user: User,
) -> None:
    """Показать список тикетов пользователя."""
    tickets = await get_user_tickets(user.id, limit=10)

    if not tickets:
        await callback.answer()
        await callback.message.edit_text(
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

    await callback.answer()
    await callback.message.edit_text(
        text,
        reply_markup=get_tickets_list_keyboard(tickets),
    )


@router.callback_query(F.data.startswith("support:ticket:"))
async def callback_view_ticket(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Показать детальную информацию о тикете."""
    ticket_id = int(callback.data.split(":")[2])

    ticket = await get_ticket_with_messages(ticket_id)

    if not ticket:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    # Форматируем информацию о тикете
    status_emoji = {
        "open": "🆕",
        "in_progress": "⏳",
        "resolved": "✅",
        "archived": "📁",
    }

    category_names = {
        "payment": "💳 Оплата",
        "technical": "🔧 Техническая проблема",
        "other": "❓ Другое",
    }

    text = f"""📋 <b>Обращение #{ticket.id}</b>

{category_names.get(ticket.category, ticket.category)}
Статус: {status_emoji.get(ticket.status, ticket.status)}
Создано: {ticket.created_at.strftime("%d.%m.%Y %H:%M")}

━━━━━━━━━━━━━━━━━━━━━

<b>Сообщения:</b>"""

    for msg in ticket.messages[-5:]:  # Показываем последние 5 сообщений
        sender = "👤 Ты" if msg.sender_type == "user" else "👨‍💻 Поддержка"
        time = msg.created_at.strftime("%H:%M")
        text += f"\n\n{sender} ({time}):\n{msg.text}"

    await state.set_state(TicketMessagingStates.replying_to_admin)
    await state.update_data(ticket_id=ticket.id)

    await callback.answer()
    await callback.message.edit_text(
        text,
        reply_markup=get_ticket_detail_keyboard(ticket.id, ticket.status),
    )


@router.callback_query(F.data.startswith("support:close_ticket:"))
async def callback_close_ticket(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Закрыть тикет (пользователь отмечает как решённый)."""
    if not _HAS_SUPPORT_CRUD:
        await callback.answer("⚠️ Служба поддержки временно недоступна", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])

    await update_ticket_status(
        ticket_id=ticket_id,
        status="resolved",
    )

    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "✅ <b>Обращение закрыто</b>\n\n"
        "Спасибо за обращение!\n"
        "Если возникнут вопросы — создавай новое обращение.",
    )

    logger.info("support_ticket_closed_by_user", ticket_id=ticket_id)


@router.callback_query(F.data.startswith("support:reopen:"))
async def callback_reopen_ticket(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Переоткрыть тикет."""
    if not _HAS_SUPPORT_CRUD:
        await callback.answer("⚠️ Служба поддержки временно недоступна", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])

    await update_ticket_status(
        ticket_id=ticket_id,
        status="open",
    )

    await callback.answer("Тикет переоткрыт", show_alert=True)

    # Перезагружаем просмотр тикета
    ticket = await get_ticket_with_messages(ticket_id)

    if ticket:
        status_emoji = {
            "open": "🆕",
            "in_progress": "⏳",
            "resolved": "✅",
            "archived": "📁",
        }

        category_names = {
            "payment": "💳 Оплата",
            "technical": "🔧 Техническая проблема",
            "other": "❓ Другое",
        }

        text = f"""📋 <b>Обращение #{ticket.id}</b>

{category_names.get(ticket.category, ticket.category)}
Статус: {status_emoji.get(ticket.status, ticket.status)}
Создано: {ticket.created_at.strftime("%d.%m.%Y %H:%M")}

━━━━━━━━━━━━━━━━━━━━━

<b>Сообщения:</b>"""

        for msg in ticket.messages[-5:]:
            sender = "👤 Ты" if msg.sender_type == "user" else "👨‍💻 Поддержка"
            time = msg.created_at.strftime("%H:%M")
            text += f"\n\n{sender} ({time}):\n{msg.text}"

        await state.set_state(TicketMessagingStates.replying_to_admin)
        await state.update_data(ticket_id=ticket.id)

        await callback.message.edit_text(
            text,
            reply_markup=get_ticket_detail_keyboard(ticket.id, ticket.status),
        )

    logger.info("support_ticket_reopened_by_user", ticket_id=ticket_id)
