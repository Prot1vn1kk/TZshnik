"""
Единый модуль для меню покупки пакетов с блокировкой повторной подписки.

Обеспечивает:
- Единое меню пакетов для /buy и callback_show_packages
- Блокировку покупки кредитов при активном безлимите
- Блокировку повторного продления безлимита (за 7 дней до окончания)
- Профессиональный UX как в крупных Telegram ботах
"""

import math
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import is_unlimited_active
from database.models import User
from config.packages import (
    get_package,
    get_packages_by_category,
    get_unlimited_packages,
)


# ============================================================
# КОНСТАНТЫ
# ============================================================

MIN_DAYS_LEFT_FOR_RENEWAL = 7  # За сколько дней до окончания разрешено продление


# ============================================================
# СТАТУС БЕЗЛИМИТНОЙ ПОДПИСКИ
# ============================================================

def get_unlimited_status_text(user: User) -> dict:
    """
    Получить детальный статус безлимитной подписки.

    Returns:
        dict с ключами:
        - is_active: bool - активна ли подписка
        - days_left: int - дней осталось (0 если не активна)
        - can_renew: bool - можно ли продлить (осталось <= 7 дней)
        - until_date: datetime или None - дата окончания
        - until_formatted: str - отформатированная дата окончания
    """
    if not is_unlimited_active(user):
        return {
            "is_active": False,
            "days_left": 0,
            "can_renew": False,
            "until_date": None,
            "until_formatted": "",
        }

    now = datetime.utcnow()
    until = user.unlimited_until

    if not until:
        return {
            "is_active": False,
            "days_left": 0,
            "can_renew": False,
            "until_date": None,
            "until_formatted": "",
        }

    delta = until - now
    days_left = max(0, math.ceil(delta.total_seconds() / 86400))

    # Форматируем дату окончания
    until_formatted = until.strftime("%d.%m.%Y")

    return {
        "is_active": True,
        "days_left": days_left,
        "can_renew": days_left <= MIN_DAYS_LEFT_FOR_RENEWAL,
        "until_date": until,
        "until_formatted": until_formatted,
    }


def _format_number(num: int) -> str:
    """Форматирование числа с пробелами (1000 -> 1 000)."""
    return f"{num:,}".replace(",", " ")


# ============================================================
# ТЕКСТ МЕНЮ
# ============================================================

