"""
Конфигурация бота поддержки.

Расширяет основной конфиг настройками для бота поддержки.
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Импортируем базовый конфиг для общих настроек
from bot.config import BASE_DIR


class SupportBotSettings(BaseSettings):
    """Настройки бота поддержки."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Токен бота поддержки (отдельный от основного)
    support_bot_token: str = ""

    # Режим отладки
    debug: bool = False

    # Username основного бота (для cross-bot уведомлений)
    main_bot_username: str = ""

    @property
    def admin_ids(self) -> List[int]:
        """Импортировать ID администраторов из основного конфига."""
        from bot.config import settings
        return settings.admin_ids


# Глобальный экземпляр настроек
support_settings = SupportBotSettings()
