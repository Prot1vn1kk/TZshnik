"""
CRUD операции для тикетов техподдержки.

Содержит функции для:
- Создания тикетов
- Добавления сообщений
- Получения тикетов с сообщениями
- Обновления статусов
- Управления администраторами
- Статистики поддержки
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, desc, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.database import get_session
from database.models import SupportTicket, SupportMessage, User


logger = structlog.get_logger()


# ==================== TICKET CREATION ====================

async def create_support_ticket(
    user_id: int,
    category: str,
    description: str,
    sender_telegram_id: int,
    priority: str = "medium",
) -> SupportTicket:
    """
    Создать новый тикет поддержки.

    Args:
        user_id: ID пользователя из БД
        category: Категория тикета (payment, technical, other)
        description: Описание проблемы (первое сообщение)
        sender_telegram_id: Telegram ID отправителя
        priority: Приоритет (low, medium, high)

    Returns:
        Созданный объект SupportTicket
    """
    async with get_session() as session:
        # Создаём тикет
        ticket = SupportTicket(
            user_id=user_id,
            category=category,
            priority=priority,
            status="open",
        )
        session.add(ticket)
        await session.flush()

        # Создаём первое сообщение
        message = SupportMessage(
            ticket_id=ticket.id,
            sender_type="user",
            sender_telegram_id=sender_telegram_id,
            text=description,
        )
        session.add(message)

        await session.commit()
        await session.refresh(ticket)

        logger.info(
            "support_ticket_created",
            ticket_id=ticket.id,
            user_id=user_id,
            category=category,
        )

        return ticket


async def add_ticket_message(
    ticket_id: int,
    sender_type: str,
    sender_telegram_id: int,
    text: str,
) -> SupportMessage:
    """
    Добавить сообщение в существующий тикет.

    При отправке сообщения от администратора обновляет SLA метрики:
    - first_response_at: время первого ответа админа
    - last_admin_response_at: время последнего ответа админа
    - sla_breach: флаг нарушения SLA (если первый ответ > 24 часов)

    Args:
        ticket_id: ID тикета
        sender_type: 'user' или 'admin'
        sender_telegram_id: Telegram ID отправителя
        text: Текст сообщения

    Returns:
        Созданный объект SupportMessage
    """
    async with get_session() as session:
        # Получаем тикет для проверки SLA
        ticket_result = await session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()

        message = SupportMessage(
            ticket_id=ticket_id,
            sender_type=sender_type,
            sender_telegram_id=sender_telegram_id,
            text=text,
        )
        session.add(message)

        # Если это ответ админа, обновляем SLA метрики
        if ticket and sender_type == "admin":
            now = datetime.now()

            # Первый ответ админа
            if ticket.first_response_at is None:
                ticket.first_response_at = now

                # Проверяем нарушение SLA (24 часа)
                time_since_creation = (now - ticket.created_at).total_seconds()
                if time_since_creation > 24 * 3600:  # 24 часа в секундах
                    ticket.sla_breach = True
                    logger.warning(
                        "sla_breach_detected",
                        ticket_id=ticket_id,
                        hours_since_creation=time_since_creation / 3600,
                    )

            # Обновляем время последнего ответа админа
            ticket.last_admin_response_at = now

        await session.commit()
        await session.refresh(message)

        logger.info(
            "support_message_added",
            ticket_id=ticket_id,
            sender_type=sender_type,
        )

        return message


# ==================== TICKET RETRIEVAL ====================

async def get_ticket_with_messages(
    ticket_id: int,
) -> Optional[SupportTicket]:
    """
    Получить тикет со всеми сообщениями.

    Args:
        ticket_id: ID тикета

    Returns:
        Объект SupportTicket с загруженными сообщениями или None
    """
    async with get_session() as session:
        result = await session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .options(selectinload(SupportTicket.user))
            .where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()


async def get_user_tickets(
    user_id: int,
    status: Optional[str] = None,
    limit: int = 20,
) -> List[SupportTicket]:
    """
    Получить тикеты пользователя.

    Args:
        user_id: ID пользователя из БД
        status: Опциональный фильтр по статусу
        limit: Максимальное количество тикетов

    Returns:
        Список объектов SupportTicket
    """
    async with get_session() as session:
        query = (
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id)
            .order_by(desc(SupportTicket.created_at))
            .limit(limit)
        )

        if status:
            query = query.where(SupportTicket.status == status)

        result = await session.execute(query)
        return list(result.scalars().all())


async def get_tickets_paginated(
    page: int = 1,
    per_page: int = 10,
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_admin_id: Optional[int] = None,
) -> Tuple[List[SupportTicket], int]:
    """
    Получить тикеты с пагинацией и фильтрами (для админ-панели).

    Args:
        page: Номер страницы (начиная с 1)
        per_page: Элементов на странице
        status: Фильтр по статусу
        category: Фильтр по категории
        priority: Фильтр по приоритету
        assigned_admin_id: Фильтр по назначенному администратору

    Returns:
        Кортеж (список тикетов, общее количество)
    """
    async with get_session() as session:
        query = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.user))
            .options(selectinload(SupportTicket.messages))
        )
        count_query = select(func.count(SupportTicket.id))

        filters = []

        if status:
            filters.append(SupportTicket.status == status)
        if category:
            filters.append(SupportTicket.category == category)
        if priority:
            filters.append(SupportTicket.priority == priority)
        if assigned_admin_id is not None:
            filters.append(SupportTicket.assigned_admin_id == assigned_admin_id)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        query = query.order_by(desc(SupportTicket.created_at))

        # Пагинация
        offset = (page - 1) * per_page
        query = query.limit(per_page).offset(offset)

        tickets_result = await session.execute(query)
        count_result = await session.execute(count_query)

        tickets = list(tickets_result.scalars().all())
        total = count_result.scalar() or 0

        return tickets, total


# ==================== TICKET UPDATES ====================

async def update_ticket_status(
    ticket_id: int,
    status: str,
    admin_id: Optional[int] = None,
    resolution_notes: Optional[str] = None,
) -> bool:
    """
    Обновить статус тикета.

    Args:
        ticket_id: ID тикета
        status: Новый статус (open, in_progress, resolved, archived)
        admin_id: Telegram ID администратора, выполняющего обновление
        resolution_notes: Примечание о решении (для архивированных тикетов)

    Returns:
        True если успешно, иначе False
    """
    async with get_session() as session:
        values: Dict[str, Any] = {"status": status}

        if status == "resolved":
            values["resolved_at"] = datetime.now()
        elif status == "open":
            values["resolved_at"] = None

        if resolution_notes:
            values["resolution_notes"] = resolution_notes

        if admin_id is not None:
            values["assigned_admin_id"] = admin_id

        result = await session.execute(
            update(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .values(**values)
        )

        await session.commit()

        success = result.rowcount > 0

        if success:
            logger.info(
                "support_ticket_status_updated",
                ticket_id=ticket_id,
                new_status=status,
                admin_id=admin_id,
            )

        return success


async def assign_ticket_admin(
    ticket_id: int,
    admin_telegram_id: int,
) -> bool:
    """
    Назначить администратора на тикет.

    Args:
        ticket_id: ID тикета
        admin_telegram_id: Telegram ID администратора

    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .values(assigned_admin_id=admin_telegram_id)
        )

        await session.commit()

        success = result.rowcount > 0

        if success:
            logger.info(
                "support_ticket_assigned",
                ticket_id=ticket_id,
                admin_id=admin_telegram_id,
            )

        return success


