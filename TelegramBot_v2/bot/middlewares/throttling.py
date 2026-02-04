"""
Throttling и Rate Limiting middleware.

Модуль обеспечивает защиту от спама и DDoS:
- Ограничение частоты запросов на пользователя
- Гибкая настройка лимитов для разных типов действий
- Автоматическая очистка старых записей
- Логирование подозрительной активности
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
import structlog


logger = structlog.get_logger()


# ============================================================
# КОНФИГУРАЦИЯ ЛИМИТОВ
# ============================================================

@dataclass
class RateLimitConfig:
    """Конфигурация rate limiting."""
    
    # Общие лимиты (запросов в секунду)
    # ВАЖНО: rate = количество запросов в секунду
    # Например, rate=5 означает минимальный интервал 0.2 секунды (200мс)
    message_rate: float = 3.0          # 3 сообщения в секунду (интервал 333мс)
    callback_rate: float = 5.0         # 5 callback в секунду (интервал 200мс)
    
    # Лимиты для "тяжёлых" действий (защита от злоупотреблений)
    generation_rate: float = 0.2       # 1 генерация в 5 секунд (требует API вызов)
    photo_rate: float = 2.0            # 2 фото в секунду
    payment_rate: float = 0.5          # 1 платёж в 2 секунды
    
    # Время бана при превышении лимита (секунды)
    ban_duration: float = 30.0         # Сократили с 60 до 30 секунд
    
    # Порог для логирования подозрительной активности
    suspicious_threshold: int = 20     # Увеличили с 10 до 20
    
    # Время жизни записи в кэше (секунды)
    cache_ttl: float = 300.0           # 5 минут


@dataclass  
class UserRateState:
    """Состояние rate limiting для пользователя."""
    
    last_request: float = 0.0
    violations: int = 0
    banned_until: float = 0.0
    requests_count: int = 0
    
    # Специфичные таймстампы
    last_generation: float = 0.0
    last_photo: float = 0.0
    last_payment: float = 0.0


# ============================================================
# THROTTLING MIDDLEWARE
# ============================================================

class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов.
    
    Отслеживает запросы каждого пользователя и блокирует
    при превышении лимитов.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Инициализация middleware.
        
        Args:
            config: Конфигурация лимитов (по умолчанию стандартная)
        """
        self.config = config or RateLimitConfig()
        self.user_states: Dict[int, UserRateState] = defaultdict(UserRateState)
        self._last_cleanup = time.time()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Проверяет rate limit и вызывает обработчик."""
        
        # Получаем user_id
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        # Определяем тип события и соответствующий rate
        event_type, rate_limit = self._get_event_rate(event, data)
        
        # Проверяем rate limit
        current_time = time.time()
        state = self.user_states[user_id]
        
        # Проверяем бан
        if state.banned_until > current_time:
            remaining = int(state.banned_until - current_time)
            await self._send_rate_limit_message(event, remaining)
            logger.warning(
                "rate_limit_banned_user_attempt",
                user_id=user_id,
                remaining_seconds=remaining,
            )
            return None
        
        # Проверяем rate
        time_since_last = current_time - state.last_request
        min_interval = 1.0 / rate_limit if rate_limit > 0 else 0
        
        if time_since_last < min_interval:
            state.violations += 1
            
            # Банним при частых нарушениях
            if state.violations >= 5:
                state.banned_until = current_time + self.config.ban_duration
                logger.warning(
                    "rate_limit_user_banned",
                    user_id=user_id,
                    violations=state.violations,
                    ban_duration=self.config.ban_duration,
                )
            
            # Логируем подозрительную активность
            if state.violations >= self.config.suspicious_threshold:
                logger.error(
                    "rate_limit_suspicious_activity",
                    user_id=user_id,
                    violations=state.violations,
                )
            
            await self._send_rate_limit_message(event)
            return None
        
        # Обновляем состояние
        state.last_request = current_time
        state.requests_count += 1
        
        # Добавляем state в data для использования в хендлерах
        data["rate_state"] = state
        
        # Периодическая очистка кэша
        if current_time - self._last_cleanup > 300:  # каждые 5 минут
            await self._cleanup_old_states(current_time)
        
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> Optional[int]:
        """Получить user_id из события."""
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None
    
    def _get_event_rate(
        self,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> tuple[str, float]:
        """
        Определить тип события и соответствующий rate limit.
        
        Returns:
            Tuple[event_type, rate_limit]
        """
        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            
            # Специфичные callback
            if callback_data.startswith("category:"):
                return "generation", self.config.generation_rate
            elif callback_data.startswith("buy:"):
                return "payment", self.config.payment_rate
            else:
                return "callback", self.config.callback_rate
        
        elif isinstance(event, Message):
            # Фото
            if event.photo:
                return "photo", self.config.photo_rate
            else:
                return "message", self.config.message_rate
        
        return "unknown", self.config.message_rate
    
    async def _send_rate_limit_message(
        self,
        event: TelegramObject,
        remaining_seconds: Optional[int] = None,
    ) -> None:
        """Отправить сообщение о превышении лимита."""
        if remaining_seconds:
            text = f"⏳ Слишком много запросов. Подождите {remaining_seconds} сек."
        else:
            text = "⏳ Не так быстро! Подождите немного."
        
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)
        except Exception as e:
            logger.warning("Failed to send rate limit message", error=str(e))
    
    async def _cleanup_old_states(self, current_time: float) -> None:
        """Очистка старых записей из кэша."""
        self._last_cleanup = current_time
        ttl = self.config.cache_ttl
        
        expired_users = [
            user_id
            for user_id, state in self.user_states.items()
            if (current_time - state.last_request) > ttl
        ]
        
        for user_id in expired_users:
            del self.user_states[user_id]
        
        if expired_users:
            logger.debug(
                "rate_limit_cache_cleanup",
                removed_count=len(expired_users),
            )
    
    def reset_user(self, user_id: int) -> None:
        """
        Сбросить состояние пользователя (для админ команд).
        
        Args:
            user_id: Telegram ID пользователя
        """
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику rate limiting для пользователя.
        
        Args:
            user_id: Telegram ID
            
        Returns:
            Словарь со статистикой
        """
        state = self.user_states.get(user_id)
        if not state:
            return {"exists": False}
        
        current_time = time.time()
        return {
            "exists": True,
            "violations": state.violations,
            "requests_count": state.requests_count,
            "is_banned": state.banned_until > current_time,
            "banned_until": state.banned_until if state.banned_until > current_time else None,
            "last_request_ago": current_time - state.last_request,
        }


