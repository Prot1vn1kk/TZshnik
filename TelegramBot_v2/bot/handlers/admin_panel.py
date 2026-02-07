"""
Обработчики админ-панели.

Полнофункциональная админ-панель для управления ботом:
- Дашборд со статистикой
- Управление пользователями
- Просмотр генераций и платежей
- Аналитика
- Настройки бота
- Логи и мониторинг

Доступ только для telegram_id из ADMIN_IDS.
"""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.keyboards.admin_keyboards import (
    CATEGORY_NAMES,
    IDEA_STATUS_NAMES,
    get_admin_actions_keyboard,
    get_admin_back_keyboard,
    get_admin_main_keyboard,
    get_analytics_keyboard,
    get_analytics_period_keyboard,
    get_category_filter_keyboard,
    get_confirm_action_keyboard,
    get_credit_amount_keyboard,
    get_date_filter_keyboard,
    get_free_credits_keyboard,
    get_generation_card_keyboard,
    get_generations_list_keyboard,
    get_idea_card_keyboard,
    get_ideas_list_keyboard,
    get_logs_keyboard,
    get_payment_card_keyboard,
    get_payments_list_keyboard,
    get_settings_keyboard,
    get_user_card_keyboard,
    get_users_list_keyboard,
    get_unlimited_manage_keyboard,
)
from bot.states import AdminStates
from database.admin_crud import (
    admin_add_credits,
    admin_block_user,
    admin_delete_generation,
    admin_remove_credits,
    admin_approve_idea,
    admin_reject_idea,
    admin_unblock_user,
    admin_grant_unlimited,
    admin_revoke_unlimited,
    get_admin_actions,
    get_bot_setting,
    get_category_stats,
    get_conversion_stats,
    get_dashboard_stats,
    get_idea_full_info,
    get_ideas_paginated,
    get_generation_full_info,
    get_generations_paginated,
    get_payments_paginated,
    get_registration_stats,
    get_revenue_by_period,
    get_user_full_info,
    get_users_paginated,
    log_admin_action,
    set_bot_setting,
)


logger = structlog.get_logger()
router = Router(name="admin")

# Количество элементов на странице
ITEMS_PER_PAGE = 10


# ============================================================
# ФИЛЬТР АДМИНА
# ============================================================

def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь администратором."""
    admin_ids = settings.admin_ids
    return user_id in admin_ids


class AdminFilter:
    """Фильтр для проверки прав администратора."""
    
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return is_admin(message.from_user.id)


class AdminCallbackFilter:
    """Фильтр для проверки прав администратора в callback."""
    
    async def __call__(self, callback: CallbackQuery) -> bool:
        if not callback.from_user:
            return False
        return is_admin(callback.from_user.id)


def _build_dashboard_text(stats: Dict[str, Any]) -> str:
    """Построить текст дашборда из статистики."""
    top_cats = stats.get("top_categories", [])
    if top_cats:
        total_gens = sum(c["count"] for c in top_cats)
        if total_gens > 0:
            cats_text = "\n".join([
                f"   • {CATEGORY_NAMES.get(c['category'], c['category'])}: "
                f"{c['count']} ({c['count']/total_gens*100:.0f}%)"
                for c in top_cats[:5]
            ])
        else:
            cats_text = "\n".join([
                f"   • {CATEGORY_NAMES.get(c['category'], c['category'])}: 0"
                for c in top_cats[:5]
            ])
    else:
        cats_text = "   • Нет данных"

    return (
        "🔐 <b>АДМИН-ПАНЕЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"👥 <b>Пользователи:</b>\n"
        f"   • Всего: <b>{stats['total_users']}</b>\n"
        f"   • Активных (7 дн): <b>{stats['active_users_week']}</b>\n"
        f"   • Новых сегодня: <b>{stats['new_users_today']}</b>\n\n"

        f"💰 <b>Доход:</b>\n"
        f"   • Сегодня: <b>{stats['revenue_today']:.0f}₽</b>\n"
        f"   • За неделю: <b>{stats['revenue_week']:.0f}₽</b>\n"
        f"   • За месяц: <b>{stats['revenue_month']:.0f}₽</b>\n"
        f"   • Всего: <b>{stats['revenue_total']:.0f}₽</b>\n\n"

        f"📝 <b>Генерации:</b>\n"
        f"   • Всего: <b>{stats['total_generations']}</b>\n"
        f"   • Сегодня: <b>{stats['generations_today']}</b>\n"
        f"   • Среднее качество: <b>{stats['avg_quality_score']}%</b>\n\n"

        f"🔥 <b>Топ категорий:</b>\n{cats_text}\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )


# ============================================================
# КОМАНДА /ADMIN - ДАШБОРД
# ============================================================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    """
    Открыть админ-панель.
    
    Показывает дашборд со статистикой и главное меню.
    """
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return
    
    # Сбрасываем состояние
    await state.clear()
    
    try:
        stats = await get_dashboard_stats()
        
        text = _build_dashboard_text(stats)

        await message.answer(
            text,
            reply_markup=get_admin_main_keyboard(),
        )

        logger.info(
            "admin_panel_opened",
            admin_id=message.from_user.id,
        )

    except Exception as e:
        logger.error("admin_panel_error", error=str(e))
        await message.answer(
            "❌ Ошибка при загрузке админ-панели.",
            reply_markup=get_admin_main_keyboard(),
        )


# ============================================================
# CALLBACK: ГЛАВНОЕ МЕНЮ
# ============================================================

@router.callback_query(F.data == "admin:main")
async def callback_admin_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Вернуться в главное меню админ-панели."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()

    try:
        stats = await get_dashboard_stats()
        text = _build_dashboard_text(stats)

        await callback.message.edit_text(
            text,
            reply_markup=get_admin_main_keyboard(),
        )

    except Exception as e:
        logger.error("admin_main_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "admin:refresh")
async def callback_admin_refresh(callback: CallbackQuery, state: FSMContext) -> None:
    """Обновить данные дашборда."""
    await callback_admin_main(callback, state)


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

@router.callback_query(F.data == "admin:users")
async def callback_users_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать список пользователей."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    # Получаем параметры из состояния или по умолчанию
    data = await state.get_data()
    page = data.get("users_page", 1)
    sort_by = data.get("users_sort", "created_at")
    
    try:
        users, total = await get_users_paginated(
            page=page,
            per_page=ITEMS_PER_PAGE,
            sort_by=sort_by,
        )
        
        total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
        
        # Преобразуем пользователей в словари
        users_data = [
            {
                "telegram_id": u.telegram_id,
                "username": u.username,
                "balance": u.balance,
                "total_generated": u.total_generated,
            }
            for u in users
        ]
        
        text = (
            f"👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Всего: {total} | Страница {page}/{total_pages}\n\n"
            f"Выберите пользователя для управления:"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_users_list_keyboard(
                users=users_data,
                page=page,
                total_pages=total_pages,
                sort_by=sort_by,
            ),
        )
        
    except Exception as e:
        logger.error("users_list_error", error=str(e))
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users_page:"))
async def callback_users_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить страницу списка пользователей."""
    page = int(callback.data.split(":")[-1])
    await state.update_data(users_page=page)
    await callback_users_list(callback, state)


