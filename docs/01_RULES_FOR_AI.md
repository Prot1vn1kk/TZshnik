# 🤖 ПРАВИЛА ДЛЯ НЕЙРОСЕТИ

> Этот документ содержит правила и стандарты кодирования, которым должна следовать нейросеть при написании кода проекта "ТЗшник v2.0".

---

## 📌 ОБЩИЕ ПРИНЦИПЫ

### 1. Язык и стиль
- **Весь код на английском** (имена переменных, функций, классов)
- **Комментарии на русском** (для понимания)
- **Docstrings на русском** (документация функций)
- Используй **type hints** везде

### 2. Форматирование
- **PEP 8** — основной стандарт
- Отступы: **4 пробела** (не табы)
- Максимальная длина строки: **100 символов**
- Пустые строки: 2 между классами, 1 между методами

### 3. Именование

```python
# Переменные и функции — snake_case
user_balance = 100
async def get_user_balance(user_id: int) -> int:
    pass

# Классы — PascalCase
class UserService:
    pass

# Константы — UPPER_SNAKE_CASE
MAX_PHOTOS = 5
FREE_GENERATIONS = 1

# Приватные методы — с underscore
def _validate_tz_quality(self, text: str) -> bool:
    pass
```

---

## 🏗 АРХИТЕКТУРНЫЕ ПРАВИЛА

### 1. Структура импортов

```python
# Порядок импортов (разделять пустой строкой):

# 1. Стандартная библиотека
import asyncio
import logging
from datetime import datetime
from typing import Optional, List

# 2. Сторонние библиотеки
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Локальные модули
from bot.config import settings
from database.models import User
from core.generator import TZGenerator
```

### 2. Конфигурация через Pydantic Settings

```python
# bot/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из .env файла."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Telegram
    telegram_bot_token: str
    admin_user_id: int
    
    # AI
    glm_api_key: str
    gemini_api_key: str
    
    # Database
    database_url: str = "sqlite+aiosqlite:///data/database.sqlite"
    
    # Settings
    debug: bool = False
    free_generations: int = 1


settings = Settings()
```

### 3. Async везде

```python
# ✅ ПРАВИЛЬНО — async функции
async def get_user(user_id: int) -> Optional[User]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        return result.scalar_one_or_none()

# ❌ НЕПРАВИЛЬНО — синхронный код
def get_user(user_id: int) -> Optional[User]:
    with Session() as session:
        return session.query(User).filter_by(telegram_id=user_id).first()
```

### 4. Dependency Injection через параметры

```python
# ✅ ПРАВИЛЬНО — зависимости передаются явно
class TZGenerator:
    def __init__(
        self,
        vision_provider: BaseVisionProvider,
        text_provider: BaseTextProvider,
        validator: TZValidator
    ):
        self.vision = vision_provider
        self.text = text_provider
        self.validator = validator

# ❌ НЕПРАВИЛЬНО — глобальные импорты внутри класса
class TZGenerator:
    def __init__(self):
        from core.ai_providers.glm import GLMProvider
        self.provider = GLMProvider()  # Жёсткая связь!
```

---

## 🔄 ОБРАБОТКА ОШИБОК

### 1. Кастомные исключения

```python
# core/exceptions.py

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
    """Недостаточно кредитов."""
    pass
```

### 2. Try-except с логированием

```python
import structlog

logger = structlog.get_logger()


async def analyze_image(self, image_bytes: bytes) -> str:
    """
    Анализирует изображение и возвращает описание товара.
    
    Args:
        image_bytes: Байты изображения
        
    Returns:
        Текстовое описание товара
        
    Raises:
        VisionAnalysisError: Если анализ не удался
    """
    try:
        result = await self._call_vision_api(image_bytes)
        
        if not result or len(result) < 50:
            raise VisionAnalysisError("Получен пустой или слишком короткий ответ")
        
        logger.info(
            "image_analyzed",
            result_length=len(result),
            provider=self.__class__.__name__
        )
        return result
        
    except httpx.TimeoutException as e:
        logger.error("vision_timeout", error=str(e))
        raise VisionAnalysisError(f"Таймаут при анализе: {e}") from e
        
    except httpx.HTTPStatusError as e:
        logger.error("vision_http_error", status=e.response.status_code)
        raise VisionAnalysisError(f"HTTP ошибка: {e.response.status_code}") from e
```

### 3. Fallback паттерн

```python
async def analyze_with_fallback(self, image_bytes: bytes) -> str:
    """Анализ с автоматическим fallback на резервный провайдер."""
    
    providers = [self.primary_provider, self.fallback_provider]
    last_error = None
    
    for provider in providers:
        try:
            result = await provider.analyze_image(image_bytes)
            if result:
                return result
        except AIProviderError as e:
            logger.warning(
                "provider_failed_trying_next",
                provider=provider.__class__.__name__,
                error=str(e)
            )
            last_error = e
            continue
    
    # Все провайдеры упали
    raise VisionAnalysisError(
        f"Все провайдеры недоступны. Последняя ошибка: {last_error}"
    )
```