async def toggle_ticket_importance(
    ticket_id: int,
) -> Optional[bool]:
    """
    Переключить флаг важности тикета.

    Args:
        ticket_id: ID тикета

    Returns:
        Новое значение флага или None
    """
    async with get_session() as session:
        result = await session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

        if not ticket:
            return None

        ticket.is_important = not ticket.is_important
        await session.commit()

        logger.info(
            "support_ticket_importance_toggled",
            ticket_id=ticket_id,
            new_value=ticket.is_important,
        )

        return ticket.is_important


async def archive_ticket(
    ticket_id: int,
    resolution_notes: Optional[str] = None,
) -> bool:
    """
    Архивировать тикет (статус resolved + archived).

    Args:
        ticket_id: ID тикета
        resolution_notes: Опциональное примечание о решении

    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .values(
                status="archived",
                resolved_at=datetime.now(),
                resolution_notes=resolution_notes,
            )
        )

        await session.commit()

        success = result.rowcount > 0

        if success:
            logger.info(
                "support_ticket_archived",
                ticket_id=ticket_id,
            )

        return success


async def delete_ticket(
    ticket_id: int,
) -> bool:
    """
    Удалить тикет (для неважных решённых тикетов).

    Args:
        ticket_id: ID тикета

    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            delete(SupportTicket).where(SupportTicket.id == ticket_id)
        )

        await session.commit()

        success = result.rowcount > 0

        if success:
            logger.info(
                "support_ticket_deleted",
                ticket_id=ticket_id,
            )

        return success


