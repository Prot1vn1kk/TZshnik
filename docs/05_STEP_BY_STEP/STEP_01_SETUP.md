# 🚀 ШАГ 1: НАСТРОЙКА ПРОЕКТА

> Создание структуры проекта, настройка окружения и конфигурации

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать базовую структуру проекта с:
- Правильной структурой папок
- Конфигурацией из `.env`
- Базовыми зависимостями
- Логированием

---

## 📁 СТРУКТУРА ФАЙЛОВ

После этого шага должны быть созданы:

```
TelegramBot_v2/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Точка входа
│   └── config.py            # Настройки
├── core/
│   ├── __init__.py
│   └── exceptions.py        # Кастомные исключения
├── database/
│   └── __init__.py
├── utils/
│   └── __init__.py
├── data/                    # Папка для SQLite
├── exports/                 # Папка для PDF
├── .env                     # Секреты (создаётся вручную)
├── .env.example             # Пример .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай базовую структуру Telegram-бота на Python.

КОНТЕКСТ ПРОЕКТА:
Это Telegram-бот "ТЗшник" для генерации технических заданий для инфографики товаров на маркетплейсах.

ТЕХНОЛОГИИ:
- Python 3.11+
- aiogram 3.x (Telegram Bot API)
- SQLAlchemy 2.0 (async) + aiosqlite
- pydantic-settings (конфигурация)
- structlog (логирование)

ЗАДАЧА:
1. Создай структуру папок согласно схеме выше
2. Создай requirements.txt со всеми зависимостями
3. Создай bot/config.py с Pydantic Settings
4. Создай .env.example с примером переменных
5. Создай .gitignore для Python проекта
6. Создай bot/main.py с базовой инициализацией бота (пока без handlers)
7. Создай core/exceptions.py с кастомными исключениями
8. Создай README.md с инструкцией по запуску

ПРАВИЛА КОДИРОВАНИЯ:
{Вставь содержимое файла docs/01_RULES_FOR_AI.md}

КОНФИГУРАЦИЯ (.env):
- TELEGRAM_BOT_TOKEN - токен бота
- ADMIN_USER_ID - ID админа в Telegram
- GLM_API_KEY - ключ Z.AI GLM
- GEMINI_API_KEY - ключ Google Gemini
- YOOKASSA_PROVIDER_TOKEN - токен YooKassa
- DATABASE_URL - путь к SQLite (по умолчанию sqlite+aiosqlite:///data/database.sqlite)
- DEBUG - режим отладки (true/false)
- FREE_GENERATIONS - количество бесплатных ТЗ (по умолчанию 1)

ТРЕБОВАНИЯ К КОДУ:
1. Все imports в правильном порядке (stdlib → third-party → local)
2. Type hints везде
3. Docstrings на русском
4. Async функции где нужно
5. Логирование через structlog
6. Обработка ошибок

Начни с создания файлов. Выводи полный код каждого файла.
```

---

## 📦 ОЖИДАЕМЫЕ ФАЙЛЫ

### requirements.txt

```txt
# Telegram Bot
aiogram>=3.4.0

# Database
sqlalchemy>=2.0.0
aiosqlite>=0.19.0

# Configuration
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0

# AI Providers
httpx>=0.25.0

# PDF Export
fpdf2>=2.7.0

# Logging
structlog>=23.1.0

# Development
pytest>=7.4.0
pytest-asyncio>=0.21.0
ruff>=0.1.0
```

### bot/config.py

```python
"""
Конфигурация приложения.
Загружает настройки из .env файла.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки приложения."""
    
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Telegram
    telegram_bot_token: str
    admin_user_id: int
    
    # AI Providers
    glm_api_key: str = ""
    gemini_api_key: str = ""
    
    # Payments
    yookassa_provider_token: str = ""
    
    # Database
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/database.sqlite"
    
    # Application Settings
    debug: bool = False
    free_generations: int = 1
    max_photos: int = 5
    
    # Timeouts (seconds)
    ai_timeout: float = 60.0
    
    @property
    def is_production(self) -> bool:
        """Продакшен режим."""
        return not self.debug


# Глобальный объект настроек
settings = Settings()
```