def build_packages_menu_text(user: User) -> str:
    """
    Построить текст меню пакетов с учётом статуса подписки.

    Args:
        user: Пользователь

    Returns:
        Текст сообщения для меню пакетов
    """
    unlimited_status = get_unlimited_status_text(user)

    # Заголовок
    text = (
        "💳 <b>Пополнение баланса</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Если активен безлимит
    if unlimited_status["is_active"]:
        days_left = unlimited_status["days_left"]
        until_formatted = unlimited_status["until_formatted"]

        text += (
            f"👑 <b>Безлимит активен</b>\n"
            f"   До {until_formatted} ({days_left} дн.)\n\n"
        )

        # Информационный блок
        if unlimited_status["can_renew"]:
            text += (
                "📦 <b>Безлимит можно продлить!</b>\n\n"
                f"У вас осталось менее {MIN_DAYS_LEFT_FOR_RENEWAL} дней. "
                "Вы можете продлить подписку, чтобы не прерывать доступ.\n\n"
            )
        else:
            text += (
                "📦 <b>У вас активен безлимит!</b>\n\n"
                "Вы можете генерировать ТЗ без ограничений.\n"
                f"Продление доступно когда осталось меньше {MIN_DAYS_LEFT_FOR_RENEWAL} дней.\n\n"
            )
    else:
        # Текущий баланс (если безлимит не активен)
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

    return text


def get_package_blocked_message(package_id: str, user: User) -> str | None:
    """
    Получить сообщение о блокировке покупки пакета.

    Args:
        package_id: ID пакета
        user: Пользователь

    Returns:
        Сообщение о блокировке или None если блокировки нет
    """
    package = get_package(package_id)

    if not package:
        return "⚠️ Пакет не найден"

    unlimited_status = get_unlimited_status_text(user)

    # Если безлимит не активен - блокировки нет
    if not unlimited_status["is_active"]:
        return None

    # Блокируем покупку кредитов при активном безлимите
    if not package.is_unlimited:
        return (
            "⚠️ <b>Покупка кредитов недоступна</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"

            "👑 У вас активна безлимитная подписка!\n"
            "Покупка кредитов не имеет смысла — "
            "вы можете генерировать ТЗ без ограничений.\n\n"
            f"Осталось дней: {unlimited_status['days_left']}\n\n"
            "Если вы хотите продлить подписку, "
            f"нажмите кнопку «Продлить» ниже (когда останется ≤ {MIN_DAYS_LEFT_FOR_RENEWAL} дней)."
        )

    # Блокируем раннее продление безлимита
    if package.is_unlimited and not unlimited_status["can_renew"]:
        days_left = unlimited_status["days_left"]
        return (
            "⚠️ <b>Продление недоступно</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👑 Ваша безлимитная подписка ещё активна!\n"
            f"Осталось {days_left} дней.\n\n"

            f"Продление доступно за {MIN_DAYS_LEFT_FOR_RENEWAL} дней до окончания. "
            "Это нужно для того, чтобы вы не потеряли дни текущей подписки.\n\n"
            f"Попробуйте продлить через {days_left - MIN_DAYS_LEFT_FOR_RENEWAL} дней."
        )

    return None


# ============================================================
# КЛАВИАТУРА
# ============================================================

def build_packages_keyboard(user: User, show_back: bool = True) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру пакетов с учётом статуса подписки.

    Args:
        user: Пользователь
        show_back: Показывать кнопку "Назад"

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()
    unlimited_status = get_unlimited_status_text(user)

    # Если активен безлимит
    if unlimited_status["is_active"]:
        # Кнопка информации о подписке
        builder.button(
            text="ℹ️ Безлимит активен",
            callback_data="unlimited_info",
        )

        # Кнопка справки
        builder.button(
            text="❓ Как это работает",
            callback_data="packages_help",
        )

        # Если можно продлить - показываем кнопку продления
        if unlimited_status["can_renew"]:
            unlimited_packages = get_unlimited_packages()
            if unlimited_packages:
                pkg = unlimited_packages[0]
                builder.button(
                    text=f"🔄 Продлить на {pkg.duration_days} дней • {_format_number(pkg.price_rub)}₽",
                    callback_data=f"buy:{pkg.id}",
                )

        # Кнопка назад
        if show_back:
            builder.button(
                text="⬅️ В меню",
                callback_data="show_main_menu",
            )

        # Раскладка: 2 в ряд, потом 1 или 2
        if unlimited_status["can_renew"]:
            builder.adjust(2, 1, 1)  # info+help, renew, back
        else:
            builder.adjust(2, 1)  # info+help, back

    else:
        # Обычное меню с пакетами

        # Стартовые пакеты (3 в ряд)
        starter_packages = get_packages_by_category("starter")
        for pkg in starter_packages:
            savings_text = f" (-{pkg.savings_percent}%)" if pkg.savings_percent > 0 else ""
            builder.button(
                text=f"{pkg.emoji} {pkg.credits} ТЗ • {pkg.price_rub}₽{savings_text}",
                callback_data=f"buy:{pkg.id}",
            )

        # Популярные пакеты (2 в ряд)
        popular_packages = get_packages_by_category("popular")
        for pkg in popular_packages:
            badge = "🔥 " if pkg.is_popular else ""
            savings_text = f" (-{pkg.savings_percent}%)" if pkg.savings_percent > 0 else ""
            builder.button(
                text=f"{badge}{pkg.emoji} {pkg.credits} ТЗ • {pkg.price_rub}₽{savings_text}",
                callback_data=f"buy:{pkg.id}",
            )

        # Бизнес пакеты (2 в ряд)
        business_packages = get_packages_by_category("business")
        for pkg in business_packages:
            badge = "💎 " if pkg.is_best_value else ""
            savings_text = f" (-{pkg.savings_percent}%)" if pkg.savings_percent > 0 else ""
            builder.button(
                text=f"{badge}{pkg.emoji} {pkg.credits} ТЗ • {_format_number(pkg.price_rub)}₽{savings_text}",
                callback_data=f"buy:{pkg.id}",
            )

        # Безлимитный тариф (отдельно)
        unlimited_packages = get_unlimited_packages()
        if unlimited_packages:
            pkg = unlimited_packages[0]
            builder.button(
                text=f"👑 БЕЗЛИМИТ {pkg.duration_days} дней • {_format_number(pkg.price_rub)}₽",
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

        # Раскладка: 3-2-2-1-1/2
        builder.adjust(3, 2, 2, 1, 2 if show_back else 1)

    return builder.as_markup()


def build_unlimited_info_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для детальной информации о безлимите.

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="⬅️ К пакетам",
        callback_data="show_packages",
    )

    builder.button(
        text="❌ Отмена",
        callback_data="cancel_payment",
    )

    builder.adjust(2)
    return builder.as_markup()
