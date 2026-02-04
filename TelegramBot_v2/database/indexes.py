"""
Управление индексами базы данных.

Модуль обеспечивает:
- Создание оптимальных индексов для частых запросов
- Проверку существующих индексов
- Статистику использования индексов
"""

from typing import List, Dict, Any

import structlog
from sqlalchemy import text

from database.database import get_session


logger = structlog.get_logger()


# ============================================================
# ОПРЕДЕЛЕНИЕ ИНДЕКСОВ
# ============================================================

# Список индексов для создания
# Формат: (название, таблица, колонки, уникальный)
INDEXES = [
    # Users
    ("idx_users_telegram_id", "users", ["telegram_id"], True),
    ("idx_users_created_at", "users", ["created_at"], False),
    ("idx_users_is_premium", "users", ["is_premium"], False),
    ("idx_users_referred_by", "users", ["referred_by"], False),
    
    # Generations
    ("idx_generations_user_id", "generations", ["user_id"], False),
    ("idx_generations_created_at", "generations", ["created_at"], False),
    ("idx_generations_category", "generations", ["category"], False),
    ("idx_generations_user_created", "generations", ["user_id", "created_at"], False),
    
    # Payments
    ("idx_payments_user_id", "payments", ["user_id"], False),
    ("idx_payments_status", "payments", ["status"], False),
    ("idx_payments_created_at", "payments", ["created_at"], False),
    ("idx_payments_user_status", "payments", ["user_id", "status"], False),
    
    # Feedback
    ("idx_feedback_generation_id", "feedbacks", ["generation_id"], False),
    ("idx_feedback_rating", "feedbacks", ["rating"], False),
    
    # Generation Photos
    ("idx_gen_photos_generation_id", "generation_photos", ["generation_id"], False),
    
    # Admin Actions
    ("idx_admin_actions_admin_id", "admin_actions", ["admin_id"], False),
    ("idx_admin_actions_created_at", "admin_actions", ["created_at"], False),
    ("idx_admin_actions_type", "admin_actions", ["action_type"], False),
]


# ============================================================
# ФУНКЦИИ УПРАВЛЕНИЯ ИНДЕКСАМИ
# ============================================================

async def create_indexes() -> Dict[str, Any]:
    """
    Создать все необходимые индексы.
    
    Пропускает уже существующие индексы.
    
    Returns:
        Результат создания {created: [...], skipped: [...], errors: [...]}
    """
    result = {
        "created": [],
        "skipped": [],
        "errors": [],
    }
    
    async with get_session() as session:
        for index_name, table, columns, unique in INDEXES:
            try:
                # Проверяем существование индекса
                exists = await _index_exists(session, index_name)
                
                if exists:
                    result["skipped"].append(index_name)
                    continue
                
                # Создаём индекс
                unique_str = "UNIQUE" if unique else ""
                columns_str = ", ".join(columns)
                
                sql = f"CREATE {unique_str} INDEX IF NOT EXISTS {index_name} ON {table} ({columns_str})"
                await session.execute(text(sql))
                
                result["created"].append(index_name)
                logger.info("index_created", index=index_name, table=table)
                
            except Exception as e:
                error_msg = f"{index_name}: {str(e)}"
                result["errors"].append(error_msg)
                logger.error("index_creation_failed", index=index_name, error=str(e))
    
    logger.info(
        "indexes_sync_completed",
        created=len(result["created"]),
        skipped=len(result["skipped"]),
        errors=len(result["errors"]),
    )
    
    return result


async def _index_exists(session, index_name: str) -> bool:
    """Проверить существование индекса (SQLite)."""
    result = await session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND name=:name"),
        {"name": index_name}
    )
    return result.scalar() is not None


async def list_indexes() -> List[Dict[str, str]]:
    """
    Получить список всех индексов в БД.
    
    Returns:
        Список индексов с их свойствами
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT name, tbl_name, sql 
                FROM sqlite_master 
                WHERE type='index' AND sql IS NOT NULL
                ORDER BY tbl_name, name
            """)
        )
        
        indexes = []
        for row in result.fetchall():
            indexes.append({
                "name": row[0],
                "table": row[1],
                "sql": row[2],
            })
        
        return indexes


async def drop_index(index_name: str) -> bool:
    """
    Удалить индекс.
    
    Args:
        index_name: Название индекса
        
    Returns:
        True если успешно
    """
    try:
        async with get_session() as session:
            await session.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
        
        logger.info("index_dropped", index=index_name)
        return True
        
    except Exception as e:
        logger.error("index_drop_failed", index=index_name, error=str(e))
        return False


async def get_index_stats() -> Dict[str, Any]:
    """
    Получить статистику использования индексов.
    
    Returns:
        Статистика индексов
    """
    indexes = await list_indexes()
    
    # Группируем по таблицам
    by_table = {}
    for idx in indexes:
        table = idx["table"]
        if table not in by_table:
            by_table[table] = []
        by_table[table].append(idx["name"])
    
    return {
        "total_indexes": len(indexes),
        "by_table": by_table,
        "expected_indexes": len(INDEXES),
    }


# ============================================================
# ИНИЦИАЛИЗАЦИЯ ПРИ СТАРТЕ
# ============================================================

async def ensure_indexes() -> None:
    """
    Убедиться что все индексы созданы.
    
    Вызывается при старте приложения.
    """
    logger.info("ensuring_database_indexes")
    result = await create_indexes()
    
    if result["errors"]:
        logger.warning(
            "some_indexes_failed",
            errors=result["errors"],
        )
