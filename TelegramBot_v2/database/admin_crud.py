"""
CRUD операции для админ-панели.

Содержит функции для:
- Расширенной статистики
- Управления пользователями
- Просмотра генераций и платежей
- Логирования действий администраторов
- Управления настройками бота
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, desc, func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.database import get_session
from database.models import (
    AdminAction,
    BotSettings,
    Feedback,
    Generation,
    GenerationPhoto,
    Payment,
    User,
)


logger = structlog.get_logger()


# ==================== ADMIN ACTIONS LOG ====================

async def log_admin_action(
    admin_id: int,
    action_type: str,
    target_user_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    session: Optional[AsyncSession] = None,
) -> AdminAction:
    """
    Логировать административное действие.
    
    Args:
        admin_id: Telegram ID администратора
        action_type: Тип действия (credit_add, credit_remove, block, unblock, etc.)
        target_user_id: Telegram ID целевого пользователя
        details: Дополнительные детали
        session: Опциональная существующая сессия (для избежания блокировок)
        
    Returns:
        Созданный объект AdminAction
    """
    action = AdminAction(
        admin_id=admin_id,
        action_type=action_type,
        target_user_id=target_user_id,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    )
    
    if session:
        # Используем существующую сессию
        session.add(action)
        await session.flush()
        await session.refresh(action)
    else:
        # Создаем новую сессию
        async with get_session() as new_session:
            new_session.add(action)
            await new_session.flush()
            await new_session.refresh(action)
    
    logger.info(
        "admin_action_logged",
        admin_id=admin_id,
        action_type=action_type,
        target_user_id=target_user_id,
    )
    
    return action


async def get_admin_actions(
    limit: int = 50,
    offset: int = 0,
    action_type: Optional[str] = None,
    admin_id: Optional[int] = None,
) -> List[AdminAction]:
    """
    Получить историю административных действий.
    
    Args:
        limit: Максимальное количество записей
        offset: Смещение для пагинации
        action_type: Фильтр по типу действия
        admin_id: Фильтр по администратору
        
    Returns:
        Список действий
    """
    async with get_session() as session:
        query = select(AdminAction).order_by(desc(AdminAction.created_at))
        
        if action_type:
            query = query.where(AdminAction.action_type == action_type)
        if admin_id:
            query = query.where(AdminAction.admin_id == admin_id)
        
        result = await session.execute(
            query.limit(limit).offset(offset)
        )
        return list(result.scalars().all())


# ==================== DASHBOARD STATS ====================

async def get_dashboard_stats() -> Dict[str, Any]:
    """
    Получить статистику для дашборда админ-панели.
    
    Returns:
        Словарь с полной статистикой
    """
    async with get_session() as session:
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # ===== USERS =====
        # Всего пользователей
        total_users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0
        
        # Новых за сегодня
        new_today_result = await session.execute(
            select(func.count(User.id))
            .where(User.created_at >= today)
        )
        new_today = new_today_result.scalar() or 0
        
        # Активных за неделю (имеют генерации за 7 дней)
        active_week_result = await session.execute(
            select(func.count(func.distinct(Generation.user_id)))
            .where(Generation.created_at >= week_ago)
        )
        active_week = active_week_result.scalar() or 0
        
        # Заблокированных
        blocked_users_result = await session.execute(
            select(func.count(User.id))
            .where(User.is_premium == False)  # Placeholder - add is_blocked field later
        )
        
        # ===== REVENUE =====
        # Доход за сегодня
        revenue_today_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(
                Payment.status == "completed",
                Payment.created_at >= today,
            )
        )
        revenue_today = (revenue_today_result.scalar() or 0) / 100
        
        # Доход за неделю
        revenue_week_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(
                Payment.status == "completed",
                Payment.created_at >= week_ago,
            )
        )
        revenue_week = (revenue_week_result.scalar() or 0) / 100
        
        # Доход за месяц
        revenue_month_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(
                Payment.status == "completed",
                Payment.created_at >= month_ago,
            )
        )
        revenue_month = (revenue_month_result.scalar() or 0) / 100
        
        # Доход всего
        revenue_total_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "completed")
        )
        revenue_total = (revenue_total_result.scalar() or 0) / 100
        
        # ===== GENERATIONS =====
        # Всего генераций
        total_generations_result = await session.execute(
            select(func.count(Generation.id))
        )
        total_generations = total_generations_result.scalar() or 0
        
        # Генераций за сегодня
        generations_today_result = await session.execute(
            select(func.count(Generation.id))
            .where(Generation.created_at >= today)
        )
        generations_today = generations_today_result.scalar() or 0
        
        # Средний quality_score
        avg_quality_result = await session.execute(
            select(func.avg(Generation.quality_score))
            .where(Generation.quality_score.isnot(None))
        )
        avg_quality = avg_quality_result.scalar() or 0
        
        # ===== TOP CATEGORIES =====
        top_categories_result = await session.execute(
            select(
                Generation.category,
                func.count(Generation.id).label("count")
            )
            .group_by(Generation.category)
            .order_by(desc("count"))
            .limit(5)
        )
        top_categories = [
            {"category": row[0], "count": row[1]}
            for row in top_categories_result.all()
        ]
        
        # ===== PAYMENTS COUNT =====
        total_payments_result = await session.execute(
            select(func.count(Payment.id))
            .where(Payment.status == "completed")
        )
        total_payments = total_payments_result.scalar() or 0
        
        return {
            # Users
            "total_users": total_users,
            "new_users_today": new_today,
            "active_users_week": active_week,
            
            # Revenue
            "revenue_today": revenue_today,
            "revenue_week": revenue_week,
            "revenue_month": revenue_month,
            "revenue_total": revenue_total,
            
            # Generations
            "total_generations": total_generations,
            "generations_today": generations_today,
            "avg_quality_score": round(avg_quality, 1) if avg_quality else 0,
            
            # Categories
            "top_categories": top_categories,
            
            # Payments
            "total_payments": total_payments,
        }


# ==================== USER MANAGEMENT ====================

async def get_users_paginated(
    page: int = 1,
    per_page: int = 10,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[User], int]:
    """
    Получить список пользователей с пагинацией.
    
    Args:
        page: Номер страницы (начиная с 1)
        per_page: Количество на странице
        search: Поиск по telegram_id или username
        sort_by: Поле сортировки (created_at, balance, total_generated)
        sort_order: Направление сортировки (asc, desc)
        
    Returns:
        Tuple[список пользователей, общее количество]
    """
    async with get_session() as session:
        # Базовый запрос
        query = select(User)
        count_query = select(func.count(User.id))
        
        # Поиск
        if search:
            search_filter = or_(
                User.telegram_id == int(search) if search.isdigit() else False,
                User.username.ilike(f"%{search.lstrip('@')}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Сортировка
        sort_column = getattr(User, sort_by, User.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Пагинация
        offset = (page - 1) * per_page
        query = query.limit(per_page).offset(offset)
        
        # Выполнение
        users_result = await session.execute(query)
        count_result = await session.execute(count_query)
        
        users = list(users_result.scalars().all())
        total = count_result.scalar() or 0
        
        return users, total


async def get_user_full_info(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить полную информацию о пользователе.
    
    Args:
        telegram_id: Telegram ID пользователя
        
    Returns:
        Словарь с полной информацией или None
    """
    async with get_session() as session:
        # Пользователь
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Количество генераций
        gen_count_result = await session.execute(
            select(func.count(Generation.id))
            .where(Generation.user_id == user.id)
        )
        generations_count = gen_count_result.scalar() or 0
        
        # Количество платежей
        payments_count_result = await session.execute(
            select(func.count(Payment.id))
            .where(Payment.user_id == user.id, Payment.status == "completed")
        )
        payments_count = payments_count_result.scalar() or 0
        
        # Сумма платежей
        total_paid_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.user_id == user.id, Payment.status == "completed")
        )
        total_paid = (total_paid_result.scalar() or 0) / 100
        
        # Последняя активность
        last_gen_result = await session.execute(
            select(Generation.created_at)
            .where(Generation.user_id == user.id)
            .order_by(desc(Generation.created_at))
            .limit(1)
        )
        last_generation = last_gen_result.scalar_one_or_none()
        
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "balance": user.balance,
            "total_generated": user.total_generated,
            "is_premium": user.is_premium,
            "created_at": user.created_at,
            "generations_count": generations_count,
            "payments_count": payments_count,
            "total_paid": total_paid,
            "last_generation": last_generation,
        }


