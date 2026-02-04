# 🗄 СХЕМА БАЗЫ ДАННЫХ

> SQLite + SQLAlchemy 2.0 (async)

---

## 📊 ER-ДИАГРАММА

```
┌─────────────────────────────────────────────────────────────────────┐
│                              USERS                                   │
├─────────────────────────────────────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY AUTOINCREMENT                   │
│ telegram_id     BIGINT UNIQUE NOT NULL                              │
│ username        VARCHAR(255) NULLABLE                               │
│ first_name      VARCHAR(255) NULLABLE                               │
│ balance         INTEGER DEFAULT 1 (бесплатные ТЗ)                   │
│ total_generated INTEGER DEFAULT 0                                   │
│ is_premium      BOOLEAN DEFAULT FALSE                               │
│ referred_by     INTEGER NULLABLE (FK → users.id)                    │
│ created_at      DATETIME DEFAULT NOW                                │
│ updated_at      DATETIME DEFAULT NOW ON UPDATE                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           GENERATIONS                                │
├─────────────────────────────────────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY AUTOINCREMENT                   │
│ user_id         INTEGER NOT NULL (FK → users.id)                    │
│ category        VARCHAR(50) NOT NULL                                │
│ photo_analysis  TEXT NOT NULL (результат Vision)                   │
│ tz_text         TEXT NOT NULL (полное ТЗ)                          │
│ quality_score   INTEGER (0-100, от валидатора)                      │
│ regenerations   INTEGER DEFAULT 0                                   │
│ is_free         BOOLEAN DEFAULT FALSE                               │
│ created_at      DATETIME DEFAULT NOW                                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         GENERATION_PHOTOS                            │
├─────────────────────────────────────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY AUTOINCREMENT                   │
│ generation_id   INTEGER NOT NULL (FK → generations.id)              │
│ file_id         VARCHAR(255) NOT NULL (Telegram file_id)           │
│ file_unique_id  VARCHAR(255) NOT NULL                               │
│ created_at      DATETIME DEFAULT NOW                                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                            PAYMENTS                                  │
├─────────────────────────────────────────────────────────────────────┤
│ id                    INTEGER PRIMARY KEY AUTOINCREMENT             │
│ user_id               INTEGER NOT NULL (FK → users.id)              │
│ telegram_payment_id   VARCHAR(255) UNIQUE NOT NULL                  │
│ amount                INTEGER NOT NULL (в копейках)                 │
│ currency              VARCHAR(3) DEFAULT 'RUB'                      │
│ credits_added         INTEGER NOT NULL                              │
│ package_name          VARCHAR(50) NOT NULL                          │
│ status                VARCHAR(20) DEFAULT 'completed'               │
│ created_at            DATETIME DEFAULT NOW                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                            FEEDBACKS                                 │
├─────────────────────────────────────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY AUTOINCREMENT                   │
│ generation_id   INTEGER NOT NULL (FK → generations.id)              │
│ user_id         INTEGER NOT NULL (FK → users.id)                    │
│ rating          INTEGER NOT NULL (1-5 или 1=👍, 0=👎)               │
│ comment         TEXT NULLABLE                                       │
│ created_at      DATETIME DEFAULT NOW                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🐍 SQLALCHEMY МОДЕЛИ

```python
# database/models.py

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, 
    Integer, String, Text, func
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Модель пользователя."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Баланс и статистика
    balance: Mapped[int] = mapped_column(Integer, default=1)  # 1 бесплатное ТЗ
    total_generated: Mapped[int] = mapped_column(Integer, default=0)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    
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
        cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
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
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, balance={self.balance})>"


class Generation(Base):
    """Модель сгенерированного ТЗ."""
    
    __tablename__ = "generations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Данные генерации
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    photo_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    tz_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Качество и статус
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    regenerations: Mapped[int] = mapped_column(Integer, default=0)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="generations")
    photos: Mapped[List["GenerationPhoto"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan"
    )
    feedback: Mapped[Optional["Feedback"]] = relationship(
        back_populates="generation",
        uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<Generation(id={self.id}, category={self.category}, score={self.quality_score})>"


class GenerationPhoto(Base):
    """Фотографии, использованные для генерации."""
    
    __tablename__ = "generation_photos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generation_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("generations.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # Telegram file IDs
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_unique_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now()
    )
    
    # Relationship
    generation: Mapped["Generation"] = relationship(back_populates="photos")


class Payment(Base):
    """Модель платежа."""
    
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Данные платежа
    telegram_payment_id: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # В копейках
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    
    # Что получил пользователь
    credits_added: Mapped[int] = mapped_column(Integer, nullable=False)
    package_name: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default="completed")
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now()
    )
    
    # Relationship
    user: Mapped["User"] = relationship(back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, credits={self.credits_added})>"


class Feedback(Base):
    """Обратная связь по ТЗ."""
    
    __tablename__ = "feedbacks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    
    # Оценка (1 = 👍, 0 = 👎)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now()
    )
    
    # Relationship
    generation: Mapped["Generation"] = relationship(back_populates="feedback")
```

---

## 🔧 ИНИЦИАЛИЗАЦИЯ БД

```python
# database/database.py

from contextlib import asynccontextmanager
from pathlib import Path
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker
)
from database.models import Base
from bot.config import settings

