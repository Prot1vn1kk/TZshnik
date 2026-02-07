"""
Конфигурация приложения.

Загружает настройки из .env файла с использованием Pydantic Settings.
Все секреты и настройки должны храниться в .env файле.
"""

from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# Корневая директория проекта (TelegramBot_v2/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Настройки приложения.
    
    Загружает конфигурацию из переменных окружения и .env файла.
    Все настройки типизированы и валидируются при запуске.
    """
    
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # ========== Telegram ==========
    telegram_bot_token: str
    admin_user_id: int  # Основной админ (для обратной совместимости)
    admin_ids_str: str = ""  # Список админов через запятую: "123,456,789"
    admin_username: str = ""  # Username админа для обратной связи (без @)
    support_bot_username: str = ""  # Username бота поддержки (без @)
    
    # ========== AI Providers ==========
    # Gemini
    gemini_api_key: str = ""
    
    # ========== Payments ==========
    yookassa_provider_token: str = ""
    
    # ========== Database ==========
    @property
    def database_url(self) -> str:
        """
        Формирует URL базы данных.
        Если в окружении задан DATABASE_URL, проверяет его на относительность для SQLite.
        """
        import os
        url = os.getenv("DATABASE_URL")
        if url:
            # Если это SQLite и путь относительный (3 слэша), делаем его абсолютным
            if url.startswith("sqlite+aiosqlite:///"):
                path_part = url.replace("sqlite+aiosqlite:///", "")
                if not path_part.startswith("/"):
                    return f"sqlite+aiosqlite:///{BASE_DIR / path_part}"
            return url
        
        # Дефолтный путь
        return f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'database.sqlite'}"
    
    # ========== Application Settings ==========
    debug: bool = False
    free_generations: int = 1
    max_photos: int = 5
    max_retries: int = 3
    
    # ========== Timeouts (seconds) ==========
    ai_timeout: float = 60.0
    vision_timeout: float = 90.0  # Vision API может быть медленнее
    
    # ========== AI Models ==========
    # Gemini модели
    gemini_vision_model: str = "gemini-1.5-flash"
    gemini_text_model: str = "gemini-1.5-flash"
    
    # ========== Computed Properties ==========
    @property
    def is_production(self) -> bool:
        """Проверка на продакшен режим."""
        return not self.debug
    
    @property
    def data_dir(self) -> Path:
        """Путь к директории с данными."""
        return BASE_DIR / "data"
    
    @property
    def exports_dir(self) -> Path:
        """Путь к директории с экспортами PDF."""
        return BASE_DIR / "exports"
    
    @property
    def admin_ids(self) -> List[int]:
        """
        Список ID администраторов.
        
        Объединяет admin_user_id и admin_ids_str.
        admin_ids_str должен быть в формате: "123456,789012,345678"
        """
        admins = {self.admin_user_id}  # Основной админ всегда в списке
        
        if self.admin_ids_str:
            try:
                for id_str in self.admin_ids_str.split(","):
                    id_str = id_str.strip()
                    if id_str.isdigit():
                        admins.add(int(id_str))
            except (ValueError, AttributeError):
                pass
        
        return list(admins)


# Глобальный объект настроек (singleton)
settings = Settings()
