"""
Middleware бота.

Содержит:
- ThrottlingMiddleware - защита от спама
- AlbumMiddleware - обработка медиагрупп (альбомов)
- (другие middleware из bot/middleware.py)
"""

from bot.middlewares.throttling import (
    ThrottlingMiddleware,
    RateLimitConfig,
    create_throttling_middleware,
    GenerationThrottlingMiddleware,
)
from bot.middlewares.album import AlbumMiddleware

__all__ = [
    "ThrottlingMiddleware",
    "RateLimitConfig",
    "create_throttling_middleware",
    "GenerationThrottlingMiddleware",
    "AlbumMiddleware",
]