---

## 📝 ЛОГИРОВАНИЕ

### 1. Использовать structlog

```python
# bot/main.py
import structlog

# Настройка при старте
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
        structlog.processors.JSONRenderer()  # или ConsoleRenderer() для дебага
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
```

### 2. Что логировать

```python
# ✅ ЛОГИРОВАТЬ:
logger.info("user_started_bot", user_id=user_id, username=username)
logger.info("generation_started", user_id=user_id, category=category)
logger.info("generation_completed", user_id=user_id, duration_sec=15.3)
logger.warning("low_balance", user_id=user_id, balance=0)
logger.error("payment_failed", user_id=user_id, error=str(e))

# ❌ НЕ ЛОГИРОВАТЬ:
logger.info(f"User {user_id} sent photo")  # Не структурировано
logger.debug(image_bytes)  # Бинарные данные
logger.info(api_key)  # Секреты!
```

---

## 🗄 РАБОТА С БАЗОЙ ДАННЫХ

### 1. Async сессии через context manager

```python
# database/database.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Контекстный менеджер для работы с БД."""
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

### 2. CRUD операции

```python
# database/crud.py
from sqlalchemy import select, update
from database.models import User, Generation
from database.database import get_session


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def create_user(telegram_id: int, username: Optional[str] = None) -> User:
    """Создать нового пользователя."""
    async with get_session() as session:
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=settings.free_generations  # 1 бесплатное ТЗ
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user


async def decrease_balance(user_id: int, amount: int = 1) -> bool:
    """Списать кредиты с баланса."""
    async with get_session() as session:
        result = await session.execute(
            update(User)
            .where(User.id == user_id, User.balance >= amount)
            .values(balance=User.balance - amount)
        )
        return result.rowcount > 0
```

---

## 🤖 AI ПРОВАЙДЕРЫ

### 1. Абстрактный базовый класс

```python
# core/ai_providers/base.py
from abc import ABC, abstractmethod
from typing import Optional


class BaseVisionProvider(ABC):
    """Абстрактный класс для Vision AI провайдеров."""
    
    @abstractmethod
    async def analyze_image(self, image_bytes: bytes) -> str:
        """
        Анализирует изображение и возвращает описание.
        
        Args:
            image_bytes: Байты изображения
            
        Returns:
            Текстовое описание содержимого
        """
        pass


class BaseTextProvider(ABC):
    """Абстрактный класс для Text AI провайдеров."""
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Генерирует текст по промпту.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            
        Returns:
            Сгенерированный текст
        """
        pass
```

### 2. Реализация провайдера

```python
# core/ai_providers/glm.py
import httpx
from core.ai_providers.base import BaseVisionProvider, BaseTextProvider


class GLMProvider(BaseVisionProvider, BaseTextProvider):
    """Провайдер Z.AI GLM-4 / GLM-4V."""
    
    BASE_URL = "https://open.z.ai/api/paas/v4"
    
    def __init__(self, api_key: str, timeout: float = 60.0):
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy инициализация HTTP клиента."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout
            )
        return self._client
    
    async def analyze_image(self, image_bytes: bytes) -> str:
        # Реализация анализа изображения
        pass
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        # Реализация генерации текста
        pass
    
    async def close(self):
        """Закрыть HTTP клиент."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

---

## 📱 AIOGRAM HANDLERS

### 1. Структура роутера

```python
# bot/handlers/start.py
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start.
    Регистрирует пользователя и показывает приветствие.
    """
    await state.clear()
    
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу создать ТЗ для инфографики твоего товара.\n\n"
        f"📸 Просто отправь фото товара и получи готовое ТЗ за 30 секунд!\n\n"
        f"💰 Твой баланс: {user.balance} ТЗ",
        reply_markup=get_main_keyboard()
    )
```

### 2. FSM States

```python
# bot/states.py
from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    """Состояния процесса генерации ТЗ."""
    
    waiting_photo = State()      # Ожидание фото
    waiting_more_photos = State() # Ожидание доп. фото
    waiting_category = State()    # Выбор категории
    generating = State()          # Процесс генерации
    waiting_feedback = State()    # Ожидание оценки
```

### 3. Middleware для сессии БД

```python
# bot/middleware.py
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.database import get_session


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для инъекции сессии БД в handler."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with get_session() as session:
            data["session"] = session
            return await handler(event, data)
```

---

## ✅ ВАЛИДАЦИЯ ТЗ