async def admin_add_credits(
    admin_id: int,
    telegram_id: int,
    amount: int,
    reason: Optional[str] = None,
) -> bool:
    """
    Начислить кредиты пользователю (от имени админа).
    
    Args:
        admin_id: Telegram ID администратора
        telegram_id: Telegram ID пользователя
        amount: Количество кредитов
        reason: Причина начисления
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(balance=User.balance + amount)
        )
        
        if result.rowcount > 0:
            # Логируем действие в той же сессии
            await log_admin_action(
                admin_id=admin_id,
                action_type="credit_add",
                target_user_id=telegram_id,
                details={"amount": amount, "reason": reason},
                session=session,
            )
            
            logger.info(
                "admin_credits_added",
                admin_id=admin_id,
                target_user_id=telegram_id,
                amount=amount,
            )
            return True
        
        return False


async def admin_remove_credits(
    admin_id: int,
    telegram_id: int,
    amount: int,
    reason: Optional[str] = None,
) -> bool:
    """
    Списать кредиты у пользователя (от имени админа).
    
    Args:
        admin_id: Telegram ID администратора
        telegram_id: Telegram ID пользователя
        amount: Количество кредитов
        reason: Причина списания
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        # Проверяем баланс и списываем
        result = await session.execute(
            update(User)
            .where(
                User.telegram_id == telegram_id,
                User.balance >= amount,
            )
            .values(balance=User.balance - amount)
        )
        
        if result.rowcount > 0:
            await log_admin_action(
                admin_id=admin_id,
                action_type="credit_remove",
                target_user_id=telegram_id,
                details={"amount": amount, "reason": reason},
                session=session,
            )
            
            logger.info(
                "admin_credits_removed",
                admin_id=admin_id,
                target_user_id=telegram_id,
                amount=amount,
            )
            return True
        
        return False


