"""
CRUD операции для работы с базой данных.

Все функции асинхронные и используют get_session() для
безопасной работы с транзакциями.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import desc, func, select, update

from database.database import get_session
from database.models import Feedback, Generation, GenerationPhoto, Payment, User


# Логгер
logger = structlog.get_logger()


# ==================== USERS ====================

async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """
    Получить пользователя по Telegram ID.
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        User или None если не найден
    """
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referred_by_telegram_id: Optional[int] = None,
) -> Tuple[User, bool]:
    """
    Получить существующего или создать нового пользователя.
    
    При создании нового пользователя начисляется 1 бесплатный кредит.
    Если указан реферер, устанавливается связь.
    
    Args:
        telegram_id: ID пользователя в Telegram
        username: Username в Telegram
        first_name: Имя пользователя
        referred_by_telegram_id: Telegram ID реферера
        
    Returns:
        Tuple[User, created]: Пользователь и флаг (True если создан)
    """
    async with get_session() as session:
        # Ищем существующего пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем данные если изменились
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            
            if updated:
                logger.debug(
                    "user_updated",
                    telegram_id=telegram_id,
                    username=username,
                )
            
            return user, False
        
        # Ищем реферера если указан
        referred_by_id = None
        if referred_by_telegram_id:
            referrer_result = await session.execute(
                select(User.id).where(User.telegram_id == referred_by_telegram_id)
            )
            referred_by_id = referrer_result.scalar_one_or_none()
        
        # Создаём нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            referred_by=referred_by_id,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        
        logger.info(
            "user_created",
            telegram_id=telegram_id,
            username=username,
            referred_by=referred_by_id,
        )
        
        return user, True


async def get_user_balance(telegram_id: int) -> int:
    """
    Получить баланс пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Баланс в кредитах (0 если пользователь не найден)
    """
    async with get_session() as session:
        result = await session.execute(
            select(User.balance).where(User.telegram_id == telegram_id)
        )
        balance = result.scalar_one_or_none()
        return balance if balance is not None else 0


async def decrease_balance(telegram_id: int, amount: int = 1) -> bool:
    """
    Списать кредиты с баланса пользователя.
    
    Атомарная операция: списание происходит только если
    баланс достаточен.
    
    Args:
        telegram_id: ID пользователя в Telegram
        amount: Количество кредитов для списания
        
    Returns:
        True если списание успешно, False если недостаточно средств
    """
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(
                User.telegram_id == telegram_id,
                User.balance >= amount,
            )
            .values(balance=User.balance - amount)
        )
        
        success = result.rowcount > 0
        
        if success:
            logger.info(
                "balance_decreased",
                telegram_id=telegram_id,
                amount=amount,
            )
        else:
            logger.warning(
                "balance_decrease_failed",
                telegram_id=telegram_id,
                amount=amount,
            )
        
        return success


async def increase_balance(telegram_id: int, amount: int) -> bool:
    """
    Пополнить баланс пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        amount: Количество кредитов для начисления
        
    Returns:
        True если успешно, False если пользователь не найден
    """
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(balance=User.balance + amount)
        )
        
        success = result.rowcount > 0
        
        if success:
            logger.info(
                "balance_increased",
                telegram_id=telegram_id,
                amount=amount,
            )
        
        return success


async def increment_total_generated(telegram_id: int) -> None:
    """
    Увеличить счётчик сгенерированных ТЗ.
    
    Args:
        telegram_id: ID пользователя в Telegram
    """
    async with get_session() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(total_generated=User.total_generated + 1)
        )


async def set_user_premium(telegram_id: int, is_premium: bool = True) -> bool:
    """
    Установить премиум-статус пользователю.
    
    Args:
        telegram_id: ID пользователя в Telegram
        is_premium: Флаг премиум-статуса
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_premium=is_premium)
        )
        return result.rowcount > 0


# ==================== GENERATIONS ====================

