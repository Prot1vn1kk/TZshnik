"""
Обработчики сообщений в тикетах.

Обрабатывает ответы пользователя на сообщения администратора.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog

from database.models import User
from database.support_crud import add_ticket_message
from support_bot.states import TicketMessagingStates
from support_bot.keyboards.support_keyboards import get_ticket_detail_keyboard


logger = structlog.get_logger()
router = Router(name="support_messaging")


@router.message(TicketMessagingStates.replying_to_admin, F.text)
async def handle_user_reply(
    message: Message,
    state: FSMContext,
    user: User,
) -> None:
    """Обработать ответ пользователя на сообщение админа."""
    text = message.text.strip()

    if len(text) > 2000:
        await message.answer(
            "❌ Слишком длинное сообщение (максимум 2000 символов).",
        )
        return

    # Получаем ID тикета из состояния
    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    if not ticket_id:
        await state.clear()
        await message.answer(
            "❌ Ошибка сессии. Пожалуйста, выбери обращение заново.",
        )
        return

    try:
        # Добавляем сообщение в тикет
        msg = await add_ticket_message(
            ticket_id=ticket_id,
            sender_type="user",
            sender_telegram_id=user.telegram_id,
            text=text,
        )

        # Уведомляем админов о новом сообщении
        from support_bot.utils import notify_admins_about_new_user_message
        await notify_admins_about_new_user_message(
            ticket_id=ticket_id,
            user=user,
            message_text=text,
            bot=message.bot,
        )

        await message.answer(
            "✅ Сообщение отправлено!\n\n"
            "Мы ответим в ближайшее время.",
        )

        logger.info(
            "support_user_reply_sent",
            ticket_id=ticket_id,
            user_id=user.id,
        )

    except Exception as e:
        logger.error(
            "failed_to_send_user_reply",
            error=str(e),
            ticket_id=ticket_id,
        )
        await message.answer(
            "❌ Произошла ошибка при отправке сообщения.",
        )
