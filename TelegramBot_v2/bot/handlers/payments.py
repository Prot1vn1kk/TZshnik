"""
Обработчики платежей через YooKassa + Telegram Payments.

Содержит:
- Показ пакетов для покупки
- Создание Invoice
- Обработка pre_checkout_query
- Обработка успешной оплаты
"""

import structlog
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    Message,
    LabeledPrice,
    PreCheckoutQuery,
)

from bot.config import settings
from config.packages import get_package, get_all_packages
from database import increase_balance, create_payment
from database.models import User
from bot.keyboards import get_main_keyboard


logger = structlog.get_logger()
router = Router(name="payments")


# ============================================================
# ПОКАЗ ПАКЕТОВ
# ============================================================

@router.callback_query(F.data == "show_packages")
async def callback_show_packages(
    callback: CallbackQuery,
    user: User,
) -> None:
    """Показать доступные пакеты для покупки."""
    await callback.answer()
    
    text = (
        "💳 <b>Выбери пакет кредитов</b>\n\n"
        "Один кредит = одно ТЗ\n\n"
    )
    
    for package in get_all_packages():
        badge = ""
        if package.is_popular:
            badge = " 🔥 Популярный"
        elif package.is_best_value:
            badge = " 💎 Выгодный"
        
        text += (
            f"{package.emoji} <b>{package.name}</b>{badge}\n"
            f"   {package.credits} кредитов за {package.price_rub}₽ "
            f"({package.price_per_credit}₽/шт)\n\n"
        )
    
    text += f"\n💰 Твой баланс: {user.balance} кредитов"
    
    # Формируем клавиатуру
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    for package in get_all_packages():
        buttons.append([
            InlineKeyboardButton(
                text=package.button_text,
                callback_data=f"buy:{package.id}",
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


# ============================================================
# СОЗДАНИЕ INVOICE
# ============================================================

@router.callback_query(F.data.startswith("buy:"))
async def callback_buy_package(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
) -> None:
    """Обработка выбора пакета — создание Invoice."""
    await callback.answer()
    
    if not callback.data or not callback.message:
        return
    
    package_id = callback.data.split(":")[1]
    package = get_package(package_id)
    
    if not package:
        await callback.message.edit_text("⚠️ Пакет не найден")
        return
    
    user_id = callback.from_user.id if callback.from_user else 0
    
    logger.info(
        "payment_invoice_creating",
        user_id=user_id,
        package=package_id,
        amount=package.price_rub,
    )
    
    # Проверяем наличие токена YooKassa
    if not settings.yookassa_provider_token:
        await callback.message.edit_text(
            "⚠️ <b>Оплата временно недоступна</b>\n\n"
            "Платёжная система не настроена. "
            "Обратитесь к администратору.",
            parse_mode="HTML",
        )
        return
    
    # Удаляем сообщение с выбором
    await callback.message.delete()
    
    # Создаём Invoice через Telegram Payments
    try:
        await bot.send_invoice(
            chat_id=callback.message.chat.id,
            title=f"Пакет «{package.name}»",
            description=package.description,
            payload=f"credits:{package.id}:{user_id}",
            provider_token=settings.yookassa_provider_token,
            currency="RUB",
            prices=[
                LabeledPrice(
                    label=f"{package.credits} кредитов",
                    amount=package.price_kopecks,  # В копейках!
                )
            ],
            start_parameter=f"buy_{package.id}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False,  # Фиксированная цена
        )
    except Exception as e:
        logger.error("invoice_creation_failed", error=str(e))
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=(
                "❌ <b>Ошибка создания платежа</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку."
            ),
            parse_mode="HTML",
        )


# ============================================================
# PRE-CHECKOUT
# ============================================================

@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout: PreCheckoutQuery) -> None:
    """
    Обработка pre_checkout_query.
    
    Telegram спрашивает: "Можно проводить оплату?"
    Проверяем валидность запроса и отвечаем.
    """
    logger.info(
        "pre_checkout_query",
        user_id=pre_checkout.from_user.id,
        total_amount=pre_checkout.total_amount,
        payload=pre_checkout.invoice_payload,
    )
    
    # Валидируем payload
    try:
        parts = pre_checkout.invoice_payload.split(":")
        
        if len(parts) != 3 or parts[0] != "credits":
            await pre_checkout.answer(
                ok=False,
                error_message="Некорректный запрос. Попробуйте заново.",
            )
            return
        
        package_id = parts[1]
        package = get_package(package_id)
        
        if not package:
            await pre_checkout.answer(
                ok=False,
                error_message="Пакет не найден. Попробуйте заново.",
            )
            return
        
        # Проверяем что цена не изменилась
        if pre_checkout.total_amount != package.price_kopecks:
            await pre_checkout.answer(
                ok=False,
                error_message="Цена изменилась. Попробуйте заново.",
            )
            return
        
    except Exception as e:
        logger.error("pre_checkout_validation_error", error=str(e))
        await pre_checkout.answer(
            ok=False,
            error_message="Ошибка валидации. Попробуйте заново.",
        )
        return
    
    # Всё ок — разрешаем оплату
    await pre_checkout.answer(ok=True)
    logger.info("pre_checkout_approved", user_id=pre_checkout.from_user.id)


# ============================================================
# УСПЕШНАЯ ОПЛАТА
# ============================================================

@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    user: User,
) -> None:
    """
    Обработка успешной оплаты.
    
    Telegram присылает это сообщение после подтверждения оплаты YooKassa.
    Начисляем кредиты и сохраняем платёж в БД.
    """
    payment = message.successful_payment
    
    if not payment or not message.from_user:
        logger.error("payment_data_missing")
        return
    
    logger.info(
        "payment_successful",
        user_id=message.from_user.id,
        telegram_payment_id=payment.telegram_payment_charge_id,
        provider_payment_id=payment.provider_payment_charge_id,
        total_amount=payment.total_amount,
        currency=payment.currency,
        payload=payment.invoice_payload,
    )
    
    try:
        # Парсим payload
        parts = payment.invoice_payload.split(":")
        package_id = parts[1]
        payload_user_id = int(parts[2])
        
        # Проверяем что это тот же пользователь
        if message.from_user.id != payload_user_id:
            logger.error(
                "payment_user_mismatch",
                actual_user=message.from_user.id,
                payload_user=payload_user_id,
            )
            await message.answer(
                "⚠️ Ошибка обработки платежа. Обратитесь в поддержку."
            )
            return
        
        # Получаем пакет
        package = get_package(package_id)
        if not package:
            logger.error("payment_package_not_found", package_id=package_id)
            await message.answer(
                "⚠️ Пакет не найден. Обратитесь в поддержку."
            )
            return
        
        # Начисляем кредиты
        await increase_balance(message.from_user.id, package.credits)
        
        # Сохраняем платёж в БД
        await create_payment(
            user_id=user.id,
            telegram_payment_id=payment.telegram_payment_charge_id,
            amount=payment.total_amount,  # В копейках
            credits_added=package.credits,
            package_name=package.name,
            currency=payment.currency,
        )
        
        # Получаем новый баланс
        new_balance = user.balance + package.credits
        
        # Отправляем подтверждение
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"📦 Пакет: {package.display_name}\n"
            f"💰 Начислено: +{package.credits} кредитов\n"
            f"💳 Сумма: {package.price_rub}₽\n\n"
            f"🏦 Ваш баланс: {new_balance} кредитов\n\n"
            f"Нажмите 📸 <b>Создать ТЗ</b>, чтобы начать!",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML",
        )
        
        logger.info(
            "credits_added",
            user_id=message.from_user.id,
            credits=package.credits,
            new_balance=new_balance,
        )
        
    except Exception as e:
        logger.exception("payment_processing_error")
        await message.answer(
            "⚠️ Произошла ошибка при начислении кредитов.\n"
            "Платёж прошёл успешно. Обратитесь в поддержку."
        )


# ============================================================
# ОТМЕНА
# ============================================================

@router.callback_query(F.data == "cancel_payment")
async def callback_cancel_payment(callback: CallbackQuery) -> None:
    """Отмена выбора пакета."""
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.edit_text(
            "❌ Покупка отменена.\n\n"
            "Нажмите 💳 <b>Купить кредиты</b> в меню, чтобы выбрать пакет.",
            parse_mode="HTML",
        )
