"""
Обработчики команд администратора.

Содержит:
- /stats - статистика бота
- /broadcast - рассылка всем пользователям
"""

import structlog
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from database import get_admin_stats
from database.models import User


logger = structlog.get_logger()
router = Router(name="admin_commands")


# ============================================================
# ФИЛЬТР АДМИНА
# ============================================================

def is_admin(message: Message) -> bool:
    """Проверка является ли пользователь администратором."""
    return message.from_user.id == settings.admin_user_id


# ============================================================
# КОМАНДА /STATS
# ============================================================

@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Показать статистику бота (только для админов).
    
    Отображает:
    - Количество пользователей
    - Количество генераций
    - Сумму платежей
    """
    # Проверяем админа
    if not is_admin(message):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return
    
    try:
        stats = await get_admin_stats(session)
        
        # Форматируем статистику
        text = (
            "📊 <b>Статистика бота</b>\n\n"
            
            f"👥 <b>Пользователи:</b>\n"
            f"   • Всего: {stats.get('total_users', 0)}\n"
            f"   • Сегодня: {stats.get('users_today', 0)}\n"
            f"   • Активных (7 дн): {stats.get('active_users_7d', 0)}\n\n"
            
            f"📝 <b>Генерации:</b>\n"
            f"   • Всего: {stats.get('total_generations', 0)}\n"
            f"   • Успешных: {stats.get('successful_generations', 0)}\n"
            f"   • Сегодня: {stats.get('generations_today', 0)}\n\n"
            
            f"💰 <b>Платежи:</b>\n"
            f"   • Всего: {stats.get('total_payments', 0)}\n"
            f"   • Сумма: {stats.get('total_revenue', 0) / 100:.2f}₽\n"
            f"   • Сегодня: {stats.get('payments_today', 0)}\n\n"
            
            f"📈 <b>Средние показатели:</b>\n"
            f"   • Генераций на юзера: {stats.get('avg_generations_per_user', 0):.1f}\n"
            f"   • Качество ТЗ: {stats.get('avg_quality_score', 0):.0f}/100\n"
        )
        
        await message.answer(text, parse_mode="HTML")
        
        logger.info(
            "Admin stats requested",
            admin_id=message.from_user.id,
        )
        
    except Exception as e:
        logger.error("Stats command failed", error=str(e))
        await message.answer("❌ Ошибка при получении статистики.")


# ============================================================
# КОМАНДА /USERS
# ============================================================

@router.message(Command("users"))
async def cmd_users(
    message: Message,
    session: AsyncSession,
) -> None:
    """Показать последних пользователей (для админа)."""
    if not is_admin(message):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return
    
    try:
        from database.database import get_session
        from sqlalchemy import select, desc
        
        async with get_session() as sess:
            result = await sess.execute(
                select(User)
                .order_by(desc(User.created_at))
                .limit(10)
            )
            users = result.scalars().all()
        
        if not users:
            await message.answer("Пользователей пока нет.")
            return
        
        text = "👥 <b>Последние пользователи:</b>\n\n"
        
        for user in users:
            username = f"@{user.username}" if user.username else "без username"
            date_str = user.created_at.strftime("%d.%m.%Y")
            text += (
                f"• <b>{user.first_name or 'Без имени'}</b> ({username})\n"
                f"  ID: {user.telegram_id} | Баланс: {user.balance}\n"
                f"  Генераций: {user.total_generated} | Дата: {date_str}\n\n"
            )
        
        await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error("Users command failed", error=str(e))
        await message.answer("❌ Ошибка при получении пользователей.")


# ============================================================
# КОМАНДА /BROADCAST
# ============================================================

@router.message(Command("broadcast"))
async def cmd_broadcast(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Рассылка сообщения всем пользователям (для админа).
    
    Использование: /broadcast Текст сообщения
    """
    if not is_admin(message):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return
    
    # Получаем текст для рассылки
    if not message.text:
        await message.answer("Использование: /broadcast Текст сообщения")
        return
    
    broadcast_text = message.text.replace("/broadcast", "").strip()
    
    if not broadcast_text:
        await message.answer(
            "📢 <b>Рассылка</b>\n\n"
            "Использование: /broadcast Текст сообщения\n\n"
            "Пример:\n"
            "<code>/broadcast Привет! Новая функция в боте!</code>",
            parse_mode="HTML",
        )
        return
    
    # Подтверждение
    await message.answer(
        f"📢 <b>Подготовка рассылки</b>\n\n"
        f"Текст:\n{broadcast_text}\n\n"
        f"Функция рассылки будет добавлена позже.",
        parse_mode="HTML",
    )
    
    logger.info(
        "Broadcast initiated",
        admin_id=message.from_user.id,
        text_length=len(broadcast_text),
    )


# Команда /admin обрабатывается в admin_panel.py