### core/exceptions.py

```python
"""
Кастомные исключения проекта.
"""


class TZGeneratorError(Exception):
    """Базовое исключение генератора ТЗ."""
    pass


class AIProviderError(TZGeneratorError):
    """Ошибка AI провайдера."""
    pass


class VisionAnalysisError(AIProviderError):
    """Ошибка анализа изображения."""
    pass


class TextGenerationError(AIProviderError):
    """Ошибка генерации текста."""
    pass


class ValidationError(TZGeneratorError):
    """ТЗ не прошло валидацию."""
    pass


class InsufficientBalanceError(TZGeneratorError):
    """Недостаточно кредитов на балансе."""
    pass


class PaymentError(TZGeneratorError):
    """Ошибка платежа."""
    pass


class DatabaseError(TZGeneratorError):
    """Ошибка базы данных."""
    pass
```

### bot/main.py

```python
"""
Точка входа Telegram-бота.
"""

import asyncio
import sys
from pathlib import Path

import structlog
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.config import settings


# Настройка логирования
def setup_logging() -> None:
    """Настройка structlog."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()


async def main() -> None:
    """Главная функция запуска бота."""
    
    # Настройка логирования
    setup_logging()
    
    logger.info(
        "starting_bot",
        debug=settings.debug,
        admin_id=settings.admin_user_id
    )
    
    # Создание необходимых директорий
    Path("data").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    
    # Инициализация бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализация диспетчера
    dp = Dispatcher()
    
    # TODO: Инициализация БД
    # await init_db()
    
    # TODO: Регистрация middleware
    # dp.message.middleware(DatabaseMiddleware())
    
    # TODO: Регистрация роутеров
    # dp.include_routers(start.router, photo.router, ...)
    
    # Запуск
    logger.info("bot_started")
    
    try:
        # Удаляем вебхук на случай если был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запуск polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error("bot_error", error=str(e))
        raise
        
    finally:
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен")
```

### .env.example

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_USER_ID=123456789

# AI Providers
GLM_API_KEY=your_glm_api_key
GEMINI_API_KEY=your_gemini_api_key

# Payments (YooKassa через BotFather)
YOOKASSA_PROVIDER_TOKEN=your_yookassa_token

# Database
DATABASE_URL=sqlite+aiosqlite:///data/database.sqlite

# Settings
DEBUG=true
FREE_GENERATIONS=1
```

### .gitignore

```gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Virtual environments
venv/
.venv/
env/

# Environment variables
.env

# Database
*.sqlite
*.db
data/

# Exports
exports/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Logs
*.log
logs/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Build
dist/
build/
*.egg-info/

# OS
.DS_Store
Thumbs.db
```

---

## ✅ ЧЕКЛИСТ ВЫПОЛНЕНИЯ

После выполнения этого шага проверь:

- [ ] Все папки созданы (`bot/`, `core/`, `database/`, `utils/`, `data/`, `exports/`)
- [ ] `requirements.txt` содержит все зависимости
- [ ] `.env` создан и заполнен реальными токенами
- [ ] `bot/config.py` загружает настройки без ошибок
- [ ] `bot/main.py` запускается (`python bot/main.py`)
- [ ] Бот отвечает в Telegram (пока без команд, просто запускается)

---

## 🧪 ТЕСТИРОВАНИЕ

```bash
# Установка зависимостей
pip install -r requirements.txt

# Проверка конфигурации
python -c "from bot.config import settings; print(settings.telegram_bot_token[:10] + '...')"

# Запуск бота
python bot/main.py
```

---

## ➡️ СЛЕДУЮЩИЙ ШАГ

После успешного выполнения переходи к [STEP_02_DATABASE.md](STEP_02_DATABASE.md)

---

*Шаг 1 из 7*
