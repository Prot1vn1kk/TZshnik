# 🤖 ШАГ 3: AI ПРОВАЙДЕРЫ

> Настройка GLM-4V, Gemini и fallback chain

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать:
- Базовые классы для AI провайдеров
- Реализацию GLM-4V / GLM-4 (Z.AI)
- Реализацию Gemini (fallback)
- Chain с автоматическим fallback
- Тесты провайдеров

---

## 📁 СТРУКТУРА ФАЙЛОВ

После этого шага:

```
core/
├── __init__.py
├── exceptions.py           # Уже есть
├── ai_providers/
│   ├── __init__.py         # Фабрика провайдеров
│   ├── base.py             # Абстрактные классы
│   ├── glm.py              # Z.AI GLM провайдер
│   ├── gemini.py           # Google Gemini провайдер
│   └── chain.py            # Fallback chain
└── prompts.py              # Промпты для AI
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай модуль AI провайдеров для Telegram-бота.

КОНТЕКСТ:
Бот анализирует фото товаров и генерирует ТЗ для инфографики.
Нужна цепочка провайдеров с автоматическим fallback.

АРХИТЕКТУРА:
Primary: Z.AI GLM (ОФИЦИАЛЬНАЯ библиотека zhipuai>=2.1.5.20250131)
  - Vision: glm-4-6v / glm-4v-flash
  - Text: glm-4-plus / glm-4-flash
Fallback: Google Gemini 1.5 Flash (vision + text)

ВАЖНО:
- Используй ТОЛЬКО официальную библиотеку zhipuai
- НЕ используй httpx для прямых запросов к GLM API
- Асинхронность через loop.run_in_executor()

ЗАДАЧА:
1. Создай core/ai_providers/base.py:
   - Dataclass ProviderResponse (success, content, provider_name, tokens_used, error_message)
   - Enum ProviderStatus (available, rate_limited, error, disabled)
   - ABC BaseVisionProvider с методами:
     * analyze_image(image_bytes, prompt) -> ProviderResponse
     * analyze_multiple_images(images, prompt) -> ProviderResponse
     * health_check() -> ProviderStatus
   - ABC BaseTextProvider с методами:
     * generate(prompt, system_prompt, max_tokens, temperature) -> ProviderResponse
     * health_check() -> ProviderStatus

2. Создай core/ai_providers/glm.py:
   - Класс GLMProvider(BaseVisionProvider, BaseTextProvider)
   - Использует библиотеку: from zhipuai import ZhipuAI
   - Инициализация: self._client = ZhipuAI(api_key=api_key)
   - Vision модели: glm-4-6v (качество) / glm-4v-flash (скорость)
   - Text модели: glm-4-plus (качество) / glm-4-flash (скорость)
   - Поддержка нескольких изображений (до 5)
   - Изображения в формате base64 data URL
   - Асинхронность через asyncio.get_event_loop().run_in_executor()
   - Логирование

3. Создай core/ai_providers/gemini.py:
   - Класс GeminiProvider(BaseVisionProvider, BaseTextProvider)
   - Endpoint: https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent
   - Авторизация: ?key=API_KEY
   - Поддержка нескольких изображений
   - systemInstruction для system prompt
   - Обработка ответа (candidates → parts → text)

4. Создай core/ai_providers/chain.py:
   - Dataclass ChainConfig (max_retries, retry_delay)
   - Класс VisionProviderChain с методами:
     * analyze_image() - пробует провайдеров по очереди
     * analyze_multiple_images() - то же для нескольких фото
     * health_check_all() - проверка всех провайдеров
   - Класс TextProviderChain с методами:
     * generate() - пробует провайдеров по очереди
   - Логирование какой провайдер сработал
   - RuntimeError если все провайдеры упали

5. Создай core/ai_providers/__init__.py:
   - Функция create_vision_chain() -> VisionProviderChain
   - Функция create_text_chain() -> TextProviderChain
   - Использует settings для API ключей

6. Создай core/prompts.py:
   - VISION_ANALYSIS_PROMPT - промпт для анализа фото
   - TZ_SYSTEM_PROMPT - системный промпт для генерации
   - TZ_GENERATION_PROMPT - основной промпт (с placeholder'ами)
   - CATEGORY_SPECIFICS - специфика по категориям
   - Функция build_full_tz_prompt(description, category, marketplace)
   - Константы MIN_TZ_LENGTH, REQUIRED_SECTIONS, etc.

ПРОМПТЫ:
{Вставь содержимое docs/04_PROMPTS.md}

ТЕХНИЧЕСКИЕ ДЕТАЛИ GLM API (zhipuai библиотека):
- Установка: pip install zhipuai>=2.1.5.20250131
- Импорт: from zhipuai import ZhipuAI
- Инициализация: client = ZhipuAI(api_key="ключ")
- Синхронный вызов (запускать через executor!):
  response = client.chat.completions.create(
    model="glm-4-6v",
    messages=[{
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
        {"type": "text", "text": "Описание..."}
      ]
    }],
    temperature=0.3,
    max_tokens=2000
  )
- Response: response.choices[0].message.content
- Tokens: response.usage.total_tokens
- Асинхронность:
  loop = asyncio.get_event_loop()
  response = await loop.run_in_executor(None, lambda: client.chat.completions.create(...))

ТЕХНИЧЕСКИЕ ДЕТАЛИ GEMINI API:
- Request format:
  {
    "contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": "base64..."}}, {"text": "..."}]}],
    "systemInstruction": {"parts": [{"text": "..."}]},
    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2000}
  }
- Response: data["candidates"][0]["content"]["parts"][0]["text"]

ПРАВИЛА:
{Вставь правила из docs/01_RULES_FOR_AI.md — секции про AI провайдеры и async}

ТРЕБОВАНИЯ:
1. Использовать ОФИЦИАЛЬНУЮ библиотеку zhipuai (НЕ httpx для GLM!)
2. Асинхронность через asyncio.get_event_loop().run_in_executor()
3. Инициализация клиента: ZhipuAI(api_key=key)
4. Логирование через structlog
5. Graceful handling ошибок (не падать, возвращать ProviderResponse с success=False)
6. Type hints везде
7. Docstrings на русском
8. Для Gemini можно использовать httpx или google-generativeai

Создай полный код всех файлов.
```

