"""
Клавиатуры для админ-панели.

Содержит все Inline-клавиатуры для:
- Главного меню админ-панели
- Управления пользователями
- Просмотра генераций и платежей
- Настроек и аналитики
"""

from typing import List, Optional, Dict, Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ============================================================
# КАТЕГОРИИ (для отображения)
# ============================================================

CATEGORY_NAMES = {
    "clothes": "👕 Одежда",
    "electronics": "📱 Электроника",
    "cosmetics": "💄 Косметика",
    "home": "🏠 Дом",
    "kids": "👶 Детям",
    "sports": "⚽ Спорт",
    "other": "📦 Другое",
}


# ============================================================
# ИДЕИ (статусы)
# ============================================================

IDEA_STATUS_NAMES = {
    "new": "🆕 Новые",
    "approved": "✅ Одобрены",
    "rejected": "❌ Отклонены",
}


# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
        InlineKeyboardButton(text="💬 Поддержка", callback_data="admin:support"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Генерации", callback_data="admin:generations"),
        InlineKeyboardButton(text="💳 Платежи", callback_data="admin:payments"),
    )
    builder.row(
        InlineKeyboardButton(text="💡 Идеи", callback_data="admin:ideas"),
        InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics"),
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Настройки", callback_data="admin:settings"),
        InlineKeyboardButton(text="📋 Логи", callback_data="admin:logs"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:refresh"),
    )

    return builder.as_markup()


# ============================================================
# ИДЕИ
# ============================================================

def get_ideas_list_keyboard(
    ideas: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    sort_by: str = "created_at",
    status_filter: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура списка идей с пагинацией и сортировкой.
    """
    builder = InlineKeyboardBuilder()
    
    status_emoji = {
        "new": "🆕",
        "approved": "✅",
        "rejected": "❌",
    }
    
    for idea in ideas:
        username = idea.get("username") or "Аноним"
        idea_id = idea.get("id")
        status = idea.get("status", "new")
        emoji = status_emoji.get(status, "📝")
        
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} @{username} | ID {idea_id}",
                callback_data=f"admin:idea:{idea_id}",
            )
        )
    
    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:ideas_page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin:ideas_info")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:ideas_page:{page+1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Фильтр по статусу
    builder.row(
        InlineKeyboardButton(
            text="🆕 Новые" + (" ✓" if status_filter == "new" else ""),
            callback_data="admin:ideas_status:new",
        ),
        InlineKeyboardButton(
            text="✅ Одобр" + (" ✓" if status_filter == "approved" else ""),
            callback_data="admin:ideas_status:approved",
        ),
        InlineKeyboardButton(
            text="❌ Откл" + (" ✓" if status_filter == "rejected" else ""),
            callback_data="admin:ideas_status:rejected",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Все" + (" ✓" if not status_filter else ""),
            callback_data="admin:ideas_status:all",
        ),
    )
    
    # Сортировка
    builder.row(
        InlineKeyboardButton(
            text="📅 По дате" + (" ✓" if sort_by == "created_at" else ""),
            callback_data="admin:ideas_sort:created_at",
        ),
        InlineKeyboardButton(
            text="🧾 По статусу" + (" ✓" if sort_by == "status" else ""),
            callback_data="admin:ideas_sort:status",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🎁 По награде" + (" ✓" if sort_by == "reward_credits" else ""),
            callback_data="admin:ideas_sort:reward_credits",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_idea_card_keyboard(
    idea_id: int,
    status: str,
) -> InlineKeyboardMarkup:
    """
    Клавиатура карточки идеи.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Одобрить (+2)",
            callback_data=f"admin:idea_approve:{idea_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"admin:idea_reject:{idea_id}",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ К списку", callback_data="admin:ideas"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_admin_back_keyboard(section: str = "main") -> InlineKeyboardMarkup:
    """Кнопка возврата в нужный раздел."""
    builder = InlineKeyboardBuilder()
    
    if section == "main":
        builder.row(
            InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:{section}"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin:main"),
        )
    
    return builder.as_markup()


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def get_users_list_keyboard(
    users: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    sort_by: str = "created_at",
) -> InlineKeyboardMarkup:
    """
    Клавиатура списка пользователей с пагинацией.
    
    Args:
        users: Список пользователей
        page: Текущая страница
        total_pages: Всего страниц
        sort_by: Поле сортировки
    """
    builder = InlineKeyboardBuilder()
    
    # Пользователи
    for user in users:
        username = user.get("username") or "Без имени"
        balance = user.get("balance", 0)
        telegram_id = user.get("telegram_id")
        
        builder.row(
            InlineKeyboardButton(
                text=f"👤 @{username} | 💰 {balance}",
                callback_data=f"admin:user:{telegram_id}",
            )
        )
    
    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:users_page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin:users_info")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:users_page:{page+1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Сортировка
    builder.row(
        InlineKeyboardButton(
            text="📅 По дате" + (" ✓" if sort_by == "created_at" else ""),
            callback_data="admin:users_sort:created_at",
        ),
        InlineKeyboardButton(
            text="💰 По балансу" + (" ✓" if sort_by == "balance" else ""),
            callback_data="admin:users_sort:balance",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📝 По генерациям" + (" ✓" if sort_by == "total_generated" else ""),
            callback_data="admin:users_sort:total_generated",
        ),
        InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:users_search"),
    )
    
    # Назад
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_user_card_keyboard(
    telegram_id: int,
    is_blocked: bool = False,
) -> InlineKeyboardMarkup:
    """
    Клавиатура карточки пользователя.
    
    Args:
        telegram_id: Telegram ID пользователя
        is_blocked: Заблокирован ли пользователь
    """
    builder = InlineKeyboardBuilder()
    
    # Управление балансом
    builder.row(
        InlineKeyboardButton(
            text="➕ Начислить",
            callback_data=f"admin:credit_add:{telegram_id}",
        ),
        InlineKeyboardButton(
            text="➖ Списать",
            callback_data=f"admin:credit_remove:{telegram_id}",
        ),
    )
    
    # Блокировка
    if is_blocked:
        builder.row(
            InlineKeyboardButton(
                text="✅ Разблокировать",
                callback_data=f"admin:unblock:{telegram_id}",
            ),
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="🚫 Заблокировать",
                callback_data=f"admin:block:{telegram_id}",
            ),
        )
    
    # Дополнительные действия
    builder.row(
        InlineKeyboardButton(
            text="📝 Генерации",
            callback_data=f"admin:user_generations:{telegram_id}",
        ),
        InlineKeyboardButton(
            text="💳 Платежи",
            callback_data=f"admin:user_payments:{telegram_id}",
        ),
    )

    # Безлимит
    builder.row(
        InlineKeyboardButton(
            text="♾ Безлимит",
            callback_data=f"admin:unlimited:{telegram_id}",
        ),
    )
    
    # Назад
    builder.row(
        InlineKeyboardButton(text="⬅️ К списку", callback_data="admin:users"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_unlimited_manage_keyboard(
    telegram_id: int,
    is_active: bool = False,
) -> InlineKeyboardMarkup:
    """Клавиатура управления безлимитом."""
    builder = InlineKeyboardBuilder()

    durations = [7, 30, 90, 180, 365]
    label_prefix = "⏳ +" if is_active else "♾ "

    for days in durations:
        builder.button(
            text=f"{label_prefix}{days}д",
            callback_data=f"admin:unlimited_grant:{telegram_id}:{days}",
        )

    builder.adjust(3)

    builder.row(
        InlineKeyboardButton(
            text="🛑 Забрать",
            callback_data=f"admin:unlimited_revoke:{telegram_id}",
        ),
    )

    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:user:{telegram_id}"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )

    return builder.as_markup()


def get_credit_amount_keyboard(
    telegram_id: int,
    action: str,
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора количества кредитов.
    
    Args:
        telegram_id: Telegram ID пользователя
        action: Тип действия (add/remove)
    """
    builder = InlineKeyboardBuilder()
    
    amounts = [1, 5, 10, 20, 50, 100]
    
    for amount in amounts:
        builder.button(
            text=f"{amount} 💎",
            callback_data=f"admin:credit_{action}_confirm:{telegram_id}:{amount}",
        )
    
    builder.adjust(3)
    
    builder.row(
        InlineKeyboardButton(
            text="✏️ Другое количество",
            callback_data=f"admin:credit_{action}_custom:{telegram_id}",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:user:{telegram_id}"),
    )
    
    return builder.as_markup()


def get_confirm_action_keyboard(
    action: str,
    telegram_id: int,
    extra_data: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения критического действия.
    
    Args:
        action: Тип действия
        telegram_id: Telegram ID пользователя
        extra_data: Дополнительные данные
    """
    builder = InlineKeyboardBuilder()
    
    confirm_data = f"admin:{action}_yes:{telegram_id}"
    cancel_data = f"admin:user:{telegram_id}"
    
    if extra_data:
        confirm_data += f":{extra_data}"
    
    builder.row(
        InlineKeyboardButton(text="✅ Да, подтверждаю", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data),
    )
    
    return builder.as_markup()


# ============================================================
# ГЕНЕРАЦИИ
# ============================================================

def get_generations_list_keyboard(
    generations: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    category_filter: Optional[str] = None,
    date_filter: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура списка генераций с пагинацией.
    
    Args:
        generations: Список генераций
        page: Текущая страница
        total_pages: Всего страниц
        category_filter: Фильтр по категории
        date_filter: Фильтр по дате (today, week, month)
    """
    builder = InlineKeyboardBuilder()
    
    # Генерации
    for gen in generations:
        username = gen.get("username") or "Аноним"
        category = CATEGORY_NAMES.get(gen.get("category", ""), gen.get("category", ""))
        score = gen.get("quality_score") or 0
        gen_id = gen.get("id")
        
        builder.row(
            InlineKeyboardButton(
                text=f"📷 @{username} | {category} | ⭐ {score}%",
                callback_data=f"admin:generation:{gen_id}",
            )
        )
    
    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:generations_page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin:gen_info")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:generations_page:{page+1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Фильтры по категории
    builder.row(
        InlineKeyboardButton(
            text="🏷 Категория" + (f" ({category_filter})" if category_filter else ""),
            callback_data="admin:gen_filter_category",
        ),
        InlineKeyboardButton(
            text="📅 Дата" + (f" ({date_filter})" if date_filter else ""),
            callback_data="admin:gen_filter_date",
        ),
    )
    
    # Назад
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_generation_card_keyboard(
    generation_id: int,
    has_photos: bool = True,
) -> InlineKeyboardMarkup:
    """
    Клавиатура карточки генерации.
    
    Args:
        generation_id: ID генерации
        has_photos: Есть ли фотографии
    """
    builder = InlineKeyboardBuilder()
    
    if has_photos:
        builder.row(
            InlineKeyboardButton(
                text="🖼 Показать фото",
                callback_data=f"admin:gen_photos:{generation_id}",
            ),
        )
    
    builder.row(
        InlineKeyboardButton(
            text="📄 Полный текст ТЗ",
            callback_data=f"admin:gen_full_tz:{generation_id}",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📝 Полный анализ",
            callback_data=f"admin:gen_full_analysis:{generation_id}",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Удалить",
            callback_data=f"admin:gen_delete:{generation_id}",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ К списку", callback_data="admin:generations"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_category_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора категории для фильтра."""
    builder = InlineKeyboardBuilder()
    
    for key, name in CATEGORY_NAMES.items():
        builder.button(
            text=name,
            callback_data=f"admin:gen_category:{key}",
        )
    
    builder.adjust(2)
    
    builder.row(
        InlineKeyboardButton(text="🔄 Сбросить фильтр", callback_data="admin:gen_category:all"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:generations"),
    )
    
    return builder.as_markup()


def get_date_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора периода для фильтра."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="admin:gen_date:today"),
        InlineKeyboardButton(text="📆 Неделя", callback_data="admin:gen_date:week"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓 Месяц", callback_data="admin:gen_date:month"),
        InlineKeyboardButton(text="🔄 Все время", callback_data="admin:gen_date:all"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:generations"),
    )
    
    return builder.as_markup()


# ============================================================
# ПЛАТЕЖИ
# ============================================================

def get_payments_list_keyboard(
    payments: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    status_filter: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура списка платежей с пагинацией.
    
    Args:
        payments: Список платежей
        page: Текущая страница
        total_pages: Всего страниц
        status_filter: Фильтр по статусу
    """
    builder = InlineKeyboardBuilder()
    
    status_icons = {
        "completed": "✅",
        "pending": "⏳",
        "failed": "❌",
        "refunded": "🔄",
    }
    
    # Платежи
    for payment in payments:
        username = payment.get("username") or "Аноним"
        amount = payment.get("amount", 0) / 100
        status = payment.get("status", "completed")
        icon = status_icons.get(status, "❓")
        payment_id = payment.get("id")
        
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {amount:.0f}₽ | @{username}",
                callback_data=f"admin:payment:{payment_id}",
            )
        )
    
    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:payments_page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin:pay_info")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:payments_page:{page+1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Фильтр по статусу
    builder.row(
        InlineKeyboardButton(
            text="✅" + (" Успешные ✓" if status_filter == "completed" else " Успешные"),
            callback_data="admin:pay_status:completed",
        ),
        InlineKeyboardButton(
            text="⏳" + (" Ожидание ✓" if status_filter == "pending" else " Ожидание"),
            callback_data="admin:pay_status:pending",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="❌" + (" Неудачные ✓" if status_filter == "failed" else " Неудачные"),
            callback_data="admin:pay_status:failed",
        ),
        InlineKeyboardButton(text="🔄 Все", callback_data="admin:pay_status:all"),
    )
    
    # Назад
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_payment_card_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """Клавиатура карточки платежа."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="⬅️ К списку", callback_data="admin:payments"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


# ============================================================
# АНАЛИТИКА
# ============================================================

def get_analytics_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура раздела аналитики."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📈 Регистрации", callback_data="admin:analytics_registrations"),
        InlineKeyboardButton(text="💰 Доходы", callback_data="admin:analytics_revenue"),
    )
    builder.row(
        InlineKeyboardButton(text="🏷 Категории", callback_data="admin:analytics_categories"),
        InlineKeyboardButton(text="🔄 Конверсия", callback_data="admin:analytics_conversion"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_analytics_period_keyboard(section: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора периода для аналитики."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="7 дней", callback_data=f"admin:analytics_{section}:7"),
        InlineKeyboardButton(text="30 дней", callback_data=f"admin:analytics_{section}:30"),
    )
    builder.row(
        InlineKeyboardButton(text="90 дней", callback_data=f"admin:analytics_{section}:90"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Аналитика", callback_data="admin:analytics"),
    )
    
    return builder.as_markup()


# ============================================================
# НАСТРОЙКИ
# ============================================================

def get_settings_keyboard(
    maintenance_mode: bool = False,
    free_generations_enabled: bool = True,
) -> InlineKeyboardMarkup:
    """
    Клавиатура раздела настроек.
    
    Args:
        maintenance_mode: Включен ли режим обслуживания
        free_generations_enabled: Включены ли бесплатные генерации
    """
    builder = InlineKeyboardBuilder()
    
    # Режим обслуживания
    builder.row(
        InlineKeyboardButton(
            text=f"🔧 Режим обслуживания: {'✅ ВКЛ' if maintenance_mode else '❌ ВЫКЛ'}",
            callback_data="admin:setting_maintenance",
        ),
    )
    
    # Бесплатные генерации
    builder.row(
        InlineKeyboardButton(
            text=f"🎁 Бесплатные генерации: {'✅ ВКЛ' if free_generations_enabled else '❌ ВЫКЛ'}",
            callback_data="admin:setting_free_gen",
        ),
    )
    
    # Количество бесплатных кредитов
    builder.row(
        InlineKeyboardButton(
            text="💎 Бесплатных кредитов: ...",
            callback_data="admin:setting_free_credits",
        ),
    )
    
    # AI провайдеры
    builder.row(
        InlineKeyboardButton(
            text="🤖 Проверить AI провайдеров",
            callback_data="admin:check_ai",
        ),
    )
    
    # Очистка статистики прибыли
    builder.row(
        InlineKeyboardButton(
            text="🗑 Сбросить статистику прибыли",
            callback_data="admin:reset_revenue_stats",
        ),
    )
    
    # Назад
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_free_credits_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора количества бесплатных кредитов."""
    builder = InlineKeyboardBuilder()
    
    for amount in [0, 1, 2, 3, 5]:
        builder.button(
            text=f"{amount} 💎",
            callback_data=f"admin:set_free_credits:{amount}",
        )
    
    builder.adjust(3)
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Настройки", callback_data="admin:settings"),
    )
    
    return builder.as_markup()


# ============================================================
# ЛОГИ
# ============================================================

def get_logs_keyboard(
    level_filter: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура раздела логов.
    
    Args:
        level_filter: Фильтр по уровню (ERROR, WARNING, INFO)
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="⚠️ Errors" + (" ✓" if level_filter == "ERROR" else ""),
            callback_data="admin:logs_level:ERROR",
        ),
        InlineKeyboardButton(
            text="⚡ Warnings" + (" ✓" if level_filter == "WARNING" else ""),
            callback_data="admin:logs_level:WARNING",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="ℹ️ Info" + (" ✓" if level_filter == "INFO" else ""),
            callback_data="admin:logs_level:INFO",
        ),
        InlineKeyboardButton(text="🔄 Все", callback_data="admin:logs_level:all"),
    )
    builder.row(
        InlineKeyboardButton(text="📜 Действия админов", callback_data="admin:admin_actions"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:logs"),
        InlineKeyboardButton(text="⬅️ Меню", callback_data="admin:main"),
    )
    
    return builder.as_markup()


def get_admin_actions_keyboard(
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Клавиатура списка действий администраторов."""
    builder = InlineKeyboardBuilder()
    
    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:actions_page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin:actions_info")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:actions_page:{page+1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Логи", callback_data="admin:logs"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )

    return builder.as_markup()


# ============================================================
# ПОДДЕРЖКА
# ============================================================

def get_support_tickets_keyboard(
    tickets: List,
    page: int = 1,
    total_pages: int = 1,
    status_filter: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура списка тикетов поддержки.

    Args:
        tickets: Список тикетов
        page: Текущая страница
        total_pages: Всего страниц
        status_filter: Фильтр по статусу
    """
    builder = InlineKeyboardBuilder()

    status_emoji = {
        "open": "🆕",
        "in_progress": "⏳",
        "resolved": "✅",
        "archived": "📁",
    }

    priority_emoji = {
        "low": "",
        "medium": "🟡",
        "high": "🔴",
    }

    category_names = {
        "payment": "💳",
        "technical": "🔧",
        "other": "❓",
    }

    for ticket in tickets:
        username = ticket.user.username if ticket.user else "Без имени"
        status = status_emoji.get(ticket.status, "❓")
        priority = priority_emoji.get(ticket.priority, "")
        category = category_names.get(ticket.category, "❓")
        important = "❗" if ticket.is_important else ""

        builder.row(
            InlineKeyboardButton(
                text=f"{status} #{ticket.id} | @{username} {category} {priority} {important}",
                callback_data=f"admin:support_ticket:{ticket.id}",
            )
        )

    # Пагинация
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin:support_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin:support_info")
        )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin:support_page:{page+1}")
            )

        if nav_buttons:
            builder.row(*nav_buttons)

    # Фильтры по статусу
    builder.row(
        InlineKeyboardButton(
            text="🆕 Открытые" + (" ✓" if status_filter == "open" else ""),
            callback_data="admin:support_filter:open",
        ),
        InlineKeyboardButton(
            text="⏳ В работе" + (" ✓" if status_filter == "in_progress" else ""),
            callback_data="admin:support_filter:in_progress",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Решённые" + (" ✓" if status_filter == "resolved" else ""),
            callback_data="admin:support_filter:resolved",
        ),
        InlineKeyboardButton(
            text="🔄 Все" + (" ✓" if status_filter is None else ""),
            callback_data="admin:support_filter:all",
        ),
    )

    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin:main"),
    )

    return builder.as_markup()


def get_support_ticket_detail_keyboard(ticket) -> InlineKeyboardMarkup:
    """
    Клавиатура детального просмотра тикета.

    Args:
        ticket: Объект SupportTicket
    """
    builder = InlineKeyboardBuilder()

    # Кнопка ответа
    builder.row(
        InlineKeyboardButton(
            text="✍️ Ответить",
            callback_data=f"admin:support_reply:{ticket.id}",
        ),
    )

    # Управление статусом
    if ticket.status == "open":
        builder.row(
            InlineKeyboardButton(
                text="⏳ Взять в работу",
                callback_data=f"admin:support_take:{ticket.id}",
            ),
        )
    elif ticket.status == "in_progress":
        builder.row(
            InlineKeyboardButton(
                text="✅ Решить",
                callback_data=f"admin:support_resolve:{ticket.id}",
            ),
        )

    # Важность
    if not ticket.is_important:
        builder.row(
            InlineKeyboardButton(
                text="⭐ Отметить важным",
                callback_data=f"admin:support_important:{ticket.id}",
            ),
        )

    # Архивирование/удаление
    if ticket.status in ["resolved", "archived"]:
        if ticket.status != "archived":
            builder.row(
                InlineKeyboardButton(
                    text="📁 Архивировать",
                    callback_data=f"admin:support_archive:{ticket.id}",
                ),
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Разархивировать",
                    callback_data=f"admin:support_reopen:{ticket.id}",
                ),
            )

    if ticket.status == "resolved":
        builder.row(
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"admin:support_delete:{ticket.id}",
            ),
        )

    builder.row(
        InlineKeyboardButton(text="⬅️ К списку", callback_data="admin:support"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
    )

    return builder.as_markup()


def get_cancel_reply_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Клавиатура отмены ответа."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:support_ticket:{ticket_id}"),
    )

    return builder.as_markup()