### 1. Структура валидатора

```python
# core/validator.py
from dataclasses import dataclass
from typing import List


@dataclass
class ValidationResult:
    """Результат валидации ТЗ."""
    is_valid: bool
    score: int  # 0-100
    found_sections: List[str]
    missing_sections: List[str]
    warnings: List[str]
    

class TZValidator:
    """Валидатор качества сгенерированного ТЗ."""
    
    REQUIRED_SECTIONS = [
        "товар",
        "целевая аудитория",
        "визуальная концепция",
        "главное фото",
        "инфографика",
        "тексты",
        "рекомендации",
        "a/b тест"
    ]
    
    MIN_LENGTH = 1500
    MAX_LENGTH = 5000
    
    def validate(self, tz_text: str) -> ValidationResult:
        """Валидирует ТЗ и возвращает результат."""
        # Реализация валидации
        pass
```

---

## 📄 PDF ЭКСПОРТ

### 1. Использовать FPDF2 (проще) или WeasyPrint (красивее)

```python
# core/pdf_export.py
from fpdf import FPDF
from pathlib import Path


class TZPDFExporter:
    """Экспортер ТЗ в PDF формат."""
    
    def __init__(self, output_dir: Path = Path("exports")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    async def export(
        self,
        tz_text: str,
        product_name: str,
        user_id: int
    ) -> Path:
        """
        Экспортирует ТЗ в PDF.
        
        Returns:
            Путь к созданному файлу
        """
        # Реализация экспорта
        pass
```

---

## 🧪 ТЕСТИРОВАНИЕ

### 1. Использовать pytest + pytest-asyncio

```python
# tests/test_validator.py
import pytest
from core.validator import TZValidator, ValidationResult


@pytest.fixture
def validator():
    return TZValidator()


def test_valid_tz(validator):
    """Тест валидного ТЗ."""
    tz_text = """
    1. ТОВАР
    Категория: Электроника...
    
    2. ЦЕЛЕВАЯ АУДИТОРИЯ
    ...
    """
    
    result = validator.validate(tz_text)
    assert result.is_valid
    assert result.score >= 80


def test_missing_sections(validator):
    """Тест ТЗ с пропущенными секциями."""
    tz_text = "Короткий текст без секций"
    
    result = validator.validate(tz_text)
    assert not result.is_valid
    assert len(result.missing_sections) > 0
```

### 2. Моки для AI провайдеров

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock
from core.ai_providers.base import BaseVisionProvider


@pytest.fixture
def mock_vision_provider():
    """Мок Vision провайдера."""
    provider = AsyncMock(spec=BaseVisionProvider)
    provider.analyze_image.return_value = "Тестовое описание товара..."
    return provider
```

---

## 🚀 ЗАПУСК ПРИЛОЖЕНИЯ

### 1. Точка входа

```python
# bot/main.py
import asyncio
import structlog
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from bot.config import settings
from bot.handlers import start, photo, generation, payment, history
from bot.middleware import DatabaseMiddleware
from database.database import init_db

logger = structlog.get_logger()


async def main():
    """Главная функция запуска бота."""
    
    # Инициализация БД
    await init_db()
    
    # Создание бота
    bot = Bot(
        token=settings.telegram_bot_token,
        parse_mode=ParseMode.HTML
    )
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Регистрация middleware
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # Регистрация роутеров
    dp.include_routers(
        start.router,
        photo.router,
        generation.router,
        payment.router,
        history.router
    )
    
    # Запуск
    logger.info("bot_starting")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚠️ ЧЕГО ИЗБЕГАТЬ

```python
# ❌ Глобальные переменные
bot = Bot(token="...")  # Плохо!

# ❌ Синхронные операции в async функциях
def get_user():  # Плохо в async контексте!
    pass

# ❌ Хардкод значений
if user.balance < 1:  # Лучше: settings.min_balance

# ❌ Игнорирование ошибок
try:
    await api_call()
except:  # Плохо — ловит всё!
    pass

# ❌ Большие функции (> 50 строк)
# Разбивай на маленькие!

# ❌ Дублирование кода
# Выноси в отдельные функции/классы

# ❌ Магические числа
await asyncio.sleep(30)  # Что за 30? Лучше: GENERATION_TIMEOUT = 30
```

---

## ✅ CHECKLIST ПЕРЕД КОММИТОМ

- [ ] Код проходит `ruff check .` без ошибок
- [ ] Все функции имеют type hints
- [ ] Все публичные функции имеют docstrings
- [ ] Нет хардкода секретов
- [ ] Логирование добавлено для важных операций
- [ ] Ошибки обрабатываются с fallback
- [ ] Тесты написаны и проходят

---

*Этот документ — основа для всех промптов разработки.*