---

## 📦 КЛЮЧЕВЫЕ ФАЙЛЫ

### core/ai_providers/base.py (полная версия)

```python
"""
Базовые классы для AI провайдеров.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class ProviderStatus(Enum):
    """Статус доступности провайдера."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ProviderResponse:
    """
    Ответ от AI провайдера.
    
    Attributes:
        success: Успешен ли запрос
        content: Сгенерированный контент
        provider_name: Имя провайдера
        tokens_used: Использовано токенов (опционально)
        error_message: Сообщение об ошибке (если success=False)
    """
    success: bool
    content: str
    provider_name: str
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None


class BaseVisionProvider(ABC):
    """
    Абстрактный базовый класс для Vision провайдеров.
    
    Vision провайдер анализирует изображения и возвращает
    текстовое описание их содержимого.
    """
    
    name: str = "base_vision"
    
    @abstractmethod
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Анализирует одно изображение.
        
        Args:
            image_bytes: Байты изображения (JPEG/PNG)
            prompt: Дополнительный промпт для анализа
            
        Returns:
            ProviderResponse с результатом анализа
        """
        pass
    
    @abstractmethod
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Анализирует несколько изображений вместе.
        
        Args:
            images: Список байтов изображений
            prompt: Общий промпт для анализа
            
        Returns:
            ProviderResponse с объединённым результатом
        """
        pass
    
    async def health_check(self) -> ProviderStatus:
        """
        Проверка доступности провайдера.
        
        Returns:
            ProviderStatus с текущим состоянием
        """
        try:
            # Минимальный тестовый запрос с 1x1 белым пикселем
            test_image = self._create_test_image()
            response = await self.analyze_image(test_image, "Test")
            
            if response.success:
                return ProviderStatus.AVAILABLE
            elif "rate" in (response.error_message or "").lower():
                return ProviderStatus.RATE_LIMITED
            else:
                return ProviderStatus.ERROR
                
        except Exception:
            return ProviderStatus.ERROR
    
    @staticmethod
    def _create_test_image() -> bytes:
        """Создаёт минимальное тестовое изображение (1x1 белый PNG)."""
        return bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])


class BaseTextProvider(ABC):
    """
    Абстрактный базовый класс для Text провайдеров.
    
    Text провайдер генерирует текст на основе промпта.
    """
    
    name: str = "base_text"
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """
        Генерирует текст по промпту.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (роль AI)
            max_tokens: Максимум токенов в ответе
            temperature: Креативность (0.0-1.0)
            
        Returns:
            ProviderResponse с сгенерированным текстом
        """
        pass
    
    async def health_check(self) -> ProviderStatus:
        """Проверка доступности провайдера."""
        try:
            response = await self.generate("Say 'OK'", max_tokens=10)
            
            if response.success:
                return ProviderStatus.AVAILABLE
            elif "rate" in (response.error_message or "").lower():
                return ProviderStatus.RATE_LIMITED
            else:
                return ProviderStatus.ERROR
                
        except Exception:
            return ProviderStatus.ERROR
```