@router.callback_query(F.data.startswith("admin:users_sort:"))
async def callback_users_sort(callback: CallbackQuery, state: FSMContext) -> None:
    """Изменить сортировку пользователей."""
    sort_by = callback.data.split(":")[-1]
    await state.update_data(users_sort=sort_by, users_page=1)
    await callback_users_list(callback, state)


@router.callback_query(F.data == "admin:users_search")
async def callback_users_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать поиск пользователя."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.searching_user)
    
    text = (
        "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Введите telegram_id или @username пользователя:\n\n"
        "<i>Например: 123456789 или @username</i>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard("users"),
    )
    await callback.answer()


@router.message(AdminStates.searching_user)
async def handle_user_search(message: Message, state: FSMContext) -> None:
    """Обработка поиска пользователя."""
    if not message.from_user or not is_admin(message.from_user.id):
        return
    
    search_query = message.text.strip()
    
    try:
        users, total = await get_users_paginated(
            page=1,
            per_page=ITEMS_PER_PAGE,
            search=search_query,
        )
        
        if not users:
            await message.answer(
                f"❌ Пользователь не найден: <b>{search_query}</b>",
                reply_markup=get_admin_back_keyboard("users"),
            )
            return
        
        # Если найден один — показываем карточку
        if len(users) == 1:
            user = users[0]
            await state.clear()
            
            # Показываем карточку пользователя
            info = await get_user_full_info(user.telegram_id)
            if info:
                await show_user_card(message, info)
        else:
            # Показываем список найденных
            users_data = [
                {
                    "telegram_id": u.telegram_id,
                    "username": u.username,
                    "balance": u.balance,
                }
                for u in users
            ]
            
            text = (
                f"🔍 <b>Результаты поиска:</b> {search_query}\n"
                f"Найдено: {total}\n\n"
                f"Выберите пользователя:"
            )
            
            await message.answer(
                text,
                reply_markup=get_users_list_keyboard(
                    users=users_data,
                    page=1,
                    total_pages=1,
                    sort_by="created_at",
                ),
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error("user_search_error", error=str(e))
        await message.answer("❌ Ошибка поиска")


def build_user_card_text(info: Dict[str, Any]) -> str:
    """Сформировать текст карточки пользователя."""
    username = info.get("username") or "Без имени"
    first_name = info.get("first_name") or ""

    created_at = info.get("created_at")
    created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "Неизвестно"

    last_gen = info.get("last_generation")
    last_gen_str = last_gen.strftime("%d.%m.%Y %H:%M") if last_gen else "Нет"

    unlimited_until = info.get("unlimited_until")
    if info.get("is_unlimited") and unlimited_until:
        unlimited_str = f"Активен до {unlimited_until.strftime('%d.%m.%Y %H:%M')}"
    elif info.get("is_unlimited"):
        unlimited_str = "Активен"
    else:
        unlimited_str = "Нет"

    return (
        f"👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📛 <b>Имя:</b> {first_name}\n"
        f"👤 <b>Username:</b> @{username}\n"
        f"🆔 <b>Telegram ID:</b> <code>{info['telegram_id']}</code>\n\n"

        f"💰 <b>Баланс:</b> {info['balance']} кредитов\n"
        f"📝 <b>Всего ТЗ:</b> {info['total_generated']}\n"
        f"💳 <b>Платежей:</b> {info['payments_count']}\n"
        f"💵 <b>Всего оплачено:</b> {info['total_paid']:.0f}₽\n\n"

        f"📅 <b>Регистрация:</b> {created_str}\n"
        f"🕐 <b>Последняя генерация:</b> {last_gen_str}\n"
        f"⭐ <b>Премиум:</b> {'Да' if info.get('is_premium') else 'Нет'}\n"
        f"♾ <b>Безлимит:</b> {unlimited_str}"
    )


async def show_user_card(message: Message, info: Dict[str, Any]) -> None:
    """Показать карточку пользователя."""
    await message.answer(
        build_user_card_text(info),
        reply_markup=get_user_card_keyboard(
            telegram_id=info["telegram_id"],
            is_blocked=False,  # TODO: добавить проверку блокировки
        ),
    )


async def render_user_card_for_callback(
    callback: CallbackQuery,
    telegram_id: int,
) -> None:
    """Обновить карточку пользователя в callback сообщении."""
    info = await get_user_full_info(telegram_id)
    if not info:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    await callback.message.edit_text(
        build_user_card_text(info),
        reply_markup=get_user_card_keyboard(
            telegram_id=telegram_id,
            is_blocked=False,
        ),
    )


@router.callback_query(F.data.startswith("admin:user:"))
async def callback_user_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать карточку пользователя."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    try:
        info = await get_user_full_info(telegram_id)
        
        if not info:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        await render_user_card_for_callback(callback, telegram_id)
        
    except Exception as e:
        logger.error("user_card_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


# ============================================================
# УПРАВЛЕНИЕ КРЕДИТАМИ
# ============================================================

@router.callback_query(F.data.startswith("admin:credit_add:"))
async def callback_credit_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать начисление кредитов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    text = (
        "➕ <b>НАЧИСЛЕНИЕ КРЕДИТОВ</b>\n\n"
        f"Пользователь: <code>{telegram_id}</code>\n\n"
        "Выберите количество кредитов:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_credit_amount_keyboard(telegram_id, "add"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:credit_remove:"))
async def callback_credit_remove(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать списание кредитов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    text = (
        "➖ <b>СПИСАНИЕ КРЕДИТОВ</b>\n\n"
        f"Пользователь: <code>{telegram_id}</code>\n\n"
        "Выберите количество кредитов:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_credit_amount_keyboard(telegram_id, "remove"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:credit_add_confirm:"))
async def callback_credit_add_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтвердить начисление кредитов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    parts = callback.data.split(":")
    telegram_id = int(parts[-2])
    amount = int(parts[-1])
    
    try:
        success = await admin_add_credits(
            admin_id=callback.from_user.id,
            telegram_id=telegram_id,
            amount=amount,
            reason="Начисление через админ-панель",
        )
        
        if success:
            await callback.answer(f"✅ Начислено {amount} кредитов", show_alert=True)
            await render_user_card_for_callback(callback, telegram_id)
        else:
            await callback.answer("❌ Ошибка начисления", show_alert=True)
            
    except Exception as e:
        logger.error("credit_add_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:credit_remove_confirm:"))
