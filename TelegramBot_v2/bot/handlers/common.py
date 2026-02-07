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

from bot.keyboards import get_main_menu_keyboard


logger = structlog.get_logger()
router = Router(name="common")


# ============================================================
# ОТМЕНА ПЛАТЕЖА
# ============================================================

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
            reply_markup=get_main_menu_keyboard(),
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
            reply_markup=get_main_menu_keyboard(),
        )
    
    logger.debug(
        "Unknown message received",
        telegram_id=message.from_user.id if message.from_user else 0,
        text=message.text[:50] if message.text else None,
        state=current_state,
    )