### core/prompts.py (ключевые части)

```python
"""
Промпты для AI генерации ТЗ.
"""

from typing import Dict

# ==================== КОНСТАНТЫ ====================

MIN_TZ_LENGTH = 1500
MAX_TZ_LENGTH = 5000
MIN_ANALYSIS_LENGTH = 200
MAX_PHOTOS = 5
INFOGRAPHIC_SLIDES_COUNT = 5

REQUIRED_SECTIONS = [
    "товар",
    "целевая аудитория", 
    "визуальная концепция",
    "главное фото",
    "инфографика",
    "готовые тексты",
    "рекомендации",
    "a/b тест"
]

# ==================== VISION ПРОМПТ ====================

VISION_ANALYSIS_PROMPT = """Ты — эксперт по маркетплейсам Wildberries и Ozon.

Проанализируй фото товара и дай ПОДРОБНОЕ описание для создания инфографики карточки товара.

ОБЯЗАТЕЛЬНО опиши:

1. ЧТО ЭТО ЗА ТОВАР
   - Точная категория
   - Название товара
   - Тип/вид
   - Материал (если видно)
   - Размер/габариты (если можно оценить)

2. ВНЕШНИЙ ВИД
   - Основные цвета
   - Форма
   - Текстура
   - Детали дизайна
   - Логотипы/надписи

3. ОСОБЕННОСТИ И ПРЕИМУЩЕСТВА
   - Что делает товар особенным
   - Видимые функции
   - Качество исполнения

4. ДЛЯ КОГО ЭТОТ ТОВАР
   - Пол покупателя
   - Возрастная группа
   - Ситуации использования

5. КОНКУРЕНТНЫЕ ПРЕИМУЩЕСТВА
   - Чем выделяется среди аналогов
   - Ценовой сегмент

Пиши на русском языке.
Будь конкретным, избегай общих фраз.
Описание должно быть 300-500 слов."""

# ==================== TEXT ПРОМПТЫ ====================

TZ_SYSTEM_PROMPT = """Ты — профессиональный маркетолог с 10-летним опытом работы с Wildberries и Ozon.

Твоя задача — создавать детальные ТЗ для дизайнеров инфографики.

ПРАВИЛА:
1. Пиши КОНКРЕТНО — никаких "можно использовать"
2. Указывай ТОЧНЫЕ цвета (HEX)
3. Давай ИЗМЕРИМЫЕ рекомендации
4. Учитывай требования маркетплейсов
5. Каждый слайд решает ОДНУ задачу
6. Тексты должны быть ПРОДАЮЩИМИ"""

TZ_GENERATION_PROMPT = """На основе описания товара создай ПОЛНОЕ техническое задание для инфографики.

ОПИСАНИЕ ТОВАРА:
{product_description}

КАТЕГОРИЯ: {category}

---

СТРУКТУРА ТЗ (все 8 секций обязательны):

## 1. 📦 ТОВАР
- Категория и подкатегория
- Название для карточки
- Ключевые характеристики (5-7 пунктов)
- УТП — 1 предложение

## 2. 🎯 ЦЕЛЕВАЯ АУДИТОРИЯ
- Пол и возраст
- Уровень дохода
- Боли и проблемы (3-5)
- Мотивация к покупке (3-5)
- Возражения и как их снять

## 3. 🎨 ВИЗУАЛЬНАЯ КОНЦЕПЦИЯ
- Стиль дизайна
- Цвета (HEX): фон, акцент, текст
- Шрифты: заголовки, текст
- Настроение

## 4. 📸 ГЛАВНОЕ ФОТО
- Ракурс товара
- Фон (HEX)
- Композиция
- Главный заголовок (точный текст)
- Подзаголовок

## 5. 📊 ИНФОГРАФИКА (5 слайдов)
Для каждого слайда:
- Цель
- Заголовок (точный текст)
- Контент
- Визуал

## 6. ✍️ ГОТОВЫЕ ТЕКСТЫ
- Заголовок карточки (до 60 символов)
- Описание (до 1000 символов)
- Буллет-поинты (5 штук)

## 7. ⚠️ РЕКОМЕНДАЦИИ ДИЗАЙНЕРУ
- ✅ Важно (3 пункта)
- ❌ Нельзя (3 пункта)
- 💡 Советы

## 8. 🧪 A/B ТЕСТЫ
- 3 идеи для тестирования

---
Минимум 2000 символов. Все секции заполнены полностью."""

# ==================== КАТЕГОРИИ ====================

CATEGORIES = {
    "clothes": {"name": "👕 Одежда", "key": "clothes"},
    "electronics": {"name": "📱 Электроника", "key": "electronics"},
    "cosmetics": {"name": "💄 Косметика", "key": "cosmetics"},
    "home": {"name": "🏠 Дом", "key": "home"},
    "kids": {"name": "👶 Детям", "key": "kids"},
    "sports": {"name": "⚽ Спорт", "key": "sports"},
    "other": {"name": "📦 Другое", "key": "other"}
}

CATEGORY_SPECIFICS: Dict[str, str] = {
    "clothes": "\nСПЕЦИФИКА: размерная сетка, материал, сезонность.",
    "electronics": "\nСПЕЦИФИКА: характеристики, комплектация, гарантия.",
    "cosmetics": "\nСПЕЦИФИКА: состав, способ применения, результат.",
    "home": "\nСПЕЦИФИКА: размеры в см, материал, уход.",
    "kids": "\nСПЕЦИФИКА: возраст, безопасность, развивающие функции.",
    "sports": "\nСПЕЦИФИКА: вид спорта, уровень, характеристики.",
    "other": ""
}


def build_tz_prompt(
    product_description: str,
    category: str,
    marketplace: str = "Wildberries и Ozon"
) -> str:
    """
    Собирает полный промпт для генерации ТЗ.
    
    Args:
        product_description: Описание товара от Vision
        category: Ключ категории
        marketplace: Маркетплейс(ы)
        
    Returns:
        Готовый промпт для Text провайдера
    """
    base_prompt = TZ_GENERATION_PROMPT.format(
        product_description=product_description,
        category=CATEGORIES.get(category, CATEGORIES["other"])["name"]
    )
    
    specifics = CATEGORY_SPECIFICS.get(category, "")
    
    return base_prompt + specifics
```

