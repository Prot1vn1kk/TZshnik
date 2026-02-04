"""
Тесты для throttling middleware.

Проверка rate limiting и защиты от спама.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.middlewares.throttling import (
    ThrottlingMiddleware,
    RateLimitConfig,
    UserRateState,
    create_throttling_middleware,
)


class TestRateLimitConfig:
    """Тесты конфигурации rate limiting."""
    
    def test_default_config(self):
        config = RateLimitConfig()
        assert config.message_rate == 1.0
        assert config.callback_rate == 0.5
        assert config.ban_duration == 60.0
    
    def test_custom_config(self):
        config = RateLimitConfig(
            message_rate=2.0,
            ban_duration=120.0,
        )
        assert config.message_rate == 2.0
        assert config.ban_duration == 120.0


class TestUserRateState:
    """Тесты состояния пользователя."""
    
    def test_initial_state(self):
        state = UserRateState()
        assert state.violations == 0
        assert state.requests_count == 0
        assert state.banned_until == 0.0


class TestThrottlingMiddleware:
    """Тесты throttling middleware."""
    
    @pytest.fixture
    def middleware(self):
        return ThrottlingMiddleware()
    
    @pytest.fixture
    def mock_handler(self):
        return AsyncMock(return_value="handler_result")
    
    @pytest.fixture
    def mock_message(self):
        msg = MagicMock()
        msg.from_user = MagicMock()
        msg.from_user.id = 12345
        msg.photo = None
        msg.answer = AsyncMock()
        return msg
    
    @pytest.mark.asyncio
    async def test_first_request_passes(self, middleware, mock_handler, mock_message):
        """Первый запрос должен проходить."""
        result = await middleware(mock_handler, mock_message, {})
        assert result == "handler_result"
        mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rapid_requests_blocked(self, middleware, mock_handler, mock_message):
        """Быстрые последовательные запросы должны блокироваться."""
        # Первый запрос проходит
        await middleware(mock_handler, mock_message, {})
        
        # Немедленно второй - блокируется
        result = await middleware(mock_handler, mock_message, {})
        assert result is None
    
    @pytest.mark.asyncio
    async def test_requests_after_delay_pass(self, middleware, mock_handler, mock_message):
        """Запросы после задержки должны проходить."""
        await middleware(mock_handler, mock_message, {})
        
        # Ждём достаточно
        await asyncio.sleep(1.1)
        
        result = await middleware(mock_handler, mock_message, {})
        assert result == "handler_result"
    
    def test_reset_user(self, middleware):
        """Сброс состояния пользователя."""
        user_id = 12345
        middleware.user_states[user_id].violations = 5
        
        middleware.reset_user(user_id)
        
        assert user_id not in middleware.user_states
    
    def test_get_user_stats_nonexistent(self, middleware):
        """Статистика для несуществующего пользователя."""
        stats = middleware.get_user_stats(99999)
        assert stats["exists"] is False
    
    @pytest.mark.asyncio
    async def test_user_gets_banned(self, middleware, mock_handler, mock_message):
        """Пользователь банится после множества нарушений."""
        # Симулируем множество быстрых запросов
        for _ in range(10):
            await middleware(mock_handler, mock_message, {})
        
        stats = middleware.get_user_stats(mock_message.from_user.id)
        # После 5 нарушений должен быть забанен
        assert stats["violations"] >= 5 or stats["is_banned"]


class TestCreateThrottlingMiddleware:
    """Тесты фабрики middleware."""
    
    def test_creates_with_custom_config(self):
        middleware = create_throttling_middleware(
            message_rate=2.0,
            callback_rate=3.0,
            ban_duration=30.0,
        )
        
        assert isinstance(middleware, ThrottlingMiddleware)
        assert middleware.config.message_rate == 2.0
        assert middleware.config.callback_rate == 3.0
        assert middleware.config.ban_duration == 30.0