# ============================================================
# СПЕЦИАЛИЗИРОВАННЫЕ RATE LIMITERS
# ============================================================

class GenerationThrottlingMiddleware(BaseMiddleware):
    """
    Специализированный throttling для генерации ТЗ.
    
    Более строгие лимиты для дорогих AI операций.
    """
    
    def __init__(self, min_interval: float = 10.0):
        """
        Args:
            min_interval: Минимальный интервал между генерациями (сек)
        """
        self.min_interval = min_interval
        self.last_generation: Dict[int, float] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Проверяет throttling для генерации."""
        
        # Только для callback генерации
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        
        callback_data = event.data or ""
        if not callback_data.startswith("category:"):
            return await handler(event, data)
        
        user_id = event.from_user.id if event.from_user else 0
        if not user_id:
            return await handler(event, data)
        
        current_time = time.time()
        last_time = self.last_generation.get(user_id, 0)
        
        if current_time - last_time < self.min_interval:
            remaining = int(self.min_interval - (current_time - last_time))
            await event.answer(
                f"⏳ Генерация доступна через {remaining} сек.",
                show_alert=True,
            )
            return None
        
        # Обновляем время последней генерации
        self.last_generation[user_id] = current_time
        
        return await handler(event, data)


# ============================================================
# ФАБРИКА MIDDLEWARE
# ============================================================

def create_throttling_middleware(
    message_rate: float = 1.0,
    callback_rate: float = 2.0,
    generation_rate: float = 0.1,
    ban_duration: float = 60.0,
) -> ThrottlingMiddleware:
    """
    Создать настроенный throttling middleware.
    
    Args:
        message_rate: Сообщений в секунду
        callback_rate: Callback в секунду  
        generation_rate: Генераций в секунду
        ban_duration: Длительность бана (сек)
        
    Returns:
        Настроенный ThrottlingMiddleware
    """
    config = RateLimitConfig(
        message_rate=message_rate,
        callback_rate=callback_rate,
        generation_rate=generation_rate,
        ban_duration=ban_duration,
    )
    return ThrottlingMiddleware(config)
