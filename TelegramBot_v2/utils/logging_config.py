"""
Расширенная конфигурация логирования.

Модуль обеспечивает:
- Структурированное логирование через structlog
- Ротацию файлов логов
- Раздельные логи для ошибок и общих событий
- Интеграцию с мониторингом
- Фильтрацию чувствительных данных
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from structlog.processors import CallsiteParameter


# ============================================================
# КОНСТАНТЫ
# ============================================================

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Размеры файлов логов
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5                 # Хранить 5 резервных копий

# Чувствительные поля для фильтрации
SENSITIVE_FIELDS = {
    "token",
    "api_key", 
    "password",
    "secret",
    "authorization",
    "yookassa_provider_token",
    "telegram_bot_token",
    "gemini_api_key",
}


# ============================================================
# ПРОЦЕССОРЫ ДЛЯ STRUCTLOG
# ============================================================

def filter_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Процессор для фильтрации чувствительных данных из логов.
    
    Заменяет значения полей с токенами/паролями на [REDACTED].
    """
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        
        # Проверяем, является ли поле чувствительным
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            event_dict[key] = "[REDACTED]"
        
        # Проверяем вложенные dict
        elif isinstance(event_dict[key], dict):
            for nested_key in list(event_dict[key].keys()):
                if any(sensitive in nested_key.lower() for sensitive in SENSITIVE_FIELDS):
                    event_dict[key][nested_key] = "[REDACTED]"
    
    return event_dict


def add_app_context(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Процессор для добавления контекста приложения.
    """
    event_dict["app"] = "tzshnik"
    event_dict["version"] = "2.0"
    return event_dict


# ============================================================
# НАСТРОЙКА ЛОГГЕРОВ
# ============================================================

def setup_file_handlers(
    log_level: int = logging.INFO,
) -> list[logging.Handler]:
    """
    Создание файловых обработчиков с ротацией.
    
    Returns:
        Список обработчиков логов
    """
    # Создаём директорию логов
    LOG_DIR.mkdir(exist_ok=True)
    
    handlers = []
    
    # Основной лог с ротацией по размеру
    main_handler = RotatingFileHandler(
        LOG_DIR / "bot.log",
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    main_handler.setLevel(log_level)
    main_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handlers.append(main_handler)
    
    # Лог ошибок (только ERROR и выше)
    error_handler = RotatingFileHandler(
        LOG_DIR / "errors.log",
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handlers.append(error_handler)
    
    # Дневной лог с ротацией по времени
    daily_handler = TimedRotatingFileHandler(
        LOG_DIR / "daily.log",
        when="midnight",
        interval=1,
        backupCount=30,  # Хранить 30 дней
        encoding="utf-8",
    )
    daily_handler.setLevel(log_level)
    daily_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handlers.append(daily_handler)
    
    return handlers


def setup_advanced_logging(
    debug: bool = False,
    log_to_file: bool = True,
) -> structlog.BoundLogger:
    """
    Настройка расширенного логирования.
    
    Args:
        debug: Режим отладки (verbose вывод)
        log_to_file: Записывать логи в файл
        
    Returns:
        Настроенный логгер
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Настраиваем stdlib logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Добавляем консольный вывод
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # Добавляем файловые обработчики
    if log_to_file:
        for handler in setup_file_handlers(log_level):
            root_logger.addHandler(handler)
    
    # Настраиваем уровни для сторонних библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if debug else logging.WARNING
    )
    
    # Выбираем рендерер для structlog
    if debug:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.better_traceback,
        )
    else:
        renderer = structlog.processors.JSONRenderer()
    
    # Процессоры structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        # Добавляем информацию о месте вызова
        structlog.processors.CallsiteParameterAdder(
            [
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
        # Кастомные процессоры
        add_app_context,
        filter_sensitive_data,
        # Форматирование исключений
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        renderer,
    ]
    
    # Конфигурируем structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()


# ============================================================
# КОНТЕКСТНОЕ ЛОГИРОВАНИЕ
# ============================================================

def get_logger_with_context(**context) -> structlog.BoundLogger:
    """
    Получить логгер с предустановленным контекстом.
    
    Пример:
        logger = get_logger_with_context(user_id=123, action="generation")
        logger.info("Starting generation")  # Включит user_id и action
    
    Args:
        **context: Ключ-значение для добавления в контекст
        
    Returns:
        Логгер с контекстом
    """
    return structlog.get_logger().bind(**context)


def log_user_action(
    user_id: int,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    level: str = "info",
) -> None:
    """
    Логирование действия пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        action: Название действия
        details: Дополнительные детали
        level: Уровень лога (info, warning, error)
    """
    logger = structlog.get_logger()
    log_data = {
        "user_id": user_id,
        "action": action,
    }
    if details:
        log_data.update(details)
    
    log_func = getattr(logger, level, logger.info)
    log_func("user_action", **log_data)


def log_api_call(
    provider: str,
    endpoint: str,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """
    Логирование вызова внешнего API.
    
    Args:
        provider: Название провайдера (gemini, yookassa, etc.)
        endpoint: Эндпоинт API
        duration_ms: Время выполнения в мс
        success: Успешен ли вызов
        error: Текст ошибки (если есть)
    """
    logger = structlog.get_logger()
    log_data = {
        "provider": provider,
        "endpoint": endpoint,
        "duration_ms": duration_ms,
        "success": success,
    }
    
    if error:
        log_data["error"] = error
        logger.error("api_call", **log_data)
    else:
        logger.info("api_call", **log_data)


def log_performance(
    operation: str,
    duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Логирование метрик производительности.
    
    Args:
        operation: Название операции
        duration_ms: Время выполнения в мс
        metadata: Дополнительные метаданные
    """
    logger = structlog.get_logger()
    log_data = {
        "operation": operation,
        "duration_ms": duration_ms,
    }
    if metadata:
        log_data.update(metadata)
    
    # Предупреждение о медленных операциях
    if duration_ms > 5000:  # > 5 секунд
        logger.warning("slow_operation", **log_data)
    else:
        logger.info("performance", **log_data)


# ============================================================
# ДЕКОРАТОРЫ ЛОГИРОВАНИЯ
# ============================================================

def log_execution(
    operation_name: Optional[str] = None,
    log_args: bool = False,
):
    """
    Декоратор для логирования выполнения функции.
    
    Args:
        operation_name: Название операции (по умолчанию имя функции)
        log_args: Логировать ли аргументы функции
    """
    import functools
    import time
    
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            name = operation_name or func.__name__
            
            start_time = time.time()
            log_data = {"operation": name}
            
            if log_args and kwargs:
                # Фильтруем чувствительные данные
                safe_kwargs = {
                    k: v for k, v in kwargs.items()
                    if not any(s in k.lower() for s in SENSITIVE_FIELDS)
                }
                log_data["kwargs"] = safe_kwargs
            
            logger.debug("operation_started", **log_data)
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info(
                    "operation_completed",
                    operation=name,
                    duration_ms=duration_ms,
                )
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    "operation_failed",
                    operation=name,
                    duration_ms=duration_ms,
                    error=str(e),
                    exc_info=True,
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            name = operation_name or func.__name__
            
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.info(
                    "operation_completed",
                    operation=name,
                    duration_ms=duration_ms,
                )
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    "operation_failed",
                    operation=name,
                    duration_ms=duration_ms,
                    error=str(e),
                    exc_info=True,
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