async def admin_block_user(
    admin_id: int,
    telegram_id: int,
    reason: str,
) -> bool:
    """
    Заблокировать пользователя.
    
    Note: Требуется добавить поле is_blocked в модель User.
    Пока используем is_premium как заглушку (инвертируем логику).
    
    Args:
        admin_id: Telegram ID администратора
        telegram_id: Telegram ID пользователя
        reason: Причина блокировки
        
    Returns:
        True если успешно
    """
    # TODO: Добавить поле is_blocked в User и обновить эту функцию
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(balance=0)  # Временная "блокировка" - обнуляем баланс
        )
        
        if result.rowcount > 0:
            await log_admin_action(
                admin_id=admin_id,
                action_type="user_block",
                target_user_id=telegram_id,
                details={"reason": reason},
                session=session,
            )
            
            logger.info(
                "user_blocked",
                admin_id=admin_id,
                target_user_id=telegram_id,
                reason=reason,
            )
            return True
        
        return False


async def admin_unblock_user(
    admin_id: int,
    telegram_id: int,
) -> bool:
    """
    Разблокировать пользователя.
    
    Args:
        admin_id: Telegram ID администратора
        telegram_id: Telegram ID пользователя
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        # Для полноценной разблокировки нужно поле is_blocked
        # Пока просто логируем действие
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            await log_admin_action(
                admin_id=admin_id,
                action_type="user_unblock",
                target_user_id=telegram_id,
                details={},
                session=session,
            )
            
            logger.info(
                "user_unblocked",
                admin_id=admin_id,
                target_user_id=telegram_id,
            )
            return True
        
        return False


# ==================== GENERATIONS MANAGEMENT ====================

async def get_generations_paginated(
    page: int = 1,
    per_page: int = 10,
    category: Optional[str] = None,
    user_telegram_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Tuple[List[Generation], int]:
    """
    Получить генерации с пагинацией и фильтрами.
    
    Args:
        page: Номер страницы
        per_page: Количество на странице
        category: Фильтр по категории
        user_telegram_id: Фильтр по пользователю
        date_from: Дата от
        date_to: Дата до
        
    Returns:
        Tuple[список генераций, общее количество]
    """
    async with get_session() as session:
        # Базовый запрос с JOIN на User для получения telegram_id
        query = (
            select(Generation)
            .options(selectinload(Generation.user))
            .options(selectinload(Generation.photos))
            .order_by(desc(Generation.created_at))
        )
        count_query = select(func.count(Generation.id))
        
        filters = []
        
        # Фильтры
        if category:
            filters.append(Generation.category == category)
        
        if user_telegram_id:
            query = query.join(User)
            count_query = count_query.join(User)
            filters.append(User.telegram_id == user_telegram_id)
        
        if date_from:
            filters.append(Generation.created_at >= date_from)
        
        if date_to:
            filters.append(Generation.created_at <= date_to)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Пагинация
        offset = (page - 1) * per_page
        query = query.limit(per_page).offset(offset)
        
        # Выполнение
        generations_result = await session.execute(query)
        count_result = await session.execute(count_query)
        
        generations = list(generations_result.scalars().all())
        total = count_result.scalar() or 0
        
        return generations, total


async def get_generation_full_info(generation_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить полную информацию о генерации.
    
    Args:
        generation_id: ID генерации
        
    Returns:
        Словарь с полной информацией
    """
    async with get_session() as session:
        result = await session.execute(
            select(Generation)
            .options(selectinload(Generation.user))
            .options(selectinload(Generation.photos))
            .options(selectinload(Generation.feedback))
            .where(Generation.id == generation_id)
        )
        generation = result.scalar_one_or_none()
        
        if not generation:
            return None
        
        return {
            "id": generation.id,
            "user_telegram_id": generation.user.telegram_id if generation.user else None,
            "username": generation.user.username if generation.user else None,
            "category": generation.category,
            "photo_analysis": generation.photo_analysis,
            "tz_text": generation.tz_text,
            "quality_score": generation.quality_score,
            "regenerations": generation.regenerations,
            "is_free": generation.is_free,
            "created_at": generation.created_at,
            "photos": [
                {"file_id": p.file_id, "file_unique_id": p.file_unique_id}
                for p in generation.photos
            ],
            "feedback": {
                "rating": generation.feedback.rating,
                "comment": generation.feedback.comment,
            } if generation.feedback else None,
        }


