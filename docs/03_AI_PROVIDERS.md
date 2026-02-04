# 🤖 AI ПРОВАЙДЕРЫ

> Настройка и использование AI моделей для анализа фото и генерации ТЗ

---

## 📊 ОБЗОР ПРОВАЙДЕРОВ

| Провайдер | Модель | Назначение | Приоритет | Лимиты |
|-----------|--------|------------|-----------|--------|
| **Z.AI GLM** | glm-4-6v / glm-4-plus | Vision + Text | Primary | По подписке |
| **Z.AI GLM Flash** | glm-4v-flash / glm-4-flash | Vision + Text (быстрые) | Primary | По подписке |
| **Google Gemini** | gemini-1.5-flash | Vision + Text | Fallback | 60 RPM бесплатно |

---

## 🔑 API КЛЮЧИ

### Z.AI (GLM) - ОФИЦИАЛЬНАЯ БИБЛИОТЕКА

**Установка библиотеки:**
```bash
pip install zhipuai>=2.1.5.20250131
```

- **Получить ключ:** https://z.ai/manage-apikey/apikey-list
- **Документация:** https://open.bigmodel.cn/dev/api
- **Модели:**
  - `glm-4-6v` — Vision GLM-4.6V (лучшее качество для анализа изображений)
  - `glm-4v-flash` — Vision Fast (быстрый анализ изображений)
  - `glm-4-plus` — Text (лучшее качество генерации текста)
  - `glm-4-air` — Text (средний баланс)
  - `glm-4-flash` — Text Fast (быстрая генерация)

**Особенности библиотеки zhipuai:**
- ✅ Полная поддержка всех моделей GLM
- ✅ Совместима с aiogram (через async/await)
- ✅ Встроенная обработка ошибок
- ✅ Официальная поддержка от Z.ai

### Google Gemini
- **Получить:** https://aistudio.google.com/apikey
- **Документация:** https://ai.google.dev/docs
- **Модели:**
  - `gemini-1.5-flash` — Быстрый, бесплатный, Vision + Text
  - `gemini-1.5-pro` — Качественнее, меньше лимиты

---

## 🏗 АРХИТЕКТУРА

```
┌─────────────────────────────────────────────────────────────────┐
│                      AIProviderChain                            │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  VisionChain    │    │   TextChain     │                    │
│  │                 │    │                 │                    │
│  │  1. GLM-4V ────►│    │  1. GLM-4 ─────►│                    │
│  │       │         │    │       │         │                    │
│  │       ▼ fail    │    │       ▼ fail    │                    │
│  │  2. Gemini ────►│    │  2. Gemini ────►│                    │
│  │                 │    │                 │                    │
│  └─────────────────┘    └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 БАЗОВЫЕ КЛАССЫ

```python
# core/ai_providers/base.py

from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


