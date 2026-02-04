"""
Middleware бота.

Содержит middleware для:
- Инъекции пользователя в обработчики
- Логирования запросов

ПРИМЕЧАНИЕ: CRUD функции управляют своими сессиями сами через get_session(),
поэтому DatabaseMiddleware не нужен.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
import structlog

from database import get_or_create_user


logger = structlog.get_logger()


class UserMiddleware(BaseMiddleware):
    """
    Middleware для инъекции пользователя.
    
    Добавляет 'user' (модель User) в data обработчика.
    Автоматически создаёт пользователя если его нет в БД.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Получает или создаёт пользователя и добавляет в data."""
        # Получаем user из события
        user_tg = None
        
        if isinstance(event, Message):
            user_tg = event.from_user
        elif isinstance(event, CallbackQuery):
            user_tg = event.from_user
        elif hasattr(event, "from_user"):
            user_tg = getattr(event, "from_user", None)
        
        if user_tg:
            try:
                # get_or_create_user возвращает Tuple[User, bool]
                user, created = await get_or_create_user(
                    telegram_id=user_tg.id,
                    username=user_tg.username,
                    first_name=user_tg.first_name,
                )
                data["user"] = user
                
                if created:
                    logger.info(
                        "New user created",
                        telegram_id=user_tg.id,
                        username=user_tg.username,
                    )
                else:
                    logger.debug(
                        "User loaded",
                        telegram_id=user_tg.id,
                        balance=user.balance,
                    )
            except Exception as e:
                logger.error(
                    "Failed to load user",
                    telegram_id=user_tg.id,
                    error=str(e),
                )
        
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования запросов.
    
    Логирует все входящие обновления для отладки.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Логирует обновление и вызывает обработчик."""
        # Определяем тип события
        event_type = type(event).__name__
        
        # Извлекаем user_id если есть
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            if event.from_user:
                user_id = event.from_user.id
        
        # Логируем запрос
        log = logger.bind(
            event_type=event_type,
            user_id=user_id,
        )
        
        log.debug("Incoming update")
        
        try:
            result = await handler(event, data)
            log.debug("Update handled successfully")
            return result
        except Exception as e:
            log.error("Handler failed", error=str(e))
            raise


# Для совместимости с main.py - DatabaseMiddleware теперь no-op
class DatabaseMiddleware(BaseMiddleware):
    """
    Заглушка для совместимости.
    
    CRUD функции используют get_session() внутри себя,
    поэтому не нужно инжектировать session в обработчики.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Просто вызывает обработчик без изменений."""
        return await handler(event, data)