async def get_payment_full_info(payment_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить полную информацию о платеже.
    
    Args:
        payment_id: ID платежа
        
    Returns:
        Словарь с полной информацией
    """
    async with get_session() as session:
        result = await session.execute(
            select(Payment)
            .options(selectinload(Payment.user))
            .where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            return None
        
        return {
            "id": payment.id,
            "user_telegram_id": payment.user.telegram_id if payment.user else None,
            "username": payment.user.username if payment.user else None,
            "amount": payment.amount,
            "credits_added": payment.credits_added,
            "status": payment.status,
            "payment_id": payment.payment_id,
            "created_at": payment.created_at,
            "completed_at": payment.completed_at if hasattr(payment, 'completed_at') else None,
        }


async def admin_delete_generation(
    admin_id: int,
    generation_id: int,
) -> bool:
    """
    Удалить генерацию (от имени админа).
    
    Args:
        admin_id: Telegram ID администратора
        generation_id: ID генерации
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        # Получаем генерацию для логирования
        gen_result = await session.execute(
            select(Generation)
            .options(selectinload(Generation.user))
            .where(Generation.id == generation_id)
        )
        generation = gen_result.scalar_one_or_none()
        
        if not generation:
            return False
        
        target_user_id = generation.user.telegram_id if generation.user else None
        
        # Удаляем
        await session.execute(
            delete(Generation).where(Generation.id == generation_id)
        )
        
        await log_admin_action(
            admin_id=admin_id,
            action_type="generation_delete",
            target_user_id=target_user_id,
            details={"generation_id": generation_id},
            session=session,
        )
        
        logger.info(
            "generation_deleted",
            admin_id=admin_id,
            generation_id=generation_id,
        )
        
        return True


# ==================== PAYMENTS MANAGEMENT ====================

async def get_payments_paginated(
    page: int = 1,
    per_page: int = 10,
    status: Optional[str] = None,
    user_telegram_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Tuple[List[Payment], int]:
    """
    Получить платежи с пагинацией и фильтрами.
    
    Args:
        page: Номер страницы
        per_page: Количество на странице
        status: Фильтр по статусу (completed, pending, failed)
        user_telegram_id: Фильтр по пользователю
        date_from: Дата от
        date_to: Дата до
        
    Returns:
        Tuple[список платежей, общее количество]
    """
    async with get_session() as session:
        query = (
            select(Payment)
            .options(selectinload(Payment.user))
            .order_by(desc(Payment.created_at))
        )
        count_query = select(func.count(Payment.id))
        
        filters = []
        
        if status:
            filters.append(Payment.status == status)
        
        if user_telegram_id:
            query = query.join(User)
            count_query = count_query.join(User)
            filters.append(User.telegram_id == user_telegram_id)
        
        if date_from:
            filters.append(Payment.created_at >= date_from)
        
        if date_to:
            filters.append(Payment.created_at <= date_to)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Пагинация
        offset = (page - 1) * per_page
        query = query.limit(per_page).offset(offset)
        
        # Выполнение
        payments_result = await session.execute(query)
        count_result = await session.execute(count_query)
        
        payments = list(payments_result.scalars().all())
        total = count_result.scalar() or 0
        
        return payments, total


async def get_revenue_by_period(days: int = 30) -> List[Dict[str, Any]]:
    """
    Получить доход по дням за указанный период.
    
    Args:
        days: Количество дней
        
    Returns:
        Список [{date, amount}]
    """
    async with get_session() as session:
        start_date = datetime.now() - timedelta(days=days)
        
        result = await session.execute(
            select(
                func.date(Payment.created_at).label("date"),
                func.sum(Payment.amount).label("amount"),
            )
            .where(
                Payment.status == "completed",
                Payment.created_at >= start_date,
            )
            .group_by(func.date(Payment.created_at))
            .order_by(func.date(Payment.created_at))
        )
        
        return [
            {"date": str(row[0]), "amount": (row[1] or 0) / 100}
            for row in result.all()
        ]


# ==================== ANALYTICS ====================

async def get_registration_stats(days: int = 30) -> List[Dict[str, Any]]:
    """
    Получить статистику регистраций по дням.
    
    Args:
        days: Количество дней
        
    Returns:
        Список [{date, count}]
    """
    async with get_session() as session:
        start_date = datetime.now() - timedelta(days=days)
        
        result = await session.execute(
            select(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("count"),
            )
            .where(User.created_at >= start_date)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
        
        return [
            {"date": str(row[0]), "count": row[1]}
            for row in result.all()
        ]


async def get_conversion_stats() -> Dict[str, Any]:
    """
    Получить статистику конверсии.
    
    Returns:
        Словарь со статистикой конверсии
    """
    async with get_session() as session:
        # Всего пользователей
        total_users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0
        
        # Пользователи с платежами
        paying_users_result = await session.execute(
            select(func.count(func.distinct(Payment.user_id)))
            .where(Payment.status == "completed")
        )
        paying_users = paying_users_result.scalar() or 0
        
        # Пользователи с генерациями
        active_users_result = await session.execute(
            select(func.count(func.distinct(Generation.user_id)))
        )
        active_users = active_users_result.scalar() or 0
        
        # Средний доход на пользователя (LTV)
        total_revenue_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "completed")
        )
        total_revenue = (total_revenue_result.scalar() or 0) / 100
        
        ltv = total_revenue / total_users if total_users > 0 else 0
        
        return {
            "total_users": total_users,
            "paying_users": paying_users,
            "active_users": active_users,
            "conversion_rate": round(
                (paying_users / total_users * 100) if total_users > 0 else 0, 2
            ),
            "ltv": round(ltv, 2),
        }


async def get_category_stats() -> List[Dict[str, Any]]:
    """
    Получить статистику по категориям.
    
    Returns:
        Список [{category, count, percentage}]
    """
    async with get_session() as session:
        # Всего генераций
        total_result = await session.execute(
            select(func.count(Generation.id))
        )
        total = total_result.scalar() or 0
        
        # По категориям
        result = await session.execute(
            select(
                Generation.category,
                func.count(Generation.id).label("count"),
            )
            .group_by(Generation.category)
            .order_by(desc("count"))
        )
        
        return [
            {
                "category": row[0],
                "count": row[1],
                "percentage": round((row[1] / total * 100) if total > 0 else 0, 1),
            }
            for row in result.all()
        ]


# ==================== BOT SETTINGS ====================

async def get_bot_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Получить настройку бота.
    
    Args:
        key: Ключ настройки
        default: Значение по умолчанию
        
    Returns:
        Значение настройки или default
    """
    async with get_session() as session:
        result = await session.execute(
            select(BotSettings.value).where(BotSettings.key == key)
        )
        value = result.scalar_one_or_none()
        return value if value is not None else default


async def set_bot_setting(
    key: str,
    value: str,
    description: Optional[str] = None,
    admin_id: Optional[int] = None,
) -> bool:
    """
    Установить настройку бота.
    
    Args:
        key: Ключ настройки
        value: Новое значение
        description: Описание настройки
        admin_id: ID администратора для логирования
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        # Проверяем существует ли настройка
        existing_result = await session.execute(
            select(BotSettings).where(BotSettings.key == key)
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Обновляем
            await session.execute(
                update(BotSettings)
                .where(BotSettings.key == key)
                .values(value=value)
            )
            old_value = existing.value
        else:
            # Создаём
            setting = BotSettings(
                key=key,
                value=value,
                description=description,
            )
            session.add(setting)
            old_value = None
        
        # Логируем если указан admin_id
        if admin_id:
            await log_admin_action(
                admin_id=admin_id,
                action_type="setting_change",
                details={"key": key, "old_value": old_value, "new_value": value},
                session=session,
            )
        
        logger.info(
            "bot_setting_changed",
            key=key,
            value=value,
        )
        
        return True


async def get_all_bot_settings() -> Dict[str, str]:
    """
    Получить все настройки бота.
    
    Returns:
        Словарь {key: value}
    """
    async with get_session() as session:
        result = await session.execute(select(BotSettings))
        settings = result.scalars().all()
        return {s.key: s.value for s in settings}
