"""
Подключение к базе данных и управление сессиями.

Модуль предоставляет:
- Async engine для SQLite с оптимизированным connection pooling
- Фабрику асинхронных сессий
- Context manager для безопасной работы с сессиями
- Функции инициализации и закрытия БД
- Мониторинг производительности БД
- Health check для БД
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

import structlog
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from bot.config import settings

# Логгер для модуля БД
logger = structlog.get_logger()


# ============================================================
# КОНФИГУРАЦИЯ CONNECTION POOL
# ============================================================

# Для SQLite используем StaticPool (один коннект, потокобезопасный)
# Для PostgreSQL/MySQL используем стандартный пул
POOL_CONFIG = {
    "sqlite": {
        "poolclass": StaticPool,
        "connect_args": {
            "check_same_thread": False,
            "timeout": 30,
        },
    },
    "postgresql": {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    },
}

def get_pool_config() -> Dict[str, Any]:
    """Получить конфигурацию пула для текущей БД."""
    db_url = settings.database_url.lower()
    
    if "sqlite" in db_url:
        return POOL_CONFIG["sqlite"]
    elif "postgresql" in db_url or "postgres" in db_url:
        return POOL_CONFIG["postgresql"]
    else:
        # Дефолтная конфигурация
        return {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_pre_ping": True,
        }


# Создаём async engine с оптимизированным пулом
pool_config = get_pool_config()
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # SQL логи в debug режиме
    future=True,
    **pool_config,
)

# Фабрика асинхронных сессий
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ============================================================
# СТАТИСТИКА И МОНИТОРИНГ
# ============================================================

class DatabaseStats:
    """Класс для сбора статистики БД."""
    
    def __init__(self):
        self.query_count = 0
        self.error_count = 0
        self.slow_queries = 0
        self.total_time_ms = 0.0
        self.last_health_check = None
    
    def record_query(self, duration_ms: float, is_slow: bool = False):
        """Записать метрику запроса."""
        self.query_count += 1
        self.total_time_ms += duration_ms
        if is_slow:
            self.slow_queries += 1
    
    def record_error(self):
        """Записать ошибку."""
        self.error_count += 1
    
    @property
    def avg_query_time_ms(self) -> float:
        """Среднее время запроса."""
        if self.query_count == 0:
            return 0.0
        return self.total_time_ms / self.query_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику."""
        return {
            "query_count": self.query_count,
            "error_count": self.error_count,
            "slow_queries": self.slow_queries,
            "avg_query_time_ms": round(self.avg_query_time_ms, 2),
            "total_time_ms": round(self.total_time_ms, 2),
        }
    
    def reset(self):
        """Сбросить статистику."""
        self.query_count = 0
        self.error_count = 0
        self.slow_queries = 0
        self.total_time_ms = 0.0


# Глобальная статистика
db_stats = DatabaseStats()

# Порог медленного запроса (мс)
SLOW_QUERY_THRESHOLD_MS = 100.0


async def init_db() -> None:
    """
    Инициализация базы данных.
    
    Создаёт все таблицы если их нет.
    Вызывается при старте бота.
    """
    # Импорт здесь чтобы избежать circular import
    from database.models import Base
    
    # Создаём директорию для БД
    settings.data_dir.mkdir(exist_ok=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("database_initialized", url=settings.database_url)


async def close_db() -> None:
    """
    Закрытие соединения с базой данных.
    
    Вызывается при остановке бота для корректного
    освобождения ресурсов.
    """
    await engine.dispose()
    logger.info("database_closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для работы с сессией БД.
    
    Автоматически выполняет commit при успехе и rollback при ошибке.
    Гарантирует закрытие сессии в любом случае.
    Собирает метрики производительности.
    
    Использование:
        async with get_session() as session:
            result = await session.execute(query)
            
    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy
    """
    session = async_session_factory()
    start_time = time.time()
    
    try:
        yield session
        await session.commit()
        
        # Записываем метрику
        duration_ms = (time.time() - start_time) * 1000
        is_slow = duration_ms > SLOW_QUERY_THRESHOLD_MS
        db_stats.record_query(duration_ms, is_slow)
        
        if is_slow:
            logger.warning(
                "slow_database_operation",
                duration_ms=round(duration_ms, 2),
            )
            
    except Exception as e:
        await session.rollback()
        db_stats.record_error()
        logger.error("database_session_error", error=str(e))
        raise
    finally:
        await session.close()


# ============================================================
# HEALTH CHECK И УТИЛИТЫ
# ============================================================

async def health_check() -> Dict[str, Any]:
    """
    Проверка здоровья БД.
    
    Returns:
        Словарь с результатами проверки
    """
    result = {
        "status": "unknown",
        "latency_ms": None,
        "error": None,
    }
    
    start_time = time.time()
    
    try:
        async with get_session() as session:
            # Простой запрос для проверки соединения
            await session.execute(text("SELECT 1"))
        
        latency_ms = (time.time() - start_time) * 1000
        result["status"] = "healthy"
        result["latency_ms"] = round(latency_ms, 2)
        db_stats.last_health_check = time.time()
        
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
        logger.error("database_health_check_failed", error=str(e))
    
    return result


async def get_db_stats() -> Dict[str, Any]:
    """
    Получить статистику работы с БД.
    
    Returns:
        Словарь со статистикой
    """
    health = await health_check()
    stats = db_stats.get_stats()
    
    return {
        "health": health,
        "stats": stats,
        "pool_info": {
            "pool_class": pool_config.get("poolclass", "default").__name__ 
                if "poolclass" in pool_config else "QueuePool",
        },
    }


async def optimize_sqlite() -> None:
    """
    Оптимизация SQLite базы данных.
    
    Выполняет VACUUM и ANALYZE для оптимизации.
    Рекомендуется запускать периодически (раз в день).
    """
    if "sqlite" not in settings.database_url.lower():
        logger.warning("optimize_sqlite called for non-SQLite database")
        return
    
    try:
        async with get_session() as session:
            # VACUUM перестраивает БД и освобождает место
            await session.execute(text("VACUUM"))
            # ANALYZE обновляет статистику для оптимизатора запросов
            await session.execute(text("ANALYZE"))
        
        logger.info("sqlite_optimized")
        
    except Exception as e:
        logger.error("sqlite_optimization_failed", error=str(e))