async def create_generation(
    user_id: int,
    category: str,
    photo_analysis: str,
    tz_text: str,
    quality_score: int,
    photo_file_ids: List[Tuple[str, str]],
    is_free: bool = False,
) -> Generation:
    """
    Создать запись о генерации ТЗ.
    
    Args:
        user_id: ID пользователя в БД (не telegram_id!)
        category: Категория товара
        photo_analysis: Результат анализа фото Vision AI
        tz_text: Сгенерированное ТЗ
        quality_score: Оценка качества (0-100)
        photo_file_ids: Список кортежей (file_id, file_unique_id)
        is_free: Бесплатная генерация
        
    Returns:
        Созданный объект Generation
    """
    async with get_session() as session:
        # Создаём генерацию
        generation = Generation(
            user_id=user_id,
            category=category,
            photo_analysis=photo_analysis,
            tz_text=tz_text,
            quality_score=quality_score,
            is_free=is_free,
        )
        session.add(generation)
        await session.flush()
        
        # Добавляем фотографии
        for file_id, file_unique_id in photo_file_ids:
            photo = GenerationPhoto(
                generation_id=generation.id,
                file_id=file_id,
                file_unique_id=file_unique_id,
            )
            session.add(photo)
        
        await session.refresh(generation)
        
        logger.info(
            "generation_created",
            generation_id=generation.id,
            user_id=user_id,
            category=category,
            quality_score=quality_score,
            photos_count=len(photo_file_ids),
        )
        
        return generation


async def get_generation_by_id(generation_id: int) -> Optional[Generation]:
    """
    Получить генерацию по ID.
    
    Args:
        generation_id: ID генерации
        
    Returns:
        Generation или None
    """
    async with get_session() as session:
        result = await session.execute(
            select(Generation).where(Generation.id == generation_id)
        )
        return result.scalar_one_or_none()


