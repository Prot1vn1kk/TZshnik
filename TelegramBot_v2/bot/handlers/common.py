"""
Общие обработчики.

Содержит:
- Обработчик неизвестных сообщений
- Обработка отмены
- Вспомогательные callback-и
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import structlog

from database.models import User
from database import get_user_payments
from bot.keyboards import get_main_keyboard


logger = structlog.get_logger()
router = Router(name="common")


# ============================================================
# ОТМЕНА ПЛАТЕЖА
# ============================================================

@router.callback_query(F.data == "cancel_payment")
async def callback_cancel_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменить процесс оплаты."""
    await callback.answer()
    await state.clear()
    
    if callback.message:
        await callback.message.edit_text(
            "❌ Покупка отменена.\n\n"
            "Вы можете вернуться к выбору пакета в любой момент.",
        )


@router.callback_query(F.data == "payment_history")
async def callback_payment_history(
    callback: CallbackQuery,
    user: User,
) -> None:
    """История платежей пользователя."""
    await callback.answer()
    
    telegram_id = callback.from_user.id if callback.from_user else 0
    payments = await get_user_payments(telegram_id, limit=10)
    
    if not payments:
        if callback.message:
            await callback.message.edit_text(
                "💳 *История платежей*\n\n"
                "У вас пока нет платежей.",
                parse_mode="Markdown",
            )
        return
    
    lines = ["💳 *История платежей:*\n"]
    
    for payment in payments:
        status_emoji = "✅" if payment.status == "completed" else "⏳"
        date_str = payment.created_at.strftime("%d.%m.%Y")
        amount_rub = payment.amount / 100  # Из копеек в рубли
        lines.append(f"{status_emoji} {date_str} — {amount_rub:.0f}₽ ({payment.credits_added} ТЗ)")
    
    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )


@router.callback_query(F.data == "back")
async def callback_back(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Общая кнопка 'Назад'."""
    await callback.answer()
    await state.clear()
    
    if callback.message:
        await callback.message.edit_text(
            "Главное меню",
        )
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_keyboard(),
        )


# ============================================================
# ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ
# ============================================================

@router.message()
async def handle_unknown(message: Message, state: FSMContext) -> None:
    """
    Обработчик всех неизвестных сообщений.
    
    Срабатывает, если сообщение не было обработано другими хендлерами.
    """
    current_state = await state.get_state()
    
    if current_state:
        # Пользователь в процессе, но отправил что-то неожиданное
        await message.answer(
            "🤔 Не понимаю это сообщение.\n\n"
            "Пожалуйста, следуйте инструкциям или нажмите /start для перезапуска.",
        )
    else:
        # Обычный режим
        await message.answer(
            "👋 Используйте кнопки меню или команду /start",
            reply_markup=get_main_keyboard(),
        )
    
    logger.debug(
        "Unknown message received",
        telegram_id=message.from_user.id if message.from_user else 0,
        text=message.text[:50] if message.text else None,
        state=current_state,
    )
