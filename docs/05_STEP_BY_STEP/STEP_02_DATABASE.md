# 🗄 ШАГ 2: БАЗА ДАННЫХ

> Создание моделей SQLAlchemy и CRUD операций

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать:
- SQLAlchemy модели для всех сущностей
- Асинхронное подключение к SQLite
- CRUD операции для работы с данными
- Инициализацию БД при старте

---

## 📁 СТРУКТУРА ФАЙЛОВ

После этого шага:

```
database/
├── __init__.py
├── database.py          # Подключение и сессии
├── models.py            # SQLAlchemy модели
└── crud.py              # CRUD операции
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай модуль базы данных для Telegram-бота.

КОНТЕКСТ:
Бот "ТЗшник" генерирует ТЗ для инфографики товаров.
Нужно хранить: пользователей, генерации, платежи, фидбеки.

ТЕХНОЛОГИИ:
- SQLAlchemy 2.0 (async mode)
- aiosqlite (SQLite драйвер)
- Pydantic для валидации (опционально)

СХЕМА БД:
{Вставь содержимое docs/02_DATABASE_SCHEMA.md — секцию с ER-диаграммой и описанием таблиц}

ЗАДАЧА:
1. Создай database/database.py:
   - Async engine для SQLite
   - Async sessionmaker
   - Функция init_db() для создания таблиц
   - Context manager get_session() для работы с сессией

2. Создай database/models.py:
   - Базовый класс Base
   - Модель User (пользователи)
   - Модель Generation (сгенерированные ТЗ)
   - Модель GenerationPhoto (фото к генерации)
   - Модель Payment (платежи)
   - Модель Feedback (отзывы)
   - Все связи (relationships)
   - Правильные индексы

3. Создай database/crud.py:
   - get_user_by_telegram_id()
   - get_or_create_user()
   - get_user_balance()
   - decrease_balance()
   - increase_balance()
   - create_generation()
   - get_user_generations()
   - create_payment()
   - get_user_stats()

4. Обнови database/__init__.py с экспортами

ПРАВИЛА:
{Вставь правила из docs/01_RULES_FOR_AI.md — секции про БД и async}

ТРЕБОВАНИЯ:
1. Все операции async
2. Используй context manager для сессий
3. Type hints везде
4. Docstrings на русском
5. Обработка ошибок с rollback
6. Индексы на часто используемых полях (telegram_id, user_id)

ПРИМЕР ИСПОЛЬЗОВАНИЯ (для понимания API):
```python
# Получить или создать пользователя
user, created = await get_or_create_user(
    telegram_id=123456789,
    username="john_doe",
    first_name="John"
)

# Проверить баланс
balance = await get_user_balance(telegram_id=123456789)

# Списать кредит
success = await decrease_balance(telegram_id=123456789, amount=1)

# Создать генерацию
generation = await create_generation(
    user_id=user.id,
    category="electronics",
    photo_analysis="Описание товара...",
    tz_text="Полное ТЗ...",
    quality_score=85,
    photo_file_ids=[("file_id_1", "unique_id_1"), ("file_id_2", "unique_id_2")],
    is_free=True
)

# Получить историю
generations = await get_user_generations(telegram_id=123456789, limit=10)
```

Создай полный код всех файлов.
```

---

## 📦 ОЖИДАЕМЫЕ ФАЙЛЫ

### database/database.py

