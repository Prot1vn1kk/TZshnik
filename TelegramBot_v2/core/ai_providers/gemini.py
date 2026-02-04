"""
Google Gemini провайдер (Fallback).

Используется как резервный провайдер когда GLM недоступен.
Поддерживает как Vision так и Text генерацию.

Использует httpx для прямых запросов к API.
"""

import asyncio
import base64
from typing import List, Optional

import httpx
import structlog

from core.ai_providers.base import (
    BaseTextProvider,
    BaseVisionProvider,
    ProviderResponse,
    ProviderStatus,
)

# Логгер
logger = structlog.get_logger()


class GeminiProvider(BaseVisionProvider, BaseTextProvider):
    """
    Провайдер Google Gemini (Fallback).
    
    Использует Gemini 1.5 Flash для Vision и Text генерации.
    Бесплатный лимит: 60 RPM.
    
    Attributes:
        name: Имя провайдера для логирования
        model: Используемая модель Gemini
    
    Example:
        provider = GeminiProvider(api_key="your_key")
        response = await provider.analyze_image(image_bytes, "Опиши товар")
    """
    
    name = "gemini"
    
    # API endpoint и модели
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    
    # Модели (используем актуальные имена из API)
    MODEL = "gemini-2.5-flash"
    MODEL_PRO = "gemini-2.5-pro"  # Более качественная, но медленнее
    
    def __init__(
        self,
        api_key: str,
        use_pro_model: bool = False,
        timeout: float = 90.0,
    ):
        """
        Инициализация провайдера Gemini.
        
        Args:
            api_key: API ключ Google AI Studio
            use_pro_model: Использовать Pro модель (качественнее, но медленнее)
            timeout: Таймаут запроса в секундах
        """
        self.api_key = api_key
        self.timeout = timeout
        self.model = self.MODEL_PRO if use_pro_model else self.MODEL
        
        logger.debug(
            "gemini_provider_initialized",
            model=self.model,
            timeout=timeout,
        )
    
    def _get_endpoint(self) -> str:
        """
        Получить URL endpoint для запроса.
        
        Returns:
            Полный URL для API запроса
        """
        return f"{self.BASE_URL}/{self.model}:generateContent?key={self.api_key}"
    
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None,
    ) -> ProviderResponse:
        """
        Анализ одного изображения.
        
        Args:
            image_bytes: Байты изображения (JPEG/PNG)
            prompt: Промпт для анализа
            
        Returns:
            ProviderResponse с описанием изображения
        """
        return await self.analyze_multiple_images([image_bytes], prompt)
    
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None,
    ) -> ProviderResponse:
        """
        Анализ нескольких изображений.
        
        Args:
            images: Список байтов изображений
            prompt: Общий промпт для анализа
            
        Returns:
            ProviderResponse с объединённым описанием
        """
        if not prompt:
            prompt = "Опиши подробно что изображено на фото."
        
        # Формируем parts для запроса
        parts = []
        
        # Добавляем изображения
        for img_bytes in images[:5]:  # Ограничение 5 фото
            base64_image = base64.b64encode(img_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64_image,
                }
            })
        
        # Добавляем текстовый промпт
        parts.append({"text": prompt})
        
        # Формируем тело запроса
        request_body = {
            "contents": [
                {
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2000,
            },
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._get_endpoint(),
                    json=request_body,
                )
                response.raise_for_status()
                data = response.json()
            
            # Извлекаем текст из ответа
            result_text = self._extract_text(data)
            
            if not result_text:
                return ProviderResponse(
                    success=False,
                    content="",
                    provider_name=self.name,
                    error_message="Пустой ответ от Gemini",
                )
            
            logger.info(
                "gemini_vision_success",
                model=self.model,
                images_count=len(images),
                result_length=len(result_text),
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                metadata={"model": self.model},
            )
            
        except httpx.TimeoutException:
            error_msg = f"Таймаут запроса ({self.timeout}s)"
            logger.error("gemini_vision_timeout", timeout=self.timeout)
            
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg,
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP ошибка: {e.response.status_code}"
            
            # Пробуем получить детали ошибки
            try:
                error_data = e.response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                pass
            
            logger.error(
                "gemini_vision_http_error",
                status_code=e.response.status_code,
                error=error_msg,
            )
            
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg,
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("gemini_vision_error", error=error_msg)
            
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg,
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """
        Генерация текста.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (роль AI)
            max_tokens: Максимум токенов в ответе
            temperature: Креативность (0.0-1.0)
            
        Returns:
            ProviderResponse с сгенерированным текстом
        """
        # Формируем тело запроса
        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        
        # Добавляем системный промпт если есть
        if system_prompt:
            request_body["systemInstruction"] = {
                "parts": [
                    {"text": system_prompt}
                ]
            }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._get_endpoint(),
                    json=request_body,
                )
                response.raise_for_status()
                data = response.json()
            
            # Извлекаем текст из ответа
            result_text = self._extract_text(data)
            
            if not result_text:
                return ProviderResponse(
                    success=False,
                    content="",
                    provider_name=self.name,
                    error_message="Пустой ответ от Gemini",
                )
            
            logger.info(
                "gemini_text_success",
                model=self.model,
                result_length=len(result_text),
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                metadata={"model": self.model},
            )
            
        except httpx.TimeoutException:
            error_msg = f"Таймаут запроса ({self.timeout}s)"
            logger.error("gemini_text_timeout", timeout=self.timeout)
            
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg,
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP ошибка: {e.response.status_code}"
            
            try:
                error_data = e.response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except Exception:
                pass
            
            logger.error(
                "gemini_text_http_error",
                status_code=e.response.status_code,
                error=error_msg,
            )
            
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg,
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("gemini_text_error", error=error_msg)
            
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg,
            )
    
    def _extract_text(self, response_data: dict) -> str:
        """
        Извлекает текст из ответа Gemini API.
        
        Args:
            response_data: JSON ответ от API
            
        Returns:
            Извлечённый текст или пустая строка
        """
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                return ""
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                return ""
            
            # Собираем текст из всех частей
            texts = []
            for part in parts:
                if "text" in part:
                    texts.append(part["text"])
            
            return "\n".join(texts)
            
        except Exception as e:
            logger.warning("gemini_extract_text_error", error=str(e))
            return ""
    
    async def health_check(self) -> ProviderStatus:
        """
        Проверка доступности провайдера Gemini.
        
        Returns:
            ProviderStatus с текущим состоянием
        """
        try:
            response = await self.generate(
                prompt="Say 'OK'",
                max_tokens=10,
                temperature=0.0,
            )
            
            if response.success:
                return ProviderStatus.AVAILABLE
            
            error_lower = (response.error_message or "").lower()
            if "rate" in error_lower or "quota" in error_lower:
                return ProviderStatus.RATE_LIMITED
            
            return ProviderStatus.ERROR
            
        except Exception:
            return ProviderStatus.ERROR