# ==================== STATISTICS ====================

async def get_support_stats() -> Dict[str, Any]:
    """
    Получить статистику тикетов поддержки.

    Включает SLA метрики:
    - avg_response_time: среднее время первого ответа (в часах)
    - sla_breach_count: количество нарушений SLA
    - sla_breach_rate: процент нарушений SLA

    Returns:
        Словарь со статистикой
    """
    async with get_session() as session:
        # Всего тикетов
        total_result = await session.execute(
            select(func.count(SupportTicket.id))
        )
        total = total_result.scalar() or 0

        # По статусам
        status_counts = {}
        for status in ["open", "in_progress", "resolved", "archived"]:
            result = await session.execute(
                select(func.count(SupportTicket.id))
                .where(SupportTicket.status == status)
            )
            status_counts[status] = result.scalar() or 0

        # По категориям
        category_result = await session.execute(
            select(
                SupportTicket.category,
                func.count(SupportTicket.id).label("count")
            )
            .group_by(SupportTicket.category)
        )
        category_counts = {row[0]: row[1] for row in category_result.all()}

        # Не назначенные тикеты
        unassigned_result = await session.execute(
            select(func.count(SupportTicket.id))
            .where(
                and_(
                    SupportTicket.status.in_(["open", "in_progress"]),
                    SupportTicket.assigned_admin_id.is_(None)
                )
            )
        )
        unassigned = unassigned_result.scalar() or 0

        # Важные нерешённые
        important_result = await session.execute(
            select(func.count(SupportTicket.id))
            .where(
                and_(
                    SupportTicket.is_important == True,  # noqa: E712
                    SupportTicket.status != "resolved"
                )
            )
        )
        important = important_result.scalar() or 0

        # SLA: Нарушения SLA
        sla_breach_result = await session.execute(
            select(func.count(SupportTicket.id))
            .where(SupportTicket.sla_breach == True)  # noqa: E712
        )
        sla_breach_count = sla_breach_result.scalar() or 0

        # SLA: Среднее время первого ответа (для тикетов с ответом)
        avg_response_result = await session.execute(
            select(
                func.avg(
                    func.cast(
                        SupportTicket.first_response_at - SupportTicket.created_at,
                        Float
                    )
                ) / 3600  # Конвертируем в часы
            )
            .where(SupportTicket.first_response_at.isnot(None))
        )
        avg_response_hours = avg_response_result.scalar() or 0

        return {
            "total": total,
            "by_status": status_counts,
            "by_category": category_counts,
            "unassigned": unassigned,
            "important_unresolved": important,
            "sla": {
                "breach_count": sla_breach_count,
                "breach_rate": round(sla_breach_count / total * 100, 1) if total > 0 else 0,
                "avg_response_hours": round(avg_response_hours, 1),
            },
        }