---

## ✅ ЧЕКЛИСТ ВЫПОЛНЕНИЯ

- [ ] Все файлы в `core/ai_providers/` созданы
- [ ] `core/prompts.py` содержит все промпты
- [ ] GLMProvider успешно анализирует тестовое фото
- [ ] GeminiProvider работает как fallback
- [ ] Chain переключается на fallback при ошибке
- [ ] Логи показывают какой провайдер использован

---

## 🧪 ТЕСТИРОВАНИЕ

```python
# Тест провайдеров
import asyncio
from core.ai_providers import create_vision_chain, create_text_chain

async def test_providers():
    # Тест vision
    vision = create_vision_chain()
    
    with open("test_image.jpg", "rb") as f:
        image_bytes = f.read()
    
    result = await vision.analyze_image(image_bytes)
    print(f"Vision result: {result.success}, provider: {result.provider_name}")
    print(f"Content: {result.content[:200]}...")
    
    # Тест text
    text = create_text_chain()
    result = await text.generate("Скажи 'Привет'")
    print(f"Text result: {result.success}, provider: {result.provider_name}")

asyncio.run(test_providers())
```

---

## ➡️ СЛЕДУЮЩИЙ ШАГ

После успешного выполнения переходи к [STEP_04_HANDLERS.md](STEP_04_HANDLERS.md)

---

*Шаг 3 из 7*
