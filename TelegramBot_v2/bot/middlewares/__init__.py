"""
Middleware бота.

Содержит:
- ThrottlingMiddleware - защита от спама
- (другие middleware из bot/middleware.py)
"""

from bot.middlewares.throttling import (
    ThrottlingMiddleware,
    RateLimitConfig,
    create_throttling_middleware,
    GenerationThrottlingMiddleware,
)

__all__ = [
    "ThrottlingMiddleware",
    "RateLimitConfig",
    "create_throttling_middleware",
    "GenerationThrottlingMiddleware",
]