```python
"""
Подключение к базе данных и управление сессиями.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)

from bot.config import settings
from database.models import Base

# Создаём директорию для БД
Path("data").mkdir(exist_ok=True)

# Async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

# Фабрика сессий
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def init_db() -> None:
    """
    Инициализация базы данных.
    Создаёт все таблицы если их нет.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Закрытие соединения с БД."""
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для работы с сессией БД.
    
    Автоматически делает commit при успехе и rollback при ошибке.
    
    Использование:
        async with get_session() as session:
            result = await session.execute(query)
    """
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

### database/models.py

```python
"""
SQLAlchemy модели базы данных.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Index
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """
    Модель пользователя.
    
    Хранит информацию о пользователе Telegram,
    его балансе и статистике.
    """
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    
    # Telegram данные
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, 
        unique=True, 
        nullable=False,
        index=True
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    
    # Баланс и статистика
    balance: Mapped[int] = mapped_column(
        Integer, 
        default=1  # 1 бесплатное ТЗ при регистрации
    )
    total_generated: Mapped[int] = mapped_column(
        Integer, 
        default=0
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean, 
        default=False
    )
    
    # Реферальная система
    referred_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    generations: Mapped[List["Generation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Self-referential для рефералов
    referrals: Mapped[List["User"]] = relationship(
        back_populates="referrer",
        foreign_keys="User.referred_by"
    )
    referrer: Mapped[Optional["User"]] = relationship(
        back_populates="referrals",
        foreign_keys=[referred_by],
        remote_side=[id]
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, tg={self.telegram_id}, balance={self.balance})>"


class Generation(Base):
    """
    Модель сгенерированного ТЗ.
    
    Хранит результат генерации: анализ фото, 
    готовое ТЗ и метаданные.
    """
    
    __tablename__ = "generations"
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Данные генерации
    category: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )
    photo_analysis: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    tz_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    
    # Качество и статус
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True
    )
    regenerations: Mapped[int] = mapped_column(
        Integer, 
        default=0
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean, 
        default=False
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="generations"
    )
    photos: Mapped[List["GenerationPhoto"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    feedback: Mapped[Optional["Feedback"]] = relationship(
        back_populates="generation",
        uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<Generation(id={self.id}, cat={self.category}, score={self.quality_score})>"


class GenerationPhoto(Base):
    """
    Фотографии, использованные для генерации.
    
    Хранит Telegram file_id для возможности
    повторного скачивания.
    """
    
    __tablename__ = "generation_photos"
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    generation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Telegram file IDs
    file_id: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    file_unique_id: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    
    # Relationship
    generation: Mapped["Generation"] = relationship(
        back_populates="photos"
    )


class Payment(Base):
    """
    Модель платежа.
    
    Хранит информацию об оплате пакета кредитов.
    """
    
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Данные платежа Telegram
    telegram_payment_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )
    
    # Сумма и валюта
    amount: Mapped[int] = mapped_column(
        Integer, 
        nullable=False  # В копейках!
    )
    currency: Mapped[str] = mapped_column(
        String(3), 
        default="RUB"
    )
    
    # Что получил пользователь
    credits_added: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    package_name: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )
    
    # Статус
    status: Mapped[str] = mapped_column(
        String(20), 
        default="completed"
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    
    # Relationship
    user: Mapped["User"] = relationship(
        back_populates="payments"
    )
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, credits={self.credits_added})>"


class Feedback(Base):
    """
    Обратная связь по сгенерированному ТЗ.
    
    Позволяет оценить качество генерации.
    """
    
    __tablename__ = "feedbacks"
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    generation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # Один фидбек на генерацию
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Оценка: 1 = 👍, 0 = 👎
    rating: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
    
    # Relationship
    generation: Mapped["Generation"] = relationship(
        back_populates="feedback"
    )


# Дополнительные индексы
Index("ix_generations_user_created", Generation.user_id, Generation.created_at.desc())
Index("ix_payments_user_created", Payment.user_id, Payment.created_at.desc())
```

### database/crud.py

```python
"""
CRUD операции для работы с базой данных.
"""

from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_session
from database.models import User, Generation, GenerationPhoto, Payment, Feedback


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
    referred_by_telegram_id: Optional[int] = None
) -> Tuple[User, bool]:
    """
    Получить существующего или создать нового пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        username: Username в Telegram
        first_name: Имя пользователя
        referred_by_telegram_id: Telegram ID реферера
        
    Returns:
        Tuple[User, created]: Пользователь и флаг создания
    """
    async with get_session() as session:
        # Ищем существующего
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
                await session.commit()
            
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
            referred_by=referred_by_id
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        
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
                User.balance >= amount
            )
            .values(balance=User.balance - amount)
        )
        return result.rowcount > 0


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
        return result.rowcount > 0


async def increment_total_generated(telegram_id: int) -> None:
    """Увеличить счётчик сгенерированных ТЗ."""
    async with get_session() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(total_generated=User.total_generated + 1)
        )


# ==================== GENERATIONS ====================

async def create_generation(
    user_id: int,
    category: str,
    photo_analysis: str,
    tz_text: str,
    quality_score: int,
    photo_file_ids: List[Tuple[str, str]],
    is_free: bool = False
) -> Generation:
    """
    Создать запись о генерации ТЗ.
    
    Args:
        user_id: ID пользователя в БД (не telegram_id!)
        category: Категория товара
        photo_analysis: Результат анализа фото
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
            is_free=is_free
        )
        session.add(generation)
        await session.flush()
        
        # Добавляем фотографии
        for file_id, file_unique_id in photo_file_ids:
            photo = GenerationPhoto(
                generation_id=generation.id,
                file_id=file_id,
                file_unique_id=file_unique_id
            )
            session.add(photo)
        
        await session.refresh(generation)
        return generation


