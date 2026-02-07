"""
Модуль базы данных "ТЗшник v2.0".

Содержит:
- models.py - SQLAlchemy модели (User, Generation, Payment, AdminAction, BotSettings)
- crud.py - CRUD операции
- admin_crud.py - CRUD операции для админ-панели
- database.py - подключение к БД, async engine
"""

from database.database import close_db, get_session, init_db
from database.models import (
    AdminAction,
    Base,
    BotSettings,
    Feedback,
    Idea,
    Generation,
    GenerationPhoto,
    Payment,
    User,
)
from database.crud import (
    # Users
    get_user_by_telegram_id,
    get_or_create_user,
    get_user_balance,
    decrease_balance,
    increase_balance,
    is_unlimited_active,
    activate_unlimited,
    # Generations
    create_generation,
    get_generation_by_id,
    get_user_generations,
    # Payments
    create_payment,
    update_payment_status,
    get_user_payments,
    # Feedback
    create_feedback,
    # Ideas
    create_idea,
    # Stats
    get_user_stats,
    get_admin_stats,
)


__all__ = [
    # Database
    "init_db",
    "close_db",
    "get_session",
    # Models
    "Base",
    "User",
    "Generation",
    "GenerationPhoto",
    "Payment",
    "Feedback",
    "Idea",
    "AdminAction",
    "BotSettings",
    # CRUD - Users
    "get_user_by_telegram_id",
    "get_or_create_user",
    "get_user_balance",
    "decrease_balance",
    "increase_balance",
    "is_unlimited_active",
    "activate_unlimited",
    # CRUD - Generations
    "create_generation",
    "get_generation_by_id",
    "get_user_generations",
    # CRUD - Payments
    "create_payment",
    "update_payment_status",
    "get_user_payments",
    # CRUD - Feedback
    "create_feedback",
    # CRUD - Ideas
    "create_idea",
    # CRUD - Stats
    "get_user_stats",
    "get_admin_stats",
]