class ProviderStatus(Enum):
    """Статус провайдера."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ProviderResponse:
    """Ответ от AI провайдера."""
    success: bool
    content: str
    provider_name: str
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None


class BaseVisionProvider(ABC):
    """Абстрактный класс для Vision провайдеров."""
    
    name: str = "base_vision"
    
    @abstractmethod
    async def analyze_image(
        self, 
        image_bytes: bytes,
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Анализирует изображение и возвращает описание.
        
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
        """Проверка доступности провайдера."""
        try:
            # Минимальный тестовый запрос
            test_image = self._create_test_image()
            response = await self.analyze_image(test_image, "Test")
            return ProviderStatus.AVAILABLE if response.success else ProviderStatus.ERROR
        except Exception:
            return ProviderStatus.ERROR
    
    def _create_test_image(self) -> bytes:
        """Создаёт минимальное тестовое изображение."""
        # 1x1 белый пиксель PNG
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
    """Абстрактный класс для Text провайдеров."""
    
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
            return ProviderStatus.AVAILABLE if response.success else ProviderStatus.ERROR
        except Exception:
            return ProviderStatus.ERROR
```

---

## 🔷 Z.AI GLM ПРОВАЙДЕР (ОФИЦИАЛЬНАЯ БИБЛИОТЕКА)

```python
# core/ai_providers/glm.py

import asyncio
import base64
import structlog
from typing import Optional, List
from zhipuai import ZhipuAI

from core.ai_providers.base import (
    BaseVisionProvider, 
    BaseTextProvider, 
    ProviderResponse
)

logger = structlog.get_logger()


class GLMProvider(BaseVisionProvider, BaseTextProvider):
    """
    Провайдер Z.AI GLM-4 / GLM-4V.
    
    Использует ОФИЦИАЛЬНУЮ библиотеку zhipuai>=2.1.5.20250131
    Документация: https://open.bigmodel.cn/dev/api
    """
    
    name = "glm"
    
    # Модели
    VISION_MODEL = "glm-4-6v"      # GLM-4.6V Vision (рекомендуется)
    VISION_FAST = "glm-4v-flash"   # Быстрый Vision
    TEXT_MODEL = "glm-4-plus"      # GLM-4 Plus (качественный)
    TEXT_FAST = "glm-4-flash"      # Быстрый Text
    
    def __init__(
        self, 
        api_key: str,
        use_fast_models: bool = False
    ):
        """
        Инициализация провайдера.
        
        Args:
            api_key: API ключ Z.AI
            use_fast_models: Использовать flash модели (быстрее, дешевле)
        """
        self.api_key = api_key
        self.use_fast_models = use_fast_models
        self._client = ZhipuAI(api_key=api_key)
        
        # Выбор моделей
        self.vision_model = self.VISION_FAST if use_fast_models else self.VISION_MODEL
        self.text_model = self.TEXT_FAST if use_fast_models else self.TEXT_MODEL
    
    async def analyze_image(
        self, 
        image_bytes: bytes,
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """Анализ одного изображения."""
        return await self.analyze_multiple_images([image_bytes], prompt)
    
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Анализ нескольких изображений.
        
        GLM-4.6V поддерживает несколько изображений в одном запросе.
        """
        if not prompt:
            prompt = "Опиши подробно что изображено на фото."
        
        # Формируем content с изображениями (base64)
        content = []
        for img_bytes in images[:5]:  # Максимум 5 фото
            base64_image = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
        
        content.append({
            "type": "text",
            "text": prompt
        })
        
        try:
            # Асинхронный вызов через executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
            )
            
            result_text = response.choices[0].message.content
            tokens_used = getattr(response.usage, 'total_tokens', None)
            
            logger.info(
                "glm_vision_success",
                model=self.vision_model,
                images_count=len(images),
                tokens=tokens_used
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("glm_vision_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """Генерация текста."""
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            # Асинхронный вызов через executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.text_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            )
            
            result_text = response.choices[0].message.content
            tokens_used = getattr(response.usage, 'total_tokens', None)
            
            logger.info(
                "glm_text_success",
                model=self.text_model,
                tokens=tokens_used,
                result_length=len(result_text)
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("glm_text_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
    
    async def close(self):
        """Закрыть клиент (не требуется для zhipuai)."""
        pass
            "temperature": 0.7
        }
        
        try:
            # Асинхронный вызов через executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
            )
            
            result_text = response.choices[0].message.content
            tokens_used = getattr(response.usage, 'total_tokens', None)
            
            logger.info(
                "glm_vision_success",
                model=self.vision_model,
                images_count=len(images),
                tokens=tokens_used
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("glm_vision_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """Генерация текста."""
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            # Асинхронный вызов через executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.text_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            )
            
            result_text = response.choices[0].message.content
            tokens_used = getattr(response.usage, 'total_tokens', None)
            
            logger.info(
                "glm_text_success",
                model=self.text_model,
                tokens=tokens_used,
                result_length=len(result_text)
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("glm_text_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
    
    async def close(self):
        """Закрыть клиент (не требуется для zhipuai)."""
        pass
```

---

## 🔶 GOOGLE GEMINI ПРОВАЙДЕР (FALLBACK)

```python
# core/ai_providers/gemini.py

import base64
import httpx
import structlog
from typing import Optional, List

from core.ai_providers.base import (
    BaseVisionProvider, 
    BaseTextProvider, 
    ProviderResponse
)

logger = structlog.get_logger()


class GeminiProvider(BaseVisionProvider, BaseTextProvider):
    """
    Провайдер Google Gemini.
    
    Используется как fallback когда GLM недоступен.
    Бесплатный tier: 60 RPM, 1M tokens/day.
    
    Документация: https://ai.google.dev/docs
    """
    
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODEL = "gemini-1.5-flash"
    
    def __init__(
        self, 
        api_key: str, 
        timeout: float = 60.0
    ):
        """
        Инициализация провайдера.
        
        Args:
            api_key: API ключ Google AI Studio
            timeout: Таймаут запроса в секундах
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy инициализация HTTP клиента."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self.timeout
            )
        return self._client
    
    async def analyze_image(
        self, 
        image_bytes: bytes,
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """Анализ одного изображения."""
        return await self.analyze_multiple_images([image_bytes], prompt)
    
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Анализ нескольких изображений.
        
        Gemini поддерживает множественные изображения.
        """
        if not prompt:
            prompt = "Опиши подробно что изображено на фото."
        
        # Формируем parts с изображениями
        parts = []
        
        for img_bytes in images:
            base64_image = base64.b64encode(img_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64_image
                }
            })
        
        parts.append({"text": prompt})
        
        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2000
            }
        }
        
        url = f"/models/{self.MODEL}:generateContent?key={self.api_key}"
        
        try:
            client = await self._get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Извлекаем текст из ответа
            candidates = data.get("candidates", [])
            if not candidates:
                return ProviderResponse(
                    success=False,
                    content="",
                    provider_name=self.name,
                    error_message="No candidates in response"
                )
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            result_text = "".join(p.get("text", "") for p in parts)
            
            # Токены из usageMetadata
            usage = data.get("usageMetadata", {})
            tokens_used = usage.get("totalTokenCount")
            
            logger.info(
                "gemini_vision_success",
                images_count=len(images),
                tokens=tokens_used
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("gemini_vision_http_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
            
        except Exception as e:
            logger.error("gemini_vision_error", error=str(e))
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=str(e)
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """Генерация текста."""
        
        # Gemini использует systemInstruction для системного промпта
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
        
        url = f"/models/{self.MODEL}:generateContent?key={self.api_key}"
        
        try:
            client = await self._get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            candidates = data.get("candidates", [])
            if not candidates:
                return ProviderResponse(
                    success=False,
                    content="",
                    provider_name=self.name,
                    error_message="No candidates in response"
                )
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            result_text = "".join(p.get("text", "") for p in parts)
            
            usage = data.get("usageMetadata", {})
            tokens_used = usage.get("totalTokenCount")
            
            logger.info(
                "gemini_text_success",
                tokens=tokens_used,
                result_length=len(result_text)
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("gemini_text_http_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
            
        except Exception as e:
            logger.error("gemini_text_error", error=str(e))
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=str(e)
            )
    
    async def close(self):
        """Закрыть HTTP клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
```

---

## 🔗 CHAIN ПРОВАЙДЕРОВ (FALLBACK ЛОГИКА)

```python
# core/ai_providers/chain.py

import structlog
from typing import List, Optional
from dataclasses import dataclass

from core.ai_providers.base import (
    BaseVisionProvider, 
    BaseTextProvider, 
    ProviderResponse,
    ProviderStatus
)

logger = structlog.get_logger()


@dataclass
class ChainConfig:
    """Конфигурация chain провайдеров."""
    max_retries: int = 2
    retry_delay: float = 1.0


class VisionProviderChain:
    """
    Chain Vision провайдеров с автоматическим fallback.
    
    Если первый провайдер недоступен — пробует следующий.
    """
    
    def __init__(
        self, 
        providers: List[BaseVisionProvider],
        config: Optional[ChainConfig] = None
    ):
        """
        Args:
            providers: Список провайдеров в порядке приоритета
            config: Конфигурация chain
        """
        self.providers = providers
        self.config = config or ChainConfig()
        self._provider_status: dict[str, ProviderStatus] = {}
    
    async def analyze_image(
        self, 
        image_bytes: bytes,
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """Анализ с автоматическим fallback."""
        return await self.analyze_multiple_images([image_bytes], prompt)
    
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """
        Анализирует изображения, пробуя провайдеров по очереди.
        
        Returns:
            ProviderResponse от первого успешного провайдера
            
        Raises:
            RuntimeError: Если все провайдеры недоступны
        """
        last_error = None
        
        for provider in self.providers:
            # Пропускаем если провайдер помечен как недоступный
            status = self._provider_status.get(provider.name)
            if status == ProviderStatus.DISABLED:
                continue
            
            logger.info(
                "trying_vision_provider",
                provider=provider.name,
                images_count=len(images)
            )
            
            for attempt in range(self.config.max_retries):
                response = await provider.analyze_multiple_images(images, prompt)
                
                if response.success and response.content:
                    logger.info(
                        "vision_provider_success",
                        provider=provider.name,
                        attempt=attempt + 1
                    )
                    return response
                
                last_error = response.error_message
                logger.warning(
                    "vision_provider_attempt_failed",
                    provider=provider.name,
                    attempt=attempt + 1,
                    error=last_error
                )
            
            # Провайдер не ответил после всех попыток
            logger.error(
                "vision_provider_failed",
                provider=provider.name,
                error=last_error
            )
        
        # Все провайдеры недоступны
        raise RuntimeError(
            f"Все Vision провайдеры недоступны. Последняя ошибка: {last_error}"
        )
    
    async def health_check_all(self) -> dict[str, ProviderStatus]:
        """Проверить доступность всех провайдеров."""
        for provider in self.providers:
            status = await provider.health_check()
            self._provider_status[provider.name] = status
            logger.info(
                "provider_health_check",
                provider=provider.name,
                status=status.value
            )
        return self._provider_status


class TextProviderChain:
    """Chain Text провайдеров с автоматическим fallback."""
    
    def __init__(
        self, 
        providers: List[BaseTextProvider],
        config: Optional[ChainConfig] = None
    ):
        self.providers = providers
        self.config = config or ChainConfig()
        self._provider_status: dict[str, ProviderStatus] = {}
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """
        Генерирует текст, пробуя провайдеров по очереди.
        """
        last_error = None
        
        for provider in self.providers:
            status = self._provider_status.get(provider.name)
            if status == ProviderStatus.DISABLED:
                continue
            
            logger.info("trying_text_provider", provider=provider.name)
            
            for attempt in range(self.config.max_retries):
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                if response.success and response.content:
                    logger.info(
                        "text_provider_success",
                        provider=provider.name,
                        attempt=attempt + 1,
                        length=len(response.content)
                    )
                    return response
                
                last_error = response.error_message
                logger.warning(
                    "text_provider_attempt_failed",
                    provider=provider.name,
                    attempt=attempt + 1,
                    error=last_error
                )
            
            logger.error(
                "text_provider_failed",
                provider=provider.name,
                error=last_error
            )
        
        raise RuntimeError(
            f"Все Text провайдеры недоступны. Последняя ошибка: {last_error}"
        )
    
    async def health_check_all(self) -> dict[str, ProviderStatus]:
        """Проверить доступность всех провайдеров."""
        for provider in self.providers:
            status = await provider.health_check()
            self._provider_status[provider.name] = status
        return self._provider_status
```

---

## 🏭 ФАБРИКА ПРОВАЙДЕРОВ

```python
# core/ai_providers/__init__.py

from bot.config import settings
from core.ai_providers.glm import GLMProvider
from core.ai_providers.gemini import GeminiProvider
from core.ai_providers.chain import VisionProviderChain, TextProviderChain, ChainConfig


def create_vision_chain() -> VisionProviderChain:
    """
    Создаёт chain Vision провайдеров.
    
    Порядок: GLM-4V → Gemini Flash
    """
    providers = []
    
    # Primary: GLM-4V
    if settings.glm_api_key:
        providers.append(GLMProvider(settings.glm_api_key))
    
    # Fallback: Gemini
    if settings.gemini_api_key:
        providers.append(GeminiProvider(settings.gemini_api_key))
    
    if not providers:
        raise ValueError("Не настроен ни один Vision провайдер!")
    
    return VisionProviderChain(providers, ChainConfig(max_retries=2))


def create_text_chain() -> TextProviderChain:
    """
    Создаёт chain Text провайдеров.
    
    Порядок: GLM-4 → Gemini Flash
    """
    providers = []
    
    # Primary: GLM-4
    if settings.glm_api_key:
        providers.append(GLMProvider(settings.glm_api_key))
    
    # Fallback: Gemini
    if settings.gemini_api_key:
        providers.append(GeminiProvider(settings.gemini_api_key))
    
    if not providers:
        raise ValueError("Не настроен ни один Text провайдер!")
    
    return TextProviderChain(providers, ChainConfig(max_retries=2))
```

---

## 🧪 ТЕСТИРОВАНИЕ ПРОВАЙДЕРОВ

```python
# tests/test_ai_providers.py

import pytest
from unittest.mock import AsyncMock, patch

from core.ai_providers.base import ProviderResponse
from core.ai_providers.glm import GLMProvider
from core.ai_providers.gemini import GeminiProvider
from core.ai_providers.chain import VisionProviderChain


@pytest.fixture
def mock_glm():
    """Мок GLM провайдера."""
    provider = AsyncMock(spec=GLMProvider)
    provider.name = "glm"
    return provider


@pytest.fixture
def mock_gemini():
    """Мок Gemini провайдера."""
    provider = AsyncMock(spec=GeminiProvider)
    provider.name = "gemini"
    return provider


@pytest.mark.asyncio
async def test_vision_chain_first_provider_success(mock_glm, mock_gemini):
    """Тест: первый провайдер успешен."""
    mock_glm.analyze_multiple_images.return_value = ProviderResponse(
        success=True,
        content="Описание товара",
        provider_name="glm"
    )
    
    chain = VisionProviderChain([mock_glm, mock_gemini])
    result = await chain.analyze_image(b"fake_image")
    
    assert result.success
    assert result.provider_name == "glm"
    mock_gemini.analyze_multiple_images.assert_not_called()


@pytest.mark.asyncio
async def test_vision_chain_fallback_on_failure(mock_glm, mock_gemini):
    """Тест: fallback на второй провайдер при ошибке первого."""
    mock_glm.analyze_multiple_images.return_value = ProviderResponse(
        success=False,
        content="",
        provider_name="glm",
        error_message="API Error"
    )
    mock_gemini.analyze_multiple_images.return_value = ProviderResponse(
        success=True,
        content="Описание от Gemini",
        provider_name="gemini"
    )
    
    chain = VisionProviderChain([mock_glm, mock_gemini])
    result = await chain.analyze_image(b"fake_image")
    
    assert result.success
    assert result.provider_name == "gemini"


@pytest.mark.asyncio
async def test_vision_chain_all_failed(mock_glm, mock_gemini):
    """Тест: все провайдеры недоступны."""
    mock_glm.analyze_multiple_images.return_value = ProviderResponse(
        success=False, content="", provider_name="glm", error_message="Error 1"
    )
    mock_gemini.analyze_multiple_images.return_value = ProviderResponse(
        success=False, content="", provider_name="gemini", error_message="Error 2"
    )
    
    chain = VisionProviderChain([mock_glm, mock_gemini])
    
    with pytest.raises(RuntimeError) as exc_info:
        await chain.analyze_image(b"fake_image")
    
    assert "Все Vision провайдеры недоступны" in str(exc_info.value)
```

---

## 📋 CHECKLIST ИНТЕГРАЦИИ

- [ ] Получить API ключ Z.AI: https://z.ai/manage-apikey/apikey-list
- [ ] Получить API ключ Gemini: https://aistudio.google.com/apikey
- [ ] Добавить ключи в `.env`
- [ ] Протестировать GLM Vision (анализ фото)
- [ ] Протестировать GLM Text (генерация)
- [ ] Протестировать Gemini как fallback
- [ ] Убедиться что chain работает при отключении GLM

---

*Документация AI провайдеров v1.0*