# Создаём папку для БД если не существует
Path("data").mkdir(exist_ok=True)

# Создание engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # SQL логи в debug режиме
    future=True
)

# Фабрика сессий
async_session = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def init_db() -> None:
    """Инициализация базы данных (создание таблиц)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Закрытие соединения с БД."""
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncSession:
    """
    Контекстный менеджер для работы с сессией БД.
    
    Использование:
        async with get_session() as session:
            user = await session.get(User, user_id)
    """
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

---

## 📝 CRUD ОПЕРАЦИИ

```python
# database/crud.py

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Generation, Payment, Feedback, GenerationPhoto
from database.database import get_session


# ==================== USERS ====================

async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def get_or_create_user(
    telegram_id: int, 
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referred_by: Optional[int] = None
) -> tuple[User, bool]:
    """
    Получить или создать пользователя.
    
    Returns:
        (User, created): Кортеж с пользователем и флагом создания
    """
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем данные если изменились
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            return user, False
        
        # Создаём нового
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            referred_by=referred_by
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user, True


async def get_user_balance(telegram_id: int) -> int:
    """Получить баланс пользователя."""
    async with get_session() as session:
        result = await session.execute(
            select(User.balance).where(User.telegram_id == telegram_id)
        )
        balance = result.scalar_one_or_none()
        return balance or 0


async def decrease_balance(telegram_id: int, amount: int = 1) -> bool:
    """
    Списать кредиты с баланса.
    
    Returns:
        True если списание успешно, False если недостаточно средств
    """
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id, User.balance >= amount)
            .values(balance=User.balance - amount)
        )
        return result.rowcount > 0


async def increase_balance(telegram_id: int, amount: int) -> bool:
    """Пополнить баланс пользователя."""
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
    photo_file_ids: List[tuple[str, str]],  # [(file_id, file_unique_id), ...]
    is_free: bool = False
) -> Generation:
    """Создать запись о генерации."""
    async with get_session() as session:
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
    """Получить историю генераций пользователя."""
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
    """Увеличить счётчик перегенераций и вернуть новое значение."""
    async with get_session() as session:
        result = await session.execute(
            select(Generation.regenerations)
            .where(Generation.id == generation_id)
        )
        current = result.scalar_one_or_none() or 0
        
        await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(regenerations=current + 1)
        )
        return current + 1


# ==================== PAYMENTS ====================

async def create_payment(
    user_id: int,
    telegram_payment_id: str,
    amount: int,
    credits_added: int,
    package_name: str,
    currency: str = "RUB"
) -> Payment:
    """Создать запись о платеже."""
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
    """Создать отзыв о генерации."""
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


# ==================== STATISTICS ====================

async def get_user_stats(telegram_id: int) -> dict:
    """Получить статистику пользователя."""
    async with get_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        # Считаем генерации за последний месяц
        month_ago = datetime.utcnow() - timedelta(days=30)
        result = await session.execute(
            select(func.count(Generation.id))
            .where(
                Generation.user_id == user.id,
                Generation.created_at >= month_ago
            )
        )
        generations_this_month = result.scalar() or 0
        
        # Общая сумма платежей
        result = await session.execute(
            select(func.sum(Payment.amount))
            .where(Payment.user_id == user.id)
        )
        total_spent = result.scalar() or 0
        
        return {
            "balance": user.balance,
            "total_generated": user.total_generated,
            "generations_this_month": generations_this_month,
            "total_spent_rub": total_spent / 100,  # Из копеек в рубли
            "is_premium": user.is_premium,
            "member_since": user.created_at
        }
```

---

## 📦 ПАКЕТЫ И ЦЕНЫ

```python
# bot/packages.py

from dataclasses import dataclass
from typing import Dict


@dataclass
class Package:
    """Пакет кредитов."""
    name: str
    credits: int
    price_rub: int  # В рублях
    description: str
    is_subscription: bool = False


# Доступные пакеты
PACKAGES: Dict[str, Package] = {
    "start": Package(
        name="Старт",
        credits=5,
        price_rub=149,
        description="5 ТЗ — для тестирования"
    ),
    "optimal": Package(
        name="Оптимальный",
        credits=20,
        price_rub=399,
        description="20 ТЗ — самый популярный"
    ),
    "pro": Package(
        name="Профи",
        credits=50,
        price_rub=699,
        description="50 ТЗ — для активных селлеров"
    ),
    "unlimited": Package(
        name="Безлимит",
        credits=999,  # Условно безлимитный
        price_rub=1499,
        description="Безлимит на месяц",
        is_subscription=True
    )
}


def get_package(package_id: str) -> Package:
    """Получить пакет по ID."""
    return PACKAGES.get(package_id)


def get_all_packages() -> Dict[str, Package]:
    """Получить все пакеты."""
    return PACKAGES
```

---

## 🔄 МИГРАЦИИ

Для простоты используем автоматическое создание таблиц при первом запуске.

Если нужны миграции в будущем — добавим Alembic:

```bash
# Установка
pip install alembic

# Инициализация
alembic init alembic

# Создание миграции
alembic revision --autogenerate -m "Add new column"

# Применение миграций
alembic upgrade head
```

---

*Схема БД версия 1.0*