async def get_user_generations(
    telegram_id: int,
    limit: int = 10,
    offset: int = 0
) -> List[Generation]:
    """
    Получить историю генераций пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество записей
        offset: Смещение для пагинации
        
    Returns:
        Список генераций (от новых к старым)
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


async def get_generation_by_id(generation_id: int) -> Optional[Generation]:
    """Получить генерацию по ID."""
    async with get_session() as session:
        result = await session.execute(
            select(Generation).where(Generation.id == generation_id)
        )
        return result.scalar_one_or_none()


async def increment_regenerations(generation_id: int) -> int:
    """
    Увеличить счётчик перегенераций.
    
    Returns:
        Новое значение счётчика
    """
    async with get_session() as session:
        # Получаем текущее значение
        result = await session.execute(
            select(Generation.regenerations)
            .where(Generation.id == generation_id)
        )
        current = result.scalar_one_or_none() or 0
        
        # Увеличиваем
        await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(regenerations=current + 1)
        )
        
        return current + 1


async def update_generation_tz(
    generation_id: int,
    tz_text: str,
    quality_score: int
) -> bool:
    """Обновить ТЗ после перегенерации."""
    async with get_session() as session:
        result = await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(tz_text=tz_text, quality_score=quality_score)
        )
        return result.rowcount > 0


# ==================== PAYMENTS ====================

async def create_payment(
    user_id: int,
    telegram_payment_id: str,
    amount: int,
    credits_added: int,
    package_name: str,
    currency: str = "RUB"
) -> Payment:
    """
    Создать запись о платеже.
    
    Args:
        user_id: ID пользователя в БД
        telegram_payment_id: ID платежа от Telegram
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
            currency=currency
        )
        session.add(payment)
        await session.flush()
        await session.refresh(payment)
        return payment


async def get_user_payments(
    telegram_id: int,
    limit: int = 10
) -> List[Payment]:
    """Получить историю платежей пользователя."""
    async with get_session() as session:
        result = await session.execute(
            select(Payment)
            .join(User)
            .where(User.telegram_id == telegram_id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


# ==================== FEEDBACKS ====================

async def create_feedback(
    generation_id: int,
    user_id: int,
    rating: int,
    comment: Optional[str] = None
) -> Feedback:
    """
    Создать отзыв о генерации.
    
    Args:
        generation_id: ID генерации
        user_id: ID пользователя в БД
        rating: Оценка (1 = 👍, 0 = 👎)
        comment: Комментарий
        
    Returns:
        Созданный объект Feedback
    """
    async with get_session() as session:
        feedback = Feedback(
            generation_id=generation_id,
            user_id=user_id,
            rating=rating,
            comment=comment
        )
        session.add(feedback)
        await session.flush()
        await session.refresh(feedback)
        return feedback


async def has_feedback(generation_id: int) -> bool:
    """Проверить есть ли уже отзыв на генерацию."""
    async with get_session() as session:
        result = await session.execute(
            select(Feedback.id).where(Feedback.generation_id == generation_id)
        )
        return result.scalar_one_or_none() is not None


# ==================== STATISTICS ====================

async def get_user_stats(telegram_id: int) -> dict:
    """
    Получить статистику пользователя.
    
    Returns:
        Словарь со статистикой:
        - balance: текущий баланс
        - total_generated: всего сгенерировано
        - generations_this_month: за последний месяц
        - total_spent_rub: потрачено денег (в рублях)
        - is_premium: премиум статус
        - member_since: дата регистрации
    """
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        # Генерации за последний месяц
        month_ago = datetime.utcnow() - timedelta(days=30)
        gen_result = await session.execute(
            select(func.count(Generation.id))
            .where(
                Generation.user_id == user.id,
                Generation.created_at >= month_ago
            )
        )
        generations_this_month = gen_result.scalar() or 0
        
        # Общая сумма платежей
        pay_result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.user_id == user.id)
        )
        total_spent = pay_result.scalar() or 0
        
        return {
            "balance": user.balance,
            "total_generated": user.total_generated,
            "generations_this_month": generations_this_month,
            "total_spent_rub": total_spent / 100,  # Из копеек в рубли
            "is_premium": user.is_premium,
            "member_since": user.created_at
        }


