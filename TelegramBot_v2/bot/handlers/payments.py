"""
Обработчики платежей через YooKassa + Telegram Payments.

Содержит:
- Показ пакетов для покупки
- Создание Invoice
- Обработка pre_checkout_query
- Обработка успешной оплаты
- Управление безлимитной подпиской
"""

import structlog
import math
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    Message,
    LabeledPrice,
    PreCheckoutQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from config.packages import (
    get_package, 
    get_all_packages, 
    get_regular_packages,
    get_unlimited_packages,
    get_packages_by_category,
    calculate_savings,
    BASE_PRICE_PER_CREDIT,
)
from database import increase_balance, create_payment, activate_unlimited, is_unlimited_active
from database.models import User
from bot.keyboards import get_main_menu_keyboard


logger = structlog.get_logger()
router = Router(name="payments")


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def format_number(num: int) -> str:
    """Форматирование числа с пробелами (1000 -> 1 000)."""
    return f"{num:,}".replace(",", " ")


def get_subscription_status(user: User) -> dict:
    """Получить статус подписки пользователя."""
    if not is_unlimited_active(user):
        return {
            "is_unlimited": False,
            "unlimited_until": None,
            "days_left": 0,
        }

    now = datetime.utcnow()
    delta = user.unlimited_until - now if user.unlimited_until else timedelta(0)
    days_left = max(0, math.ceil(delta.total_seconds() / 86400))

    return {
        "is_unlimited": True,
        "unlimited_until": user.unlimited_until,
        "days_left": days_left,
    }


def build_packages_keyboard(
    show_back: bool = True,
    highlight_popular: bool = True,
) -> InlineKeyboardMarkup:
    """
    Создать профессиональную клавиатуру выбора пакетов.
    """
    builder = InlineKeyboardBuilder()
    
    # Разделитель: Пакеты для начинающих
    starter_packages = get_packages_by_category("starter")
    
    # Добавляем стартовые пакеты (3 в ряд)
    for pkg in starter_packages:
        savings_text = f" (-{pkg.savings_percent}%)" if pkg.savings_percent > 0 else ""
        builder.button(
            text=f"{pkg.emoji} {pkg.credits} ТЗ • {pkg.price_rub}₽{savings_text}",
            callback_data=f"buy:{pkg.id}",
        )
    
    # Популярные пакеты
    popular_packages = get_packages_by_category("popular")
    for pkg in popular_packages:
        badge = "🔥 " if pkg.is_popular else ""
        savings_text = f" (-{pkg.savings_percent}%)" if pkg.savings_percent > 0 else ""
        builder.button(
            text=f"{badge}{pkg.emoji} {pkg.credits} ТЗ • {pkg.price_rub}₽{savings_text}",
            callback_data=f"buy:{pkg.id}",
        )
    
    # Бизнес пакеты
    business_packages = get_packages_by_category("business")
    for pkg in business_packages:
        badge = "💎 " if pkg.is_best_value else ""
        savings_text = f" (-{pkg.savings_percent}%)" if pkg.savings_percent > 0 else ""
        builder.button(
            text=f"{badge}{pkg.emoji} {pkg.credits} ТЗ • {format_number(pkg.price_rub)}₽{savings_text}",
            callback_data=f"buy:{pkg.id}",
        )
    
    # Безлимитный тариф — отдельно и выделенно
    unlimited_packages = get_unlimited_packages()
    if unlimited_packages:
        pkg = unlimited_packages[0]
        builder.button(
            text=f"👑 БЕЗЛИМИТ {pkg.duration_days} дней • {format_number(pkg.price_rub)}₽",
            callback_data=f"buy:{pkg.id}",
        )
    
    # Информационные кнопки
    builder.button(
        text="❓ Как это работает",
        callback_data="packages_help",
    )
    
    if show_back:
        builder.button(
            text="⬅️ Назад",
            callback_data="show_main_menu",
        )
        builder.button(
            text="❌ Отмена",
            callback_data="cancel_payment",
        )
    
    # Расположение кнопок: 3-2-2-1-1-2
    builder.adjust(3, 2, 2, 1, 1, 2)
    return builder.as_markup()


