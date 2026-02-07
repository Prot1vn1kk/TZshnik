"""
Обработчики команд администратора.

Содержит:
- /stats - статистика бота
- /broadcast - рассылка всем пользователям
"""

import asyncio
import structlog
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, desc

from bot.config import settings
from database import get_admin_stats
from database.models import User
from database.database import get_session


logger = structlog.get_logger()
router = Router(name="admin_commands")


# ============================================================
# ФИЛЬТР АДМИНА
# ============================================================

def is_admin(message: Message) -> bool:
    """Проверка является ли пользователь администратором."""
    return message.from_user.id in settings.admin_ids


# ============================================================
# КОМАНДА /STATS
# ============================================================

@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
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
        stats = await get_admin_stats()
        
        # Форматируем статистику
        total_users = stats.get('total_users', 0)
        total_gens = stats.get('total_generations', 0)
        avg_per_user = total_gens / total_users if total_users > 0 else 0

        text = (
            "📊 <b>Статистика бота</b>\n\n"

            f"👥 <b>Пользователи:</b>\n"
            f"   • Всего: {total_users}\n"
            f"   • Новых сегодня: {stats.get('new_users_today', 0)}\n\n"

            f"📝 <b>Генерации:</b>\n"
            f"   • Всего: {total_gens}\n\n"

            f"💰 <b>Выручка:</b>\n"
            f"   • Сумма: {stats.get('total_revenue_rub', 0):.2f}₽\n\n"

            f"📈 <b>Средние показатели:</b>\n"
            f"   • Генераций на юзера: {avg_per_user:.1f}\n"
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
) -> None:
    """Показать последних пользователей (для админа)."""
    if not is_admin(message):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return
    
    try:
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
    bot: Bot,
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
    
    # Получаем всех пользователей
    try:
        async with get_session() as session:
            result = await session.execute(select(User.telegram_id))
            user_ids = [row[0] for row in result.fetchall()]
        
        if not user_ids:
            await message.answer("❌ Нет пользователей для рассылки.")
            return
        
        total = len(user_ids)
        
        # Отправляем уведомление о начале
        status_msg = await message.answer(
            f"📢 <b>Рассылка начата...</b>\n\n"
            f"Всего пользователей: {total}\n"
            f"Отправлено: 0/{total}",
            parse_mode="HTML",
        )
        
        success = 0
        failed = 0
        
        for i, user_id in enumerate(user_ids, 1):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=broadcast_text,
                    parse_mode="HTML",
                )
                success += 1
            except Exception as e:
                failed += 1
                logger.debug("broadcast_send_failed", user_id=user_id, error=str(e))
            
            # Обновляем статус каждые 10 пользователей
            if i % 10 == 0 or i == total:
                try:
                    await status_msg.edit_text(
                        f"📢 <b>Рассылка в процессе...</b>\n\n"
                        f"Отправлено: {i}/{total} ({i*100//total}%)\n"
                        f"✅ Успешно: {success}\n"
                        f"❌ Ошибок: {failed}",
                        parse_mode="HTML",
                    )
                except:
                    pass
            
            # Задержка для избежания flood control
            await asyncio.sleep(0.05)
        
        # Итоговое сообщение
        await status_msg.edit_text(
            f"📢 <b>Рассылка завершена!</b>\n\n"
            f"✅ Успешно: {success}\n"
            f"❌ Неудачно: {failed}\n"
            f"📊 Всего: {total}",
            parse_mode="HTML",
        )
        
        logger.info(
            "Broadcast completed",
            admin_id=message.from_user.id,
            total=total,
            success=success,
            failed=failed,
        )
        
    except Exception as e:
        logger.error("Broadcast error", error=str(e))
        await message.answer(f"❌ Ошибка рассылки: {e}")


# Команда /admin обрабатывается в admin_panel.py
