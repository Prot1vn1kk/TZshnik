"""
SQLAlchemy модели базы данных.

Модели:
- User: пользователи Telegram
- Generation: сгенерированные ТЗ
- GenerationPhoto: фотографии для генерации
- Payment: платежи за кредиты
- Feedback: отзывы о качестве ТЗ
- SupportTicket: тикеты техподдержки
- SupportMessage: сообщения в тикетах поддержки
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """
    Модель пользователя.
    
    Хранит информацию о пользователе Telegram,
    его балансе кредитов и статистике генераций.
    
    Attributes:
        telegram_id: Уникальный ID пользователя в Telegram
        username: Username в Telegram (может меняться)
        first_name: Имя пользователя
        balance: Количество доступных кредитов
        total_generated: Общее количество сгенерированных ТЗ
        is_premium: Флаг премиум-пользователя
        is_unlimited: Флаг активной безлимитной подписки
        unlimited_until: Дата окончания безлимитной подписки
        balance_before_unlimited: Баланс до покупки безлимита
        referred_by: ID реферера (если есть)
    """
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Telegram данные
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Баланс и статистика
    balance: Mapped[int] = mapped_column(
        Integer,
        default=1,  # 1 бесплатное ТЗ при регистрации
    )
    total_generated: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_unlimited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    unlimited_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    balance_before_unlimited: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Реферальная система (self-referential FK)
    referred_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    generations: Mapped[List["Generation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    ideas: Mapped[List["Idea"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    support_tickets: Mapped[List["SupportTicket"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    # Self-referential для рефералов
    referrals: Mapped[List["User"]] = relationship(
        back_populates="referrer",
        foreign_keys="User.referred_by",
    )
    referrer: Mapped[Optional["User"]] = relationship(
        back_populates="referrals",
        foreign_keys=[referred_by],
        remote_side=[id],
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, tg={self.telegram_id}, balance={self.balance})>"


class Generation(Base):
    """
    Модель сгенерированного ТЗ.
    
    Хранит результат генерации: анализ фото Vision AI,
    готовое техническое задание и метаданные качества.
    
    Attributes:
        user_id: ID пользователя (FK)
        category: Категория товара (одежда, электроника, и т.д.)
        photo_analysis: Результат анализа фото Vision AI
        tz_text: Полный текст сгенерированного ТЗ
        quality_score: Оценка качества от валидатора (0-100)
        regenerations: Количество перегенераций
        is_free: Флаг бесплатной генерации
    """
    
    __tablename__ = "generations"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Данные генерации
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    photo_analysis: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    tz_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Качество и статус
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    regenerations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="generations",
    )
    photos: Mapped[List["GenerationPhoto"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feedback: Mapped[Optional["Feedback"]] = relationship(
        back_populates="generation",
        uselist=False,
    )
    
    def __repr__(self) -> str:
        return f"<Generation(id={self.id}, cat={self.category}, score={self.quality_score})>"


class GenerationPhoto(Base):
    """
    Фотографии, использованные для генерации.
    
    Хранит Telegram file_id для возможности повторного
    скачивания или просмотра фотографий.
    
    Attributes:
        generation_id: ID генерации (FK)
        file_id: Telegram file_id фотографии
        file_unique_id: Уникальный ID файла в Telegram
    """
    
    __tablename__ = "generation_photos"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    generation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Telegram file IDs
    file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_unique_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    
    # Relationship
    generation: Mapped["Generation"] = relationship(
        back_populates="photos",
    )
    
    def __repr__(self) -> str:
        return f"<GenerationPhoto(id={self.id}, gen_id={self.generation_id})>"


class Payment(Base):
    """
    Модель платежа.
    
    Хранит информацию об оплате пакета кредитов
    через Telegram Payments (YooKassa).
    
    Attributes:
        user_id: ID пользователя (FK)
        telegram_payment_id: Уникальный ID платежа в Telegram
        amount: Сумма в копейках
        currency: Валюта (RUB)
        credits_added: Количество начисленных кредитов
        package_name: Название пакета
        status: Статус платежа
    """
    
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Данные платежа Telegram
    telegram_payment_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    
    # Сумма и валюта
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,  # В копейках!
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="RUB",
    )
    
    # Что получил пользователь
    credits_added: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    package_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    # Статус
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    
    # Relationship
    user: Mapped["User"] = relationship(
        back_populates="payments",
    )
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, credits={self.credits_added})>"


class Feedback(Base):
    """
    Обратная связь по сгенерированному ТЗ.
    
    Позволяет пользователю оценить качество генерации
    и оставить комментарий.
    
    Attributes:
        generation_id: ID генерации (FK, unique - один фидбек на ТЗ)
        user_id: ID пользователя (FK)
        rating: Оценка (1 = 👍, 0 = 👎)
        comment: Текстовый комментарий (опционально)
    """
    
    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint("rating IN (0, 1)", name="check_feedback_rating_valid"),
    )
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    generation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Один фидбек на генерацию
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Оценка: 1 = 👍, 0 = 👎
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    
    # Relationship
    generation: Mapped["Generation"] = relationship(
        back_populates="feedback",
    )
    
    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, gen_id={self.generation_id}, rating={self.rating})>"


class Idea(Base):
    """
    Идея/предложение от пользователя.
    
    Хранит текст идеи и статус модерации.
    """
    
    __tablename__ = "ideas"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="new",
        index=True,
    )
    reward_credits: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    decided_by_admin_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    
    user: Mapped["User"] = relationship(
        back_populates="ideas",
    )
    
    def __repr__(self) -> str:
        return f"<Idea(id={self.id}, user_id={self.user_id}, status={self.status})>"


class AdminAction(Base):
    """
    Логирование действий администратора.
    
    Хранит все административные действия для аудита:
    - Начисление/списание кредитов
    - Блокировка/разблокировка пользователей
    - Изменение настроек
    
    Attributes:
        admin_id: Telegram ID администратора
        action_type: Тип действия (credit_add, credit_remove, block, unblock, etc.)
        target_user_id: Telegram ID целевого пользователя (если применимо)
        details: Детали действия в JSON формате
    """
    
    __tablename__ = "admin_actions"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    # Администратор, выполнивший действие
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    
    # Тип действия
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Целевой пользователь (если есть)
    target_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    
    # Детали в JSON
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<AdminAction(id={self.id}, type={self.action_type}, admin={self.admin_id})>"


class BotSettings(Base):
    """
    Настройки бота, изменяемые из админ-панели.
    
    Хранит глобальные настройки:
    - Бесплатные генерации для новых пользователей
    - Режим обслуживания
    - Другие конфигурируемые параметры
    """
    
    __tablename__ = "bot_settings"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    
    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<BotSettings(key={self.key}, value={self.value})>"


class SupportTicket(Base):
    """
    Модель тикета техподдержки.

    Хранит обращения пользователей в поддержку:
    - Категория проблемы (Payment, Technical, Other)
    - Статус (Open, In Progress, Resolved, Archived)
    - Приоритет (Low, Medium, High)
    - Сообщения в двухстороннем диалоге
    - Назначенный администратор
    - Решение проблемы (для архивированных)
    - Флаг важности
    """

    __tablename__ = "support_tickets"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Пользователь
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Категория проблемы
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'payment', 'technical', 'other'

    # Статус тикета
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        index=True,
    )  # 'open', 'in_progress', 'resolved', 'archived'

    # Приоритет
    priority: Mapped[str] = mapped_column(
        String(10),
        default="medium",
        nullable=False,
    )  # 'low', 'medium', 'high'

    # Назначенный администратор (telegram_id)
    assigned_admin_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    # Флаг важности (для архивации важных тикетов)
    is_important: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Примечание о решении (для архивированных тикетов)
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # SLA Tracking
    first_response_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        comment="Время первого ответа администратора",
    )
    last_admin_response_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Время последнего ответа администратора",
    )
    sla_breach: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Флаг нарушения SLA (ответ > 24 часа)",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="support_tickets",
    )
    messages: Mapped[List["SupportMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SupportMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<SupportTicket(id={self.id}, category={self.category}, status={self.status})>"


class SupportMessage(Base):
    """
    Сообщение в тикете поддержки.

    Хранит сообщения от пользователя и администратора
    в рамках тикета техподдержки.
    """

    __tablename__ = "support_messages"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Тикет
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Отправитель: 'user' или 'admin'
    sender_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # 'user', 'admin'

    # ID отправителя в Telegram
    sender_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    # Текст сообщения
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )

    # Relationship
    ticket: Mapped["SupportTicket"] = relationship(
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<SupportMessage(id={self.id}, ticket_id={self.ticket_id}, sender={self.sender_type})>"


# Дополнительные составные индексы для оптимизации запросов
Index("ix_generations_user_created", Generation.user_id, Generation.created_at.desc())
Index("ix_payments_user_created", Payment.user_id, Payment.created_at.desc())
Index("ix_admin_actions_created", AdminAction.created_at.desc())
Index("ix_ideas_status_created", Idea.status, Idea.created_at.desc())
Index("ix_support_tickets_status_created", SupportTicket.status, SupportTicket.created_at.desc())
Index("ix_support_tickets_user_created", SupportTicket.user_id, SupportTicket.created_at.desc())
Index("ix_support_messages_ticket_created", SupportMessage.ticket_id, SupportMessage.created_at.desc())