def build_package_detail_keyboard(package_id: str) -> InlineKeyboardMarkup:
    """Клавиатура детального просмотра пакета."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="✅ Оплатить",
        callback_data=f"confirm_buy:{package_id}",
    )
    builder.button(
        text="⬅️ К пакетам",
        callback_data="show_packages",
    )
    builder.button(
        text="❌ Отмена",
        callback_data="cancel_payment",
    )
    
    builder.adjust(1, 2)
    return builder.as_markup()


# ============================================================
# ПОКАЗ ПАКЕТОВ
# ============================================================

@router.callback_query(F.data == "show_packages")
async def callback_show_packages(
    callback: CallbackQuery,
    user: User,
) -> None:
    """Показать профессиональное меню пакетов."""
    await callback.answer()
    
    # Получаем статус подписки
    sub_status = get_subscription_status(user)
    
    # Формируем заголовок
    text = (
        "💳 <b>Пополнение баланса</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Текущий баланс
    if sub_status["is_unlimited"] and sub_status["unlimited_until"]:
        days_left = sub_status["days_left"]
        text += (
            f"👑 <b>У вас активен БЕЗЛИМИТ</b>\n"
            f"   Осталось дней: {days_left}\n\n"
        )
    else:
        balance_emoji = "🟢" if user.balance >= 5 else "🟡" if user.balance > 0 else "🔴"
        text += f"{balance_emoji} Ваш баланс: <b>{user.balance}</b> кредитов\n\n"
    
    # Описание пакетов по категориям
    text += (
        "📦 <b>Выберите пакет:</b>\n\n"
        
        "<b>🎯 Для старта</b>\n"
        "   <i>Пробный • Старт • Базовый</i>\n\n"
        
        "<b>⭐ Популярные</b>\n"
        "   <i>Оптимальный • Профи</i>\n\n"
        
        "<b>💼 Для бизнеса</b>\n"
        "   <i>Бизнес • Корпоративный</i>\n\n"
        
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <b>БЕЗЛИМИТ</b> — неограниченные генерации\n"
        "   30 дней за 1 790₽ • Без лимитов!\n\n"
        
        "💡 <i>Чем больше пакет — тем выгоднее!</i>\n"
    )
    
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=build_packages_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "packages_help")
async def callback_packages_help(callback: CallbackQuery) -> None:
    """Справка о системе кредитов."""
    await callback.answer()
    
    text = (
        "❓ <b>Как работают кредиты</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "📍 <b>1 кредит = 1 генерация ТЗ</b>\n"
        "   Загрузите фото товара и получите готовое\n"
        "   техническое задание для маркетплейса.\n\n"
        
        "💰 <b>Экономия при покупке:</b>\n"
        f"   • Базовая цена: {int(BASE_PRICE_PER_CREDIT)}₽ за ТЗ\n"
        "   • Пакеты: <b>до 63% экономии</b>\n"
        "   • Безлимит: <b>неограниченные</b> генерации\n\n"
        
        "⏱ <b>Срок действия:</b>\n"
        "   • Кредиты: <b>бессрочно</b>\n"
        "   • Безлимит: 30 дней с момента покупки\n\n"
        
        "🔒 <b>Гарантии:</b>\n"
        "   • Оплата через YooKassa (Сбер)\n"
        "   • Моментальное зачисление\n"
        "   • Поддержка 24/7\n\n"
        
        "📧 Вопросы: @TZshnik_support_bot"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К пакетам", callback_data="show_packages")
    
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )


# ============================================================
# ДЕТАЛИ ПАКЕТА И ПОДТВЕРЖДЕНИЕ
# ============================================================

@router.callback_query(F.data.startswith("buy:"))
async def callback_buy_package(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
) -> None:
    """Показать детали пакета и запросить подтверждение."""
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
        "package_selected",
        user_id=user_id,
        package=package_id,
    )
    
    # Формируем детальное описание
    if package.is_unlimited:
        savings = calculate_savings(package)
        text = (
            f"👑 <b>Безлимитная подписка</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Тариф:</b> {package.display_name}\n"
            f"⏱ <b>Срок:</b> {package.duration_days} дней\n"
            f"💳 <b>Стоимость:</b> {format_number(package.price_rub)}₽\n\n"
            f"✨ <b>Что включено:</b>\n"
            f"   • Неограниченные генерации ТЗ\n"
            f"   • Приоритетная обработка\n"
            f"   • Доступ к новым функциям\n\n"
            f"🎯 <i>Идеально для активных продавцов!</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Нажмите «Оплатить» для перехода к оплате"
        )
    else:
        savings = calculate_savings(package)
        savings_text = f"\n💰 <b>Экономия:</b> {savings}₽ ({package.savings_percent}%)" if savings > 0 else ""
        
        text = (
            f"{package.emoji} <b>Пакет «{package.name}»</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Кредитов:</b> {package.credits} ТЗ\n"
            f"💳 <b>Стоимость:</b> {format_number(package.price_rub)}₽\n"
            f"📊 <b>Цена за 1 ТЗ:</b> {package.price_per_credit}₽"
            f"{savings_text}\n\n"
        )
        
        if package.is_popular:
            text += "🔥 <i>Самый популярный выбор!</i>\n\n"
        elif package.is_best_value:
            text += "💎 <i>Лучшее соотношение цена/качество!</i>\n\n"
        
        text += (
            f"💰 Ваш баланс: {user.balance} → <b>{user.balance + package.credits}</b> кредитов\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Нажмите «Оплатить» для перехода к оплате"
        )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=build_package_detail_keyboard(package_id),
        parse_mode="HTML",
    )


# ============================================================
# СОЗДАНИЕ INVOICE
# ============================================================

@router.callback_query(F.data.startswith("confirm_buy:"))
async def callback_confirm_buy(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
) -> None:
    """Создание Invoice после подтверждения."""
    await callback.answer("Создаём платёж...")
    
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
            "Платёжная система не настроена.\n"
            "Обратитесь к администратору: @TZshnik_support_bot",
            parse_mode="HTML",
        )
        logger.error("yookassa_token_missing")
        return
    
    # Удаляем сообщение с выбором
    await callback.message.delete()
    
    # Формируем описание для Invoice
    if package.is_unlimited:
        invoice_title = f"👑 Безлимит на {package.duration_days} дней"
        invoice_description = (
            f"Безлимитная подписка TZ Generator\n"
            f"• {package.duration_days} дней неограниченных генераций\n"
            f"• Приоритетная обработка\n"
            f"• Доступ к новым функциям"
        )
        label_text = f"Безлимит {package.duration_days} дней"
    else:
        invoice_title = f"{package.emoji} Пакет «{package.name}»"
        invoice_description = (
            f"Пакет кредитов TZ Generator\n"
            f"• {package.credits} генераций ТЗ\n"
            f"• Цена за ТЗ: {package.price_per_credit}₽\n"
            f"• Бессрочное использование"
        )
        label_text = f"{package.credits} кредитов"
    
    # Создаём Invoice через Telegram Payments
    try:
        await bot.send_invoice(
            chat_id=callback.message.chat.id,
            title=invoice_title,
            description=invoice_description,
            payload=f"credits:{package.id}:{user_id}",
            provider_token=settings.yookassa_provider_token,
            currency="RUB",
            prices=[
                LabeledPrice(
                    label=label_text,
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
            protect_content=True,  # Защита от пересылки
        )
        
        logger.info(
            "invoice_sent",
            user_id=user_id,
            package=package_id,
        )
        
    except Exception as e:
        logger.error("invoice_creation_failed", error=str(e))
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=(
                "❌ <b>Ошибка создания платежа</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку:\n"
                "@TZshnik_support_bot"
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
    Начисляем кредиты или активируем безлимит и сохраняем платёж в БД.
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
                "⚠️ Ошибка обработки платежа. Обратитесь в поддержку:\n"
                "@TZshnik_support_bot"
            )
            return
        
        # Получаем пакет
        package = get_package(package_id)
        if not package:
            logger.error("payment_package_not_found", package_id=package_id)
            await message.answer(
                "⚠️ Пакет не найден. Обратитесь в поддержку:\n"
                "@TZshnik_support_bot"
            )
            return
        
        # Обрабатываем в зависимости от типа пакета
        if package.is_unlimited:
            # Активируем безлимитную подписку
            expiry_date = await activate_unlimited(message.from_user.id, package.duration_days)
            
            if not expiry_date:
                logger.error("unlimited_activation_failed", user_id=message.from_user.id)
                await message.answer(
                    "⚠️ Не удалось активировать безлимит. Обратитесь в поддержку:\n"
                    "@TZshnik_support_bot"
                )
                return
            
            # Сохраняем платёж в БД
            await create_payment(
                user_id=user.id,
                telegram_payment_id=payment.telegram_payment_charge_id,
                amount=payment.total_amount,
                credits_added=0,  # Безлимит не добавляет кредиты
                package_name=f"Безлимит {package.duration_days} дней",
                currency=payment.currency,
            )
            
            # Отправляем подтверждение для безлимита
            await message.answer(
                f"✅ <b>Безлимит активирован!</b>\n\n"
                f"👑 <b>Тариф:</b> Безлимитная подписка\n"
                f"⏱ <b>Срок:</b> {package.duration_days} дней\n"
                f"📅 <b>Действует до:</b> {expiry_date.strftime('%d.%m.%Y')}\n"
                f"💳 <b>Оплачено:</b> {format_number(package.price_rub)}₽\n\n"
                f"🎉 Теперь вы можете генерировать ТЗ без ограничений!\n\n"
                f"Нажмите 🚀 <b>Создать ТЗ</b>, чтобы начать!",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            
            logger.info(
                "unlimited_activated",
                user_id=message.from_user.id,
                duration_days=package.duration_days,
                expiry_date=expiry_date.isoformat(),
            )
            
        else:
            # Стандартный пакет — начисляем кредиты
            await increase_balance(message.from_user.id, package.credits)
            
            # Сохраняем платёж в БД
            await create_payment(
                user_id=user.id,
                telegram_payment_id=payment.telegram_payment_charge_id,
                amount=payment.total_amount,
                credits_added=package.credits,
                package_name=package.name,
                currency=payment.currency,
            )
            
            # Получаем новый баланс
            new_balance = user.balance + package.credits
            
            # Формируем сообщение успеха
            savings = calculate_savings(package)
            savings_text = f"\n💰 Вы сэкономили: {savings}₽" if savings > 0 else ""
            
            # Отправляем подтверждение
            await message.answer(
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"📦 <b>Пакет:</b> {package.display_name}\n"
                f"➕ <b>Начислено:</b> +{package.credits} кредитов\n"
                f"💳 <b>Оплачено:</b> {format_number(package.price_rub)}₽"
                f"{savings_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏦 <b>Ваш баланс:</b> {new_balance} кредитов\n\n"
                f"Нажмите 🚀 <b>Создать ТЗ</b>, чтобы начать!",
                reply_markup=get_main_menu_keyboard(),
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
            "⚠️ Произошла ошибка при обработке платежа.\n"
            "Платёж прошёл успешно — средства будут зачислены.\n\n"
            "Если кредиты не появились в течение 5 минут,\n"
            "обратитесь в поддержку: @TZshnik_support_bot"
        )


# ============================================================
# ИСТОРИЯ ПЛАТЕЖЕЙ
# ============================================================

@router.callback_query(F.data == "payment_history")
async def callback_payment_history(
    callback: CallbackQuery,
    user: User,
) -> None:
    """Показать историю платежей."""
    await callback.answer()
    
    # Получаем последние платежи
    payments = user.payments[-10:] if user.payments else []
    
    if not payments:
        text = (
            "📋 <b>История покупок</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤷 У вас пока нет покупок\n\n"
            "Купите пакет кредитов, чтобы\n"
            "начать генерировать ТЗ!"
        )
    else:
        text = (
            "📋 <b>История покупок</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        for p in reversed(payments):
            date_str = p.created_at.strftime("%d.%m.%Y")
            amount_rub = p.amount // 100  # Из копеек в рубли
            credits_text = f"+{p.credits_added} кредитов" if p.credits_added > 0 else "Безлимит"
            
            text += (
                f"📅 {date_str}\n"
                f"   💳 {format_number(amount_rub)}₽ — {credits_text}\n\n"
            )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Пополнить", callback_data="show_packages")
    builder.button(text="⬅️ К балансу", callback_data="show_balance")
    builder.adjust(2)
    
    if callback.message:
        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )


# ============================================================
# ОТМЕНА
# ============================================================

@router.callback_query(F.data == "cancel_payment")
async def callback_cancel_payment(callback: CallbackQuery) -> None:
    """Отмена выбора пакета."""
    await callback.answer("Отменено")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Посмотреть пакеты", callback_data="show_packages")
    builder.button(text="📖 В меню", callback_data="show_main_menu")
    builder.adjust(2)
    
    if callback.message:
        await callback.message.edit_text(
            "❌ <b>Покупка отменена</b>\n\n"
            "Вы можете вернуться к выбору пакетов\n"
            "в любое время.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