async def get_user_generations(
    telegram_id: int,
    limit: int = 10,
    offset: int = 0,
) -> List[Generation]:
    """
    Получить историю генераций пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество записей
        offset: Смещение для пагинации
        
    Returns:
        Список генераций, отсортированных по дате (новые первые)
    """
    async with get_session() as session:
        result = await session.execute(
            select(Generation)
            .join(User)
            .where(User.telegram_id == telegram_id)
            .order_by(desc(Generation.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


async def get_user_generations_count(telegram_id: int) -> int:
    """
    Получить количество генераций пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Количество генераций
    """
    async with get_session() as session:
        result = await session.execute(
            select(func.count(Generation.id))
            .join(User)
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar() or 0


async def increment_regenerations(generation_id: int) -> bool:
    """
    Увеличить счётчик перегенераций.
    
    Args:
        generation_id: ID генерации
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(regenerations=Generation.regenerations + 1)
        )
        return result.rowcount > 0


async def update_generation_tz(
    generation_id: int,
    tz_text: str,
    quality_score: int,
) -> bool:
    """
    Обновить ТЗ при перегенерации.
    
    Args:
        generation_id: ID генерации
        tz_text: Новый текст ТЗ
        quality_score: Новая оценка качества
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(
                tz_text=tz_text,
                quality_score=quality_score,
                regenerations=Generation.regenerations + 1,
            )
        )
        return result.rowcount > 0


async def update_generation_status(
    generation_id: int,
    status: str,
    result_text: Optional[str] = None,
    vision_analysis: Optional[str] = None,
    quality_score: Optional[int] = None,
    error_message: Optional[str] = None,
) -> bool:
    """
    Обновить статус генерации.
    
    Args:
        generation_id: ID генерации
        status: Новый статус (pending, completed, failed)
        result_text: Результат ТЗ
        vision_analysis: Результат анализа изображений
        quality_score: Оценка качества
        error_message: Сообщение об ошибке
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        values: dict[str, object] = {"status": status}
        
        if result_text is not None:
            values["tz_text"] = result_text
        if vision_analysis is not None:
            values["photo_analysis"] = vision_analysis
        if quality_score is not None:
            values["quality_score"] = quality_score
        
        result = await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(**values)
        )
        
        logger.info(
            "generation_status_updated",
            generation_id=generation_id,
            status=status,
        )
        
        return result.rowcount > 0


# ==================== PAYMENTS ====================

async def create_payment(
    user_id: int,
    telegram_payment_id: str,
    amount: int,
    credits_added: int,
    package_name: str,
    currency: str = "RUB",
) -> Payment:
    """
    Создать запись о платеже.
    
    Args:
        user_id: ID пользователя в БД
        telegram_payment_id: ID платежа в Telegram
        amount: Сумма в копейках
        credits_added: Количество начисленных кредитов
        package_name: Название пакета
        currency: Валюта
        
    Returns:
        Созданный объект Payment
    """
    async with get_session() as session:
        payment = Payment(
            user_id=user_id,
            telegram_payment_id=telegram_payment_id,
            amount=amount,
            credits_added=credits_added,
            package_name=package_name,
            currency=currency,
        )
        session.add(payment)
        await session.flush()
        await session.refresh(payment)
        
        logger.info(
            "payment_created",
            payment_id=payment.id,
            user_id=user_id,
            amount=amount,
            credits=credits_added,
            package=package_name,
        )
        
        return payment


async def get_user_payments(
    telegram_id: int,
    limit: int = 10,
) -> List[Payment]:
    """
    Получить историю платежей пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество записей
        
    Returns:
        Список платежей
    """
    async with get_session() as session:
        result = await session.execute(
            select(Payment)
            .join(User)
            .where(User.telegram_id == telegram_id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_total_revenue() -> int:
    """
    Получить общую сумму платежей (для админа).
    
    Returns:
        Сумма в копейках
    """
    async with get_session() as session:
        result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "completed")
        )
        return result.scalar() or 0


async def update_payment_status(
    payment_id: int,
    status: str,
) -> bool:
    """
    Обновить статус платежа.
    
    Args:
        payment_id: ID платежа
        status: Новый статус (pending, completed, failed)
        
    Returns:
        True если успешно
    """
    async with get_session() as session:
        result = await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status=status)
        )
        
        logger.info(
            "payment_status_updated",
            payment_id=payment_id,
            status=status,
        )
        
        return result.rowcount > 0


# ==================== FEEDBACK ====================

async def create_feedback(
    generation_id: int,
    user_id: int,
    rating: int,
    comment: Optional[str] = None,
) -> Feedback:
    """
    Создать отзыв о генерации.
    
    Args:
        generation_id: ID генерации
        user_id: ID пользователя в БД
        rating: Оценка (1 = 👍, 0 = 👎)
        comment: Текстовый комментарий
        
    Returns:
        Созданный объект Feedback
    """
    async with get_session() as session:
        feedback = Feedback(
            generation_id=generation_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )
        session.add(feedback)
        await session.flush()
        await session.refresh(feedback)
        
        logger.info(
            "feedback_created",
            generation_id=generation_id,
            rating=rating,
        )
        
        return feedback


async def get_feedback_stats() -> dict:
    """
    Получить статистику отзывов (для админа).
    
    Returns:
        Словарь со статистикой
    """
    async with get_session() as session:
        # Всего отзывов
        total_result = await session.execute(
            select(func.count(Feedback.id))
        )
        total = total_result.scalar() or 0
        
        # Положительных
        positive_result = await session.execute(
            select(func.count(Feedback.id))
            .where(Feedback.rating == 1)
        )
        positive = positive_result.scalar() or 0
        
        return {
            "total": total,
            "positive": positive,
            "negative": total - positive,
            "positive_rate": (positive / total * 100) if total > 0 else 0,
        }


# ==================== STATISTICS ====================

async def get_user_stats(telegram_id: int) -> dict:
    """
    Получить статистику пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Словарь со статистикой
    """
    async with get_session() as session:
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return {}
        
        # Количество генераций
        gen_count_result = await session.execute(
            select(func.count(Generation.id))
            .where(Generation.user_id == user.id)
        )
        generations_count = gen_count_result.scalar() or 0
        
        # Сумма платежей
        payments_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.user_id == user.id)
        )
        total_paid = payments_result.scalar() or 0
        
        return {
            "telegram_id": telegram_id,
            "username": user.username,
            "balance": user.balance,
            "total_generated": user.total_generated,
            "generations_count": generations_count,
            "is_premium": user.is_premium,
            "total_paid_rub": total_paid / 100,  # Конвертируем в рубли
            "member_since": user.created_at,
        }


async def get_admin_stats() -> dict:
    """
    Получить общую статистику (для админа).
    
    Returns:
        Словарь со статистикой
    """
    async with get_session() as session:
        # Всего пользователей
        users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = users_result.scalar() or 0
        
        # Новых за сегодня
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        new_today_result = await session.execute(
            select(func.count(User.id))
            .where(User.created_at >= today)
        )
        new_today = new_today_result.scalar() or 0
        
        # Всего генераций
        generations_result = await session.execute(
            select(func.count(Generation.id))
        )
        total_generations = generations_result.scalar() or 0
        
        # Выручка
        revenue_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.status == "completed")
        )
        total_revenue = revenue_result.scalar() or 0
        
        # Средняя оценка качества
        avg_score_result = await session.execute(
            select(func.avg(Generation.quality_score))
            .where(Generation.quality_score.isnot(None))
        )
        avg_quality = avg_score_result.scalar() or 0
        
        return {
            "total_users": total_users,
            "new_users_today": new_today,
            "total_generations": total_generations,
            "total_revenue_rub": total_revenue / 100,
            "avg_quality_score": round(avg_quality, 1),
        }