async def get_admin_stats() -> dict:
    """
    Получить статистику для админа.
    
    Returns:
        - total_users: всего пользователей
        - total_generations: всего генераций
        - total_revenue: общая выручка (рубли)
        - users_today: новых пользователей за сегодня
    """
    async with get_session() as session:
        # Всего пользователей
        users_result = await session.execute(select(func.count(User.id)))
        total_users = users_result.scalar() or 0
        
        # Всего генераций
        gen_result = await session.execute(select(func.count(Generation.id)))
        total_generations = gen_result.scalar() or 0
        
        # Общая выручка
        rev_result = await session.execute(select(func.sum(Payment.amount)))
        total_revenue = (rev_result.scalar() or 0) / 100
        
        # Новые пользователи за сегодня
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_result = await session.execute(
            select(func.count(User.id))
            .where(User.created_at >= today_start)
        )
        users_today = today_result.scalar() or 0
        
        return {
            "total_users": total_users,
            "total_generations": total_generations,
            "total_revenue": total_revenue,
            "users_today": users_today
        }
```

### database/__init__.py

```python
"""
Модуль базы данных.
"""

from database.database import init_db, close_db, get_session
from database.models import User, Generation, GenerationPhoto, Payment, Feedback
from database import crud

__all__ = [
    # Database
    "init_db",
    "close_db", 
    "get_session",
    
    # Models
    "User",
    "Generation",
    "GenerationPhoto",
    "Payment",
    "Feedback",
    
    # CRUD
    "crud"
]
```

---

## ✅ ЧЕКЛИСТ ВЫПОЛНЕНИЯ

- [ ] Все файлы созданы в папке `database/`
- [ ] `init_db()` создаёт таблицы без ошибок
- [ ] `get_or_create_user()` работает корректно
- [ ] `decrease_balance()` не уходит в минус
- [ ] `create_generation()` сохраняет фото
- [ ] Тесты проходят

---

## 🧪 ТЕСТИРОВАНИЕ

```python
# tests/test_database.py
import pytest
from database import crud, init_db

@pytest.mark.asyncio
async def test_create_user():
    await init_db()
    
    user, created = await crud.get_or_create_user(
        telegram_id=123456789,
        username="test_user"
    )
    
    assert created is True
    assert user.telegram_id == 123456789
    assert user.balance == 1  # Бесплатное ТЗ


@pytest.mark.asyncio
async def test_balance_operations():
    user, _ = await crud.get_or_create_user(telegram_id=999)
    
    # Начальный баланс
    balance = await crud.get_user_balance(telegram_id=999)
    assert balance == 1
    
    # Списание
    success = await crud.decrease_balance(telegram_id=999, amount=1)
    assert success is True
    
    # Нельзя списать больше чем есть
    success = await crud.decrease_balance(telegram_id=999, amount=1)
    assert success is False
```

---

## ➡️ СЛЕДУЮЩИЙ ШАГ

После успешного выполнения переходи к [STEP_03_AI_PROVIDERS.md](STEP_03_AI_PROVIDERS.md)

---

*Шаг 2 из 7*