async def callback_credit_remove_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтвердить списание кредитов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    parts = callback.data.split(":")
    telegram_id = int(parts[-2])
    amount = int(parts[-1])
    
    try:
        success = await admin_remove_credits(
            admin_id=callback.from_user.id,
            telegram_id=telegram_id,
            amount=amount,
            reason="Списание через админ-панель",
        )
        
        if success:
            await callback.answer(f"✅ Списано {amount} кредитов", show_alert=True)
            await render_user_card_for_callback(callback, telegram_id)
        else:
            await callback.answer("❌ Недостаточно кредитов", show_alert=True)
            
    except Exception as e:
        logger.error("credit_remove_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


# ============================================================
# БЛОКИРОВКА ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

@router.callback_query(F.data.startswith("admin:block:"))
async def callback_block_user(callback: CallbackQuery, state: FSMContext) -> None:
    """Запросить подтверждение блокировки."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    text = (
        "⚠️ <b>ПОДТВЕРЖДЕНИЕ БЛОКИРОВКИ</b>\n\n"
        f"Пользователь: <code>{telegram_id}</code>\n\n"
        "Вы уверены, что хотите заблокировать этого пользователя?"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_confirm_action_keyboard("block", telegram_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:block_yes:"))
async def callback_block_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтвердить блокировку."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    try:
        success = await admin_block_user(
            admin_id=callback.from_user.id,
            telegram_id=telegram_id,
            reason="Блокировка через админ-панель",
        )
        
        if success:
            await callback.answer("✅ Пользователь заблокирован", show_alert=True)
        else:
            await callback.answer("❌ Ошибка блокировки", show_alert=True)

        await render_user_card_for_callback(callback, telegram_id)
        
    except Exception as e:
        logger.error("block_user_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:unblock:"))
async def callback_unblock_user(callback: CallbackQuery, state: FSMContext) -> None:
    """Разблокировать пользователя."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    try:
        success = await admin_unblock_user(
            admin_id=callback.from_user.id,
            telegram_id=telegram_id,
        )
        
        if success:
            await callback.answer("✅ Пользователь разблокирован", show_alert=True)
        else:
            await callback.answer("❌ Ошибка", show_alert=True)

        await render_user_card_for_callback(callback, telegram_id)
        
    except Exception as e:
        logger.error("unblock_user_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


# ============================================================
# БЕЗЛИМИТ
# ============================================================

@router.callback_query(F.data.startswith("admin:unlimited:"))
async def callback_unlimited_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Открыть меню управления безлимитом."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[-1])

    try:
        info = await get_user_full_info(telegram_id)
        if not info:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        is_active = bool(info.get("is_unlimited"))
        unlimited_until = info.get("unlimited_until")
        if is_active and unlimited_until:
            status_text = f"Активен до {unlimited_until.strftime('%d.%m.%Y %H:%M')}"
        elif is_active:
            status_text = "Активен"
        else:
            status_text = "Не активен"

        text = (
            "♾ <b>БЕЗЛИМИТ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Пользователь: <code>{telegram_id}</code>\n"
            f"Статус: <b>{status_text}</b>\n\n"
            "Выберите срок для выдачи/продления или заберите безлимит."
        )

        await callback.message.edit_text(
            text,
            reply_markup=get_unlimited_manage_keyboard(
                telegram_id=telegram_id,
                is_active=is_active,
            ),
        )

    except Exception as e:
        logger.error("unlimited_menu_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("admin:unlimited_grant:"))
async def callback_unlimited_grant(callback: CallbackQuery, state: FSMContext) -> None:
    """Выдать/продлить безлимит."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    telegram_id = int(parts[-2])
    duration_days = int(parts[-1])

    try:
        new_until = await admin_grant_unlimited(
            admin_id=callback.from_user.id,
            telegram_id=telegram_id,
            duration_days=duration_days,
            reason="Управление безлимитом через админ-панель",
        )

        if new_until:
            until_str = new_until.strftime("%d.%m.%Y %H:%M")
            await callback.answer(
                f"✅ Безлимит до {until_str}",
                show_alert=True,
            )
            await render_user_card_for_callback(callback, telegram_id)
        else:
            await callback.answer("❌ Пользователь не найден", show_alert=True)

    except Exception as e:
        logger.error("unlimited_grant_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:unlimited_revoke:"))
async def callback_unlimited_revoke(callback: CallbackQuery, state: FSMContext) -> None:
    """Забрать безлимит."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[-1])

    try:
        success = await admin_revoke_unlimited(
            admin_id=callback.from_user.id,
            telegram_id=telegram_id,
            reason="Управление безлимитом через админ-панель",
        )

        if success:
            await callback.answer("✅ Безлимит снят", show_alert=True)
            await render_user_card_for_callback(callback, telegram_id)
        else:
            await callback.answer("❌ Пользователь не найден", show_alert=True)

    except Exception as e:
        logger.error("unlimited_revoke_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


# ============================================================
# ИДЕИ
# ============================================================

@router.callback_query(F.data == "admin:ideas")
async def callback_ideas_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать список идей."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    page = data.get("ideas_page", 1)
    sort_by = data.get("ideas_sort", "created_at")
    status_filter = data.get("ideas_status")
    
    try:
        ideas, total = await get_ideas_paginated(
            page=page,
            per_page=ITEMS_PER_PAGE,
            status=status_filter,
            sort_by=sort_by,
        )
        
        total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
        
        ideas_data = []
        for idea in ideas:
            ideas_data.append({
                "id": idea.id,
                "username": idea.user.username if idea.user else None,
                "status": idea.status,
                "reward_credits": idea.reward_credits,
                "created_at": idea.created_at,
            })
        
        status_text = IDEA_STATUS_NAMES.get(status_filter, "Все") if status_filter else "Все"
        
        text = (
            f"💡 <b>ИДЕИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Всего: {total} | Страница {page}/{total_pages}\n"
            f"Статус: {status_text} | Сортировка: {sort_by}\n\n"
            f"Выберите идею для просмотра:"
        )
        
        try:
            await callback.message.edit_text(
                text,
                reply_markup=get_ideas_list_keyboard(
                    ideas=ideas_data,
                    page=page,
                    total_pages=total_pages,
                    sort_by=sort_by,
                    status_filter=status_filter,
                ),
            )
        except Exception as edit_error:
            if "message is not modified" in str(edit_error).lower():
                await callback.answer()
                return
            raise
        
    except Exception as e:
        logger.error("ideas_list_error", error=str(e))
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ideas_page:"))
async def callback_ideas_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить страницу идей."""
    page = int(callback.data.split(":")[-1])
    await state.update_data(ideas_page=page)
    await callback_ideas_list(callback, state)


@router.callback_query(F.data.startswith("admin:ideas_sort:"))
async def callback_ideas_sort(callback: CallbackQuery, state: FSMContext) -> None:
    """Изменить сортировку идей."""
    sort_by = callback.data.split(":")[-1]
    await state.update_data(ideas_sort=sort_by, ideas_page=1)
    await callback_ideas_list(callback, state)


@router.callback_query(F.data.startswith("admin:ideas_status:"))
async def callback_ideas_status(callback: CallbackQuery, state: FSMContext) -> None:
    """Изменить фильтр статуса идей."""
    status = callback.data.split(":")[-1]
    if status == "all":
        await state.update_data(ideas_status=None, ideas_page=1)
    else:
        await state.update_data(ideas_status=status, ideas_page=1)
    await callback_ideas_list(callback, state)


@router.callback_query(F.data.startswith("admin:idea:"))
async def callback_idea_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать карточку идеи."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    idea_id = int(callback.data.split(":")[-1])
    
    try:
        info = await get_idea_full_info(idea_id)
        if not info:
            await callback.answer("❌ Идея не найдена", show_alert=True)
            return
        
        username = info.get("username") or "Аноним"
        created_at = info.get("created_at")
        created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "?"
        decided_at = info.get("decided_at")
        decided_str = decided_at.strftime("%d.%m.%Y %H:%M") if decided_at else "—"
        status = info.get("status", "new")
        status_name = IDEA_STATUS_NAMES.get(status, status)
        reward = info.get("reward_credits", 0)
        
        text = (
            f"💡 <b>ИДЕЯ #{info['id']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Пользователь:</b> @{username}\n"
            f"🆔 <b>Telegram ID:</b> <code>{info.get('user_telegram_id')}</code>\n\n"
            f"📌 <b>Статус:</b> {status_name}\n"
            f"🎁 <b>Награда:</b> {reward} кредитов\n"
            f"📅 <b>Создано:</b> {created_str}\n"
            f"✅ <b>Решение:</b> {decided_str}\n\n"
            f"💬 <b>Текст идеи:</b>\n{info.get('text')}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_idea_card_keyboard(idea_id=info["id"], status=status),
        )
        
    except Exception as e:
        logger.error("idea_card_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:idea_approve:"))
async def callback_idea_approve(callback: CallbackQuery, state: FSMContext) -> None:
    """Одобрить идею и начислить награду."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    idea_id = int(callback.data.split(":")[-1])
    
    result = await admin_approve_idea(
        admin_id=callback.from_user.id,
        idea_id=idea_id,
        reward_credits=2,
    )
    
    if result == "not_found":
        await callback.answer("❌ Идея не найдена", show_alert=True)
        return
    if result == "already":
        await callback.answer("ℹ️ Уже одобрено", show_alert=True)
        await callback_idea_card(callback, state)
        return
    
    # Уведомляем пользователя
    try:
        info = await get_idea_full_info(idea_id)
        if info and info.get("user_telegram_id"):
            await callback.bot.send_message(
                chat_id=info["user_telegram_id"],
                text="🎉 Ваша идея одобрена!\n\nМы начислили вам +2 кредита. Спасибо за вклад!",
            )
    except Exception as e:
        logger.warning("idea_notify_failed", error=str(e), idea_id=idea_id)
    
    await callback.answer("✅ Идея одобрена", show_alert=True)
    await callback_idea_card(callback, state)


@router.callback_query(F.data.startswith("admin:idea_reject:"))
async def callback_idea_reject(callback: CallbackQuery, state: FSMContext) -> None:
    """Отклонить идею."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    idea_id = int(callback.data.split(":")[-1])
    
    result = await admin_reject_idea(
        admin_id=callback.from_user.id,
        idea_id=idea_id,
    )
    
    if result == "not_found":
        await callback.answer("❌ Идея не найдена", show_alert=True)
        return
    if result == "already":
        await callback.answer("ℹ️ Уже отклонено", show_alert=True)
        await callback_idea_card(callback, state)
        return
    
    await callback.answer("❌ Идея отклонена", show_alert=True)
    await callback_idea_card(callback, state)


# ============================================================
# ГЕНЕРАЦИИ
# ============================================================

@router.callback_query(F.data == "admin:generations")
async def callback_generations_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать список генераций."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    page = data.get("generations_page", 1)
    category_filter = data.get("gen_category_filter")
    date_filter = data.get("gen_date_filter")
    
    # Определяем дату для фильтра
    date_from = None
    if date_filter == "today":
        date_from = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_filter == "week":
        date_from = datetime.now() - timedelta(days=7)
    elif date_filter == "month":
        date_from = datetime.now() - timedelta(days=30)
    
    try:
        generations, total = await get_generations_paginated(
            page=page,
            per_page=ITEMS_PER_PAGE,
            category=category_filter,
            date_from=date_from,
        )
        
        total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
        
        gens_data = []
        for gen in generations:
            gens_data.append({
                "id": gen.id,
                "username": gen.user.username if gen.user else None,
                "category": gen.category,
                "quality_score": gen.quality_score,
                "created_at": gen.created_at,
            })
        
        text = (
            f"📝 <b>ГЕНЕРАЦИИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Всего: {total} | Страница {page}/{total_pages}\n"
        )
        
        if category_filter:
            text += f"🏷 Категория: {CATEGORY_NAMES.get(category_filter, category_filter)}\n"
        if date_filter:
            text += f"📅 Период: {date_filter}\n"
        
        text += "\nВыберите генерацию для просмотра:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_generations_list_keyboard(
                generations=gens_data,
                page=page,
                total_pages=total_pages,
                category_filter=category_filter,
                date_filter=date_filter,
            ),
        )
        
    except Exception as e:
        logger.error("generations_list_error", error=str(e))
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:generations_page:"))
async def callback_generations_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить страницу генераций."""
    page = int(callback.data.split(":")[-1])
    await state.update_data(generations_page=page)
    await callback_generations_list(callback, state)


@router.callback_query(F.data == "admin:gen_filter_category")
async def callback_gen_filter_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать фильтр по категории."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = "🏷 <b>ВЫБЕРИТЕ КАТЕГОРИЮ:</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_category_filter_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:gen_category:"))
async def callback_gen_set_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить фильтр категории."""
    category = callback.data.split(":")[-1]
    
    if category == "all":
        await state.update_data(gen_category_filter=None, generations_page=1)
    else:
        await state.update_data(gen_category_filter=category, generations_page=1)
    
    await callback_generations_list(callback, state)


@router.callback_query(F.data == "admin:gen_filter_date")
async def callback_gen_filter_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать фильтр по дате."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = "📅 <b>ВЫБЕРИТЕ ПЕРИОД:</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_date_filter_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:gen_date:"))
async def callback_gen_set_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить фильтр даты."""
    date_filter = callback.data.split(":")[-1]
    
    if date_filter == "all":
        await state.update_data(gen_date_filter=None, generations_page=1)
    else:
        await state.update_data(gen_date_filter=date_filter, generations_page=1)
    
    await callback_generations_list(callback, state)


@router.callback_query(F.data.startswith("admin:generation:"))
async def callback_generation_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать карточку генерации."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[-1])
    
    try:
        info = await get_generation_full_info(generation_id)
        
        if not info:
            await callback.answer("❌ Генерация не найдена", show_alert=True)
            return
        
        username = info.get("username") or "Аноним"
        category = CATEGORY_NAMES.get(info.get("category", ""), info.get("category", ""))
        created_at = info.get("created_at")
        created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "?"
        
        # Обрезаем тексты
        analysis = info.get("photo_analysis", "")[:300]
        if len(info.get("photo_analysis", "")) > 300:
            analysis += "..."
        
        tz_text = info.get("tz_text", "")[:400]
        if len(info.get("tz_text", "")) > 400:
            tz_text += "..."
        
        photos_count = len(info.get("photos", []))
        
        text = (
            f"📝 <b>ГЕНЕРАЦИЯ #{generation_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"👤 <b>Пользователь:</b> @{username}\n"
            f"🏷 <b>Категория:</b> {category}\n"
            f"⭐ <b>Качество:</b> {info.get('quality_score') or 0}%\n"
            f"🖼 <b>Фото:</b> {photos_count}\n"
            f"🔄 <b>Перегенераций:</b> {info.get('regenerations', 0)}\n"
            f"🎁 <b>Бесплатная:</b> {'Да' if info.get('is_free') else 'Нет'}\n"
            f"📅 <b>Дата:</b> {created_str}\n\n"
            
            f"📊 <b>Анализ товара:</b>\n"
            f"<i>{analysis}</i>\n\n"
            
            f"📄 <b>ТЗ:</b>\n"
            f"<i>{tz_text}</i>"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_generation_card_keyboard(
                generation_id=generation_id,
                has_photos=photos_count > 0,
            ),
        )
        
    except Exception as e:
        logger.error("generation_card_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:gen_photos:"))
async def callback_generation_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать фотографии генерации."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[-1])
    
    try:
        info = await get_generation_full_info(generation_id)
        
        if not info or not info.get("photos"):
            await callback.answer("❌ Фото не найдены", show_alert=True)
            return
        
        # Отправляем фото
        for photo in info["photos"]:
            try:
                await callback.message.answer_photo(
                    photo=photo["file_id"],
                    caption=f"📷 Генерация #{generation_id}",
                )
            except Exception as e:
                logger.warning("photo_send_error", error=str(e))
        
        await callback.answer()
        
    except Exception as e:
        logger.error("generation_photos_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:gen_delete:"))
async def callback_generation_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Удалить генерацию."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[-1])
    
    text = (
        f"⚠️ <b>УДАЛЕНИЕ ГЕНЕРАЦИИ #{generation_id}</b>\n\n"
        "Вы уверены? Это действие необратимо!"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_confirm_action_keyboard("gen_delete", generation_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:gen_delete_yes:"))
async def callback_generation_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтвердить удаление генерации."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[-1])
    
    try:
        success = await admin_delete_generation(
            admin_id=callback.from_user.id,
            generation_id=generation_id,
        )
        
        if success:
            await callback.answer("✅ Генерация удалена", show_alert=True)
        else:
            await callback.answer("❌ Ошибка удаления", show_alert=True)
        
        # Возвращаемся к списку
        await callback_generations_list(callback, state)
        
    except Exception as e:
        logger.error("generation_delete_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


# ============================================================
# ПЛАТЕЖИ
# ============================================================

@router.callback_query(F.data == "admin:payments")
async def callback_payments_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать список платежей."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    page = data.get("payments_page", 1)
    status_filter = data.get("pay_status_filter")
    
    try:
        payments, total = await get_payments_paginated(
            page=page,
            per_page=ITEMS_PER_PAGE,
            status=status_filter,
        )
        
        total_pages = math.ceil(total / ITEMS_PER_PAGE) or 1
        
        payments_data = []
        for payment in payments:
            payments_data.append({
                "id": payment.id,
                "username": payment.user.username if payment.user else None,
                "amount": payment.amount,
                "status": payment.status,
                "created_at": payment.created_at,
            })
        
        text = (
            f"💳 <b>ПЛАТЕЖИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Всего: {total} | Страница {page}/{total_pages}\n\n"
            f"Выберите платёж для просмотра:"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_payments_list_keyboard(
                payments=payments_data,
                page=page,
                total_pages=total_pages,
                status_filter=status_filter,
            ),
        )
        
    except Exception as e:
        logger.error("payments_list_error", error=str(e))
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:payments_page:"))
async def callback_payments_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить страницу платежей."""
    page = int(callback.data.split(":")[-1])
    await state.update_data(payments_page=page)
    await callback_payments_list(callback, state)


@router.callback_query(F.data.startswith("admin:pay_status:"))
async def callback_pay_status_filter(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить фильтр статуса платежей."""
    status = callback.data.split(":")[-1]
    
    if status == "all":
        await state.update_data(pay_status_filter=None, payments_page=1)
    else:
        await state.update_data(pay_status_filter=status, payments_page=1)
    
    await callback_payments_list(callback, state)


# ============================================================
# АНАЛИТИКА
# ============================================================

@router.callback_query(F.data == "admin:analytics")
async def callback_analytics(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать раздел аналитики."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = (
        "📊 <b>АНАЛИТИКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите раздел для просмотра:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_analytics_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:analytics_conversion")
async def callback_analytics_conversion(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать статистику конверсии."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        stats = await get_conversion_stats()
        
        text = (
            "🔄 <b>КОНВЕРСИЯ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"👥 <b>Всего пользователей:</b> {stats['total_users']}\n"
            f"💳 <b>Платящих:</b> {stats['paying_users']}\n"
            f"📝 <b>Активных (с генерациями):</b> {stats['active_users']}\n\n"
            
            f"📈 <b>Конверсия в платёж:</b> {stats['conversion_rate']}%\n"
            f"💰 <b>LTV (средний доход):</b> {stats['ltv']:.2f}₽"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_back_keyboard("analytics"),
        )
        
    except Exception as e:
        logger.error("analytics_conversion_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "admin:analytics_categories")
async def callback_analytics_categories(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать статистику по категориям."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        stats = await get_category_stats()
        
        if stats:
            cats_text = "\n".join([
                f"   • {CATEGORY_NAMES.get(s['category'], s['category'])}: "
                f"{s['count']} ({s['percentage']}%)"
                for s in stats
            ])
        else:
            cats_text = "   • Нет данных"
        
        text = (
            "🏷 <b>КАТЕГОРИИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{cats_text}"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_back_keyboard("analytics"),
        )
        
    except Exception as e:
        logger.error("analytics_categories_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "admin:analytics_registrations")
async def callback_analytics_registrations(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать выбор периода для регистраций."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = "📈 <b>РЕГИСТРАЦИИ</b>\n\nВыберите период:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_analytics_period_keyboard("reg"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:analytics_reg:"))
async def callback_analytics_reg_period(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать статистику регистраций за период."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    days = int(callback.data.split(":")[-1])
    
    try:
        stats = await get_registration_stats(days=days)
        
        if stats:
            total = sum(s["count"] for s in stats)
            avg = total / len(stats) if stats else 0
            
            # Простая ASCII диаграмма
            max_count = max(s["count"] for s in stats) if stats else 1
            chart_lines = []
            for s in stats[-10:]:  # Последние 10 дней
                bar_len = int(s["count"] / max_count * 20) if max_count > 0 else 0
                bar = "█" * bar_len
                chart_lines.append(f"{s['date'][-5:]}: {bar} {s['count']}")
            
            chart = "\n".join(chart_lines)
        else:
            total = 0
            avg = 0
            chart = "Нет данных"
        
        text = (
            f"📈 <b>РЕГИСТРАЦИИ ({days} дней)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"<b>Всего:</b> {total}\n"
            f"<b>В среднем/день:</b> {avg:.1f}\n\n"
            
            f"<code>{chart}</code>"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_back_keyboard("analytics"),
        )
        
    except Exception as e:
        logger.error("analytics_reg_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "admin:analytics_revenue")
async def callback_analytics_revenue(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать выбор периода для доходов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = "💰 <b>ДОХОДЫ</b>\n\nВыберите период:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_analytics_period_keyboard("rev"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:analytics_rev:"))
async def callback_analytics_rev_period(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать статистику доходов за период."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    days = int(callback.data.split(":")[-1])
    
    try:
        stats = await get_revenue_by_period(days=days)
        
        if stats:
            total = sum(s["amount"] for s in stats)
            avg = total / len(stats) if stats else 0
            
            # Простая ASCII диаграмма
            max_amount = max(s["amount"] for s in stats) if stats else 1
            chart_lines = []
            for s in stats[-10:]:
                bar_len = int(s["amount"] / max_amount * 15) if max_amount > 0 else 0
                bar = "█" * bar_len
                chart_lines.append(f"{s['date'][-5:]}: {bar} {s['amount']:.0f}₽")
            
            chart = "\n".join(chart_lines)
        else:
            total = 0
            avg = 0
            chart = "Нет данных"
        
        text = (
            f"💰 <b>ДОХОДЫ ({days} дней)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"<b>Всего:</b> {total:.0f}₽\n"
            f"<b>В среднем/день:</b> {avg:.0f}₽\n\n"
            
            f"<code>{chart}</code>"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_back_keyboard("analytics"),
        )
        
    except Exception as e:
        logger.error("analytics_rev_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


# ============================================================
# НАСТРОЙКИ
# ============================================================

@router.callback_query(F.data == "admin:settings")
async def callback_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать раздел настроек."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        maintenance = await get_bot_setting("maintenance_mode", "false")
        free_gen = await get_bot_setting("free_generations_enabled", "true")
        
        text = (
            "🔧 <b>НАСТРОЙКИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Управление настройками бота:"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_settings_keyboard(
                maintenance_mode=maintenance == "true",
                free_generations_enabled=free_gen == "true",
            ),
        )
        
    except Exception as e:
        logger.error("settings_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "admin:setting_maintenance")
async def callback_toggle_maintenance(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить режим обслуживания."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        current = await get_bot_setting("maintenance_mode", "false")
        new_value = "false" if current == "true" else "true"
        
        await set_bot_setting(
            key="maintenance_mode",
            value=new_value,
            admin_id=callback.from_user.id,
        )
        
        status = "включен" if new_value == "true" else "выключен"
        await callback.answer(f"🔧 Режим обслуживания {status}", show_alert=True)
        
        await callback_settings(callback, state)
        
    except Exception as e:
        logger.error("toggle_maintenance_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin:setting_free_gen")
async def callback_toggle_free_gen(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить бесплатные генерации."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        current = await get_bot_setting("free_generations_enabled", "true")
        new_value = "false" if current == "true" else "true"
        
        await set_bot_setting(
            key="free_generations_enabled",
            value=new_value,
            admin_id=callback.from_user.id,
        )
        
        status = "включены" if new_value == "true" else "выключены"
        await callback.answer(f"🎁 Бесплатные генерации {status}", show_alert=True)
        
        await callback_settings(callback, state)
        
    except Exception as e:
        logger.error("toggle_free_gen_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin:setting_free_credits")
async def callback_free_credits(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать выбор количества бесплатных кредитов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    current = await get_bot_setting("free_credits", "1")
    
    text = (
        "💎 <b>БЕСПЛАТНЫЕ КРЕДИТЫ</b>\n\n"
        f"Текущее значение: <b>{current}</b>\n\n"
        "Выберите количество кредитов для новых пользователей:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_free_credits_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:set_free_credits:"))
async def callback_set_free_credits(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить количество бесплатных кредитов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    amount = callback.data.split(":")[-1]
    
    try:
        await set_bot_setting(
            key="free_credits",
            value=amount,
            admin_id=callback.from_user.id,
        )
        
        await callback.answer(f"✅ Установлено {amount} бесплатных кредитов", show_alert=True)
        await callback_settings(callback, state)
        
    except Exception as e:
        logger.error("set_free_credits_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin:reset_revenue_stats")
async def callback_reset_revenue_stats(callback: CallbackQuery, state: FSMContext) -> None:
    """Сбросить статистику прибыли."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    # Показываем подтверждение
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, сбросить",
            callback_data="admin:confirm_reset_revenue",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="admin:settings",
        ),
    )
    
    await callback.message.edit_text(
        "🗑 <b>СБРОС СТАТИСТИКИ ПРИБЫЛИ</b>\n\n"
        "⚠️ <b>Внимание!</b> Это действие удалит ВСЕ записи о платежах.\n\n"
        "Вы уверены?",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:confirm_reset_revenue")
async def callback_confirm_reset_revenue(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение сброса статистики прибыли."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        from database.database import get_session
        from database.models import Payment
        from sqlalchemy import delete
        
        async with get_session() as session:
            # Удаляем все платежи
            await session.execute(delete(Payment))
            await session.commit()
        
        # Логируем действие
        await log_admin_action(
            admin_id=callback.from_user.id,
            action_type="reset_revenue",
            description="Сброс статистики прибыли",
        )
        
        await callback.answer("✅ Статистика прибыли сброшена", show_alert=True)
        
        logger.info(
            "revenue_stats_reset",
            admin_id=callback.from_user.id,
        )
        
        await callback_settings(callback, state)
        
    except Exception as e:
        logger.error("reset_revenue_error", error=str(e))
        await callback.answer("❌ Ошибка сброса статистики", show_alert=True)


@router.callback_query(F.data == "admin:check_ai")
async def callback_check_ai(callback: CallbackQuery, state: FSMContext) -> None:
    """Проверить статус AI провайдеров."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.answer("🔄 Проверка AI провайдеров...")
    
    # TODO: Реализовать проверку AI провайдеров
    # Пока заглушка
    
    gemini_status = "✅ Online" if settings.gemini_api_key else "❌ Не настроен"
    
    text = (
        "🤖 <b>СТАТУС AI ПРОВАЙДЕРА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        f"<b>Gemini:</b> {gemini_status}\n\n"
        
        f"📅 Проверено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard("settings"),
    )


# ============================================================
# ЛОГИ
# ============================================================

@router.callback_query(F.data == "admin:logs")
async def callback_logs(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать раздел логов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    level_filter = data.get("logs_level_filter")
    
    text = (
        "📋 <b>ЛОГИ И МОНИТОРИНГ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "Логи хранятся в structlog.\n"
        "Для просмотра файловых логов используйте сервер.\n\n"
        
        "Выберите уровень для фильтрации:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_logs_keyboard(level_filter=level_filter),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:logs_level:"))
async def callback_logs_level(callback: CallbackQuery, state: FSMContext) -> None:
    """Установить фильтр уровня логов."""
    level = callback.data.split(":")[-1]
    
    # Получаем текущий фильтр
    data = await state.get_data()
    current_filter = data.get("logs_level_filter")
    
    # Определяем новый фильтр
    new_filter = None if level == "all" else level
    
    # Если фильтр не изменился, просто отвечаем на callback
    if current_filter == new_filter:
        await callback.answer()
        return
    
    # Обновляем фильтр
    if level == "all":
        await state.update_data(logs_level_filter=None)
    else:
        await state.update_data(logs_level_filter=level)
    
    await callback_logs(callback, state)


@router.callback_query(F.data == "admin:admin_actions")
async def callback_admin_actions(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать историю действий администраторов."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    page = data.get("actions_page", 1)
    
    try:
        actions = await get_admin_actions(
            limit=ITEMS_PER_PAGE,
            offset=(page - 1) * ITEMS_PER_PAGE,
        )
        
        if actions:
            actions_text = "\n".join([
                f"• [{a.created_at.strftime('%d.%m %H:%M')}] "
                f"<b>{a.action_type}</b> → {a.target_user_id or 'N/A'}"
                for a in actions
            ])
        else:
            actions_text = "Нет действий"
        
        # TODO: Получить общее количество для пагинации
        total_pages = 1
        
        text = (
            "📜 <b>ДЕЙСТВИЯ АДМИНИСТРАТОРОВ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{actions_text}"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_actions_keyboard(page=page, total_pages=total_pages),
        )
        
    except Exception as e:
        logger.error("admin_actions_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


# ============================================================
# ДОПОЛНИТЕЛЬНЫЕ CALLBACK'и (информационные)
# ============================================================

@router.callback_query(F.data.in_({"admin:users_info", "admin:gen_info", "admin:pay_info", "admin:actions_info"}))
async def callback_info_stub(callback: CallbackQuery) -> None:
    """Заглушка для информационных кнопок."""
    await callback.answer()


# ============================================================
# ПОЛНЫЙ ТЕКСТ ТЗ И АНАЛИЗА
# ============================================================

@router.callback_query(F.data.startswith("admin:gen_full_tz:"))
async def callback_gen_full_tz(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать полный текст ТЗ."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[-1])
    
    try:
        info = await get_generation_full_info(generation_id)
        
        if not info or not info.get("tz_text"):
            await callback.answer("❌ ТЗ не найдено", show_alert=True)
            return
        
        tz_text = info.get("tz_text", "")
        
        # Разбиваем на части если слишком длинное
        max_length = 4000
        parts = []
        
        while len(tz_text) > max_length:
            split_pos = tz_text.rfind("\n", 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            parts.append(tz_text[:split_pos])
            tz_text = tz_text[split_pos:].strip()
        
        if tz_text:
            parts.append(tz_text)
        
        # Отправляем первую часть
        header = f"📄 <b>ПОЛНЫЙ ТЕКСТ ТЗ #{generation_id}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, part in enumerate(parts):
            if i == 0:
                text = header + part
            else:
                text = f"<i>Продолжение ({i+1}/{len(parts)}):</i>\n\n" + part
            
            await callback.message.answer(text, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logger.error("gen_full_tz_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:gen_full_analysis:"))
async def callback_gen_full_analysis(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать полный анализ фото."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[-1])
    
    try:
        info = await get_generation_full_info(generation_id)
        
        if not info or not info.get("photo_analysis"):
            await callback.answer("❌ Анализ не найден", show_alert=True)
            return
        
        analysis = info.get("photo_analysis", "")
        
        # Разбиваем на части если слишком длинное
        max_length = 4000
        parts = []
        
        while len(analysis) > max_length:
            split_pos = analysis.rfind("\n", 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            parts.append(analysis[:split_pos])
            analysis = analysis[split_pos:].strip()
        
        if analysis:
            parts.append(analysis)
        
        header = f"📝 <b>ПОЛНЫЙ АНАЛИЗ ФОТО #{generation_id}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, part in enumerate(parts):
            if i == 0:
                text = header + part
            else:
                text = f"<i>Продолжение ({i+1}/{len(parts)}):</i>\n\n" + part
            
            await callback.message.answer(text, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logger.error("gen_full_analysis_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)


# ============================================================
# КАРТОЧКА ПЛАТЕЖА
# ============================================================

@router.callback_query(F.data.startswith("admin:payment:"))
async def callback_payment_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать карточку платежа."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    payment_id = int(callback.data.split(":")[-1])
    
    try:
        from database.admin_crud import get_payment_full_info
        
        info = await get_payment_full_info(payment_id)
        
        if not info:
            await callback.answer("❌ Платёж не найден", show_alert=True)
            return
        
        username = info.get("username") or "Аноним"
        status = info.get("status", "unknown")
        amount = info.get("amount", 0) / 100
        credits = info.get("credits_added", 0)
        
        created_at = info.get("created_at")
        created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "?"
        
        status_text = {
            "completed": "✅ Успешно",
            "pending": "⏳ В обработке",
            "failed": "❌ Неудачно",
            "refunded": "🔄 Возврат",
        }.get(status, f"❓ {status}")
        
        text = (
            f"💳 <b>ПЛАТЁЖ #{payment_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            f"👤 <b>Пользователь:</b> @{username}\n"
            f"💵 <b>Сумма:</b> {amount:.0f}₽\n"
            f"💎 <b>Кредитов:</b> {credits}\n"
            f"📊 <b>Статус:</b> {status_text}\n"
            f"📅 <b>Дата:</b> {created_str}\n"
        )
        
        if info.get("payment_id"):
            text += f"🔗 <b>ID платежа:</b> <code>{info['payment_id']}</code>\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_payment_card_keyboard(payment_id),
        )
        
    except ImportError:
        # Функция не существует - создаём заглушку
        await callback.answer("⚠️ Функция в разработке", show_alert=True)
    except Exception as e:
        logger.error("payment_card_error", error=str(e))
        await callback.answer("❌ Ошибка", show_alert=True)
    
    await callback.answer()


# ============================================================
# ПАГИНАЦИЯ ДЕЙСТВИЙ АДМИНОВ
# ============================================================

@router.callback_query(F.data.startswith("admin:actions_page:"))
async def callback_actions_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключить страницу действий администраторов."""
    page = int(callback.data.split(":")[-1])
    await state.update_data(actions_page=page)
    await callback_admin_actions(callback, state)


# ============================================================
# КАСТОМНОЕ КОЛИЧЕСТВО КРЕДИТОВ
# ============================================================

@router.callback_query(F.data.startswith("admin:credit_add_custom:"))
async def callback_credit_add_custom(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать ввод произвольного количества кредитов для начисления."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    await state.set_state(AdminStates.entering_custom_credits)
    await state.update_data(credit_action="add", target_telegram_id=telegram_id)
    
    text = (
        "✏️ <b>НАЧИСЛЕНИЕ КРЕДИТОВ</b>\n\n"
        f"Пользователь: <code>{telegram_id}</code>\n\n"
        "Введите количество кредитов для начисления:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard("users"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:credit_remove_custom:"))
async def callback_credit_remove_custom(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать ввод произвольного количества кредитов для списания."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    await state.set_state(AdminStates.entering_custom_credits)
    await state.update_data(credit_action="remove", target_telegram_id=telegram_id)
    
    text = (
        "✏️ <b>СПИСАНИЕ КРЕДИТОВ</b>\n\n"
        f"Пользователь: <code>{telegram_id}</code>\n\n"
        "Введите количество кредитов для списания:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard("users"),
    )
    await callback.answer()


@router.message(AdminStates.entering_custom_credits)
async def handle_custom_credits_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода произвольного количества кредитов."""
    if not message.from_user or not is_admin(message.from_user.id):
        return
    
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Введите положительное число.")
            return
        if amount > 10000:
            await message.answer("❌ Максимум 10000 кредитов за раз.")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return
    
    data = await state.get_data()
    action = data.get("credit_action", "add")
    telegram_id = data.get("target_telegram_id")
    
    if not telegram_id:
        await message.answer("❌ Ошибка: пользователь не найден.")
        await state.clear()
        return
    
    try:
        if action == "add":
            success = await admin_add_credits(
                admin_id=message.from_user.id,
                telegram_id=telegram_id,
                amount=amount,
                reason="Начисление через админ-панель (кастомное)",
            )
            if success:
                await message.answer(f"✅ Начислено {amount} кредитов пользователю {telegram_id}")
            else:
                await message.answer("❌ Ошибка начисления")
        else:
            success = await admin_remove_credits(
                admin_id=message.from_user.id,
                telegram_id=telegram_id,
                amount=amount,
                reason="Списание через админ-панель (кастомное)",
            )
            if success:
                await message.answer(f"✅ Списано {amount} кредитов у пользователя {telegram_id}")
            else:
                await message.answer("❌ Недостаточно кредитов для списания")
        
        await state.clear()
        
    except Exception as e:
        logger.error("custom_credits_error", error=str(e))
        await message.answer("❌ Ошибка операции")
        await state.clear()


# ============================================================
# ПЛАТЕЖИ И ГЕНЕРАЦИИ ПОЛЬЗОВАТЕЛЯ
# ============================================================

@router.callback_query(F.data.startswith("admin:user_payments:"))
async def callback_user_payments(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать платежи конкретного пользователя."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    try:
        from database.database import get_session
        from database.models import User, Payment
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        async with get_session() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.payments))
                .where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        payments = sorted(user.payments, key=lambda p: p.created_at, reverse=True)[:10]
        
        if not payments:
            text = (
                f"💳 <b>ПЛАТЕЖИ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Пользователь: <code>{telegram_id}</code>\n\n"
                f"📭 Платежей пока нет"
            )
        else:
            total_sum = sum(p.amount for p in user.payments) / 100
            text = (
                f"💳 <b>ПЛАТЕЖИ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Пользователь: @{user.username or 'Аноним'}\n"
                f"💰 Всего оплачено: <b>{total_sum:.0f}₽</b>\n"
                f"📊 Транзакций: {len(user.payments)}\n\n"
                f"<b>Последние платежи:</b>\n"
            )
            
            for p in payments:
                status_emoji = "✅" if p.status == "completed" else "⏳"
                date_str = p.created_at.strftime("%d.%m.%Y")
                text += f"{status_emoji} {p.amount/100:.0f}₽ — {p.credits_added} кр. ({date_str})\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="⬅️ К пользователю",
                callback_data=f"admin:user:{telegram_id}",
            ),
        )
        builder.row(
            InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error("user_payments_error", error=str(e), telegram_id=telegram_id)
        await callback.answer("❌ Ошибка загрузки платежей", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user_generations:"))
async def callback_user_generations(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать генерации конкретного пользователя."""
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split(":")[-1])
    
    try:
        from database.database import get_session
        from database.models import User, Generation
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        async with get_session() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.generations))
                .where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        generations = sorted(user.generations, key=lambda g: g.created_at, reverse=True)[:10]
        
        if not generations:
            text = (
                f"📝 <b>ГЕНЕРАЦИИ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Пользователь: <code>{telegram_id}</code>\n\n"
                f"📭 Генераций пока нет"
            )
        else:
            text = (
                f"📝 <b>ГЕНЕРАЦИИ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Пользователь: @{user.username or 'Аноним'}\n"
                f"📊 Всего генераций: <b>{len(user.generations)}</b>\n\n"
                f"<b>Последние генерации:</b>\n"
            )
            
            for g in generations:
                cat_name = CATEGORY_NAMES.get(g.category, g.category)
                date_str = g.created_at.strftime("%d.%m.%Y")
                score = g.quality_score or 0
                text += f"• {cat_name} — {score}/100 ({date_str})\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="⬅️ К пользователю",
                callback_data=f"admin:user:{telegram_id}",
            ),
        )
        builder.row(
            InlineKeyboardButton(text="🏠 Меню", callback_data="admin:main"),
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error("user_generations_error", error=str(e), telegram_id=telegram_id)
        await callback.answer("❌ Ошибка загрузки генераций", show_alert=True)
    
    await callback.answer()
