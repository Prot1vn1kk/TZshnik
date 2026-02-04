"""
Цепочки провайдеров с автоматическим fallback.

Реализует паттерн Chain of Responsibility для AI провайдеров.
При ошибке одного провайдера автоматически переключается на следующий.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import structlog

from core.ai_providers.base import (
    BaseTextProvider,
    BaseVisionProvider,
    ProviderResponse,
    ProviderStatus,
)

# Логгер
logger = structlog.get_logger()


@dataclass
class ChainConfig:
    """
    Конфигурация цепочки провайдеров.
    
    Attributes:
        max_retries: Максимальное количество попыток на провайдер
        retry_delay: Задержка между попытками (секунды)
        fail_fast: Не пробовать следующий провайдер при критической ошибке
    """
    max_retries: int = 1
    retry_delay: float = 0.5
    fail_fast: bool = False


class VisionProviderChain:
    """
    Цепочка Vision провайдеров с автоматическим fallback.
    
    Пробует провайдеров по очереди пока один не вернёт успешный результат.
    
    Example:
        chain = VisionProviderChain([glm_provider, gemini_provider])
        response = await chain.analyze_image(image_bytes, prompt)
    """
    
    def __init__(
        self,
        providers: List[BaseVisionProvider],
        config: Optional[ChainConfig] = None,
    ):
        """
        Инициализация цепочки Vision провайдеров.
        
        Args:
            providers: Список провайдеров в порядке приоритета
            config: Конфигурация цепочки
        """
        self.providers = providers
        self.config = config or ChainConfig()
        
        logger.info(
            "vision_chain_initialized",
            providers=[p.name for p in providers],
        )
    
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None,
    ) -> ProviderResponse:
        """
        Анализ одного изображения с fallback.
        
        Args:
            image_bytes: Байты изображения
            prompt: Промпт для анализа
            
        Returns:
            ProviderResponse от первого успешного провайдера
            
        Raises:
            RuntimeError: Если все провайдеры вернули ошибку
        """
        return await self.analyze_multiple_images([image_bytes], prompt)
    
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None,
    ) -> ProviderResponse:
        """
        Анализ нескольких изображений с fallback.
        
        Args:
            images: Список байтов изображений
            prompt: Общий промпт для анализа
            
        Returns:
            ProviderResponse от первого успешного провайдера
            
        Raises:
            RuntimeError: Если все провайдеры вернули ошибку
        """
        errors: List[str] = []
        
        for provider in self.providers:
            for attempt in range(self.config.max_retries):
                logger.debug(
                    "vision_chain_trying_provider",
                    provider=provider.name,
                    attempt=attempt + 1,
                    images_count=len(images),
                )
                
                response = await provider.analyze_multiple_images(images, prompt)
                
                if response.success:
                    logger.info(
                        "vision_chain_success",
                        provider=provider.name,
                        attempt=attempt + 1,
                    )
                    return response
                
                # Запоминаем ошибку
                error_msg = f"{provider.name}: {response.error_message}"
                errors.append(error_msg)
                
                logger.warning(
                    "vision_chain_provider_failed",
                    provider=provider.name,
                    attempt=attempt + 1,
                    error=response.error_message,
                )
                
                # Ждём перед повторной попыткой
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
        
        # Все провайдеры упали
        all_errors = "; ".join(errors)
        logger.error(
            "vision_chain_all_failed",
            errors=errors,
        )
        
        raise RuntimeError(f"Все Vision провайдеры недоступны: {all_errors}")
    
    async def health_check_all(self) -> Dict[str, ProviderStatus]:
        """
        Проверка доступности всех провайдеров.
        
        Returns:
            Словарь {имя_провайдера: статус}
        """
        results = {}
        
        for provider in self.providers:
            status = await provider.health_check()
            results[provider.name] = status
            
            logger.debug(
                "vision_provider_health_check",
                provider=provider.name,
                status=status.value,
            )
        
        return results


class TextProviderChain:
    """
    Цепочка Text провайдеров с автоматическим fallback.
    
    Пробует провайдеров по очереди пока один не вернёт успешный результат.
    
    Example:
        chain = TextProviderChain([glm_provider, gemini_provider])
        response = await chain.generate(prompt, system_prompt)
    """
    
    def __init__(
        self,
        providers: List[BaseTextProvider],
        config: Optional[ChainConfig] = None,
    ):
        """
        Инициализация цепочки Text провайдеров.
        
        Args:
            providers: Список провайдеров в порядке приоритета
            config: Конфигурация цепочки
        """
        self.providers = providers
        self.config = config or ChainConfig()
        
        logger.info(
            "text_chain_initialized",
            providers=[p.name for p in providers],
        )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """
        Генерация текста с fallback.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт
            max_tokens: Максимум токенов
            temperature: Креативность
            
        Returns:
            ProviderResponse от первого успешного провайдера
            
        Raises:
            RuntimeError: Если все провайдеры вернули ошибку
        """
        errors: List[str] = []
        
        for provider in self.providers:
            for attempt in range(self.config.max_retries):
                logger.debug(
                    "text_chain_trying_provider",
                    provider=provider.name,
                    attempt=attempt + 1,
                )
                
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                if response.success:
                    logger.info(
                        "text_chain_success",
                        provider=provider.name,
                        attempt=attempt + 1,
                        result_length=len(response.content),
                    )
                    return response
                
                # Запоминаем ошибку
                error_msg = f"{provider.name}: {response.error_message}"
                errors.append(error_msg)
                
                logger.warning(
                    "text_chain_provider_failed",
                    provider=provider.name,
                    attempt=attempt + 1,
                    error=response.error_message,
                )
                
                # Ждём перед повторной попыткой
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
        
        # Все провайдеры упали
        all_errors = "; ".join(errors)
        logger.error(
            "text_chain_all_failed",
            errors=errors,
        )
        
        raise RuntimeError(f"Все Text провайдеры недоступны: {all_errors}")
    
    async def health_check_all(self) -> Dict[str, ProviderStatus]:
        """
        Проверка доступности всех провайдеров.
        
        Returns:
            Словарь {имя_провайдера: статус}
        """
        results = {}
        
        for provider in self.providers:
            status = await provider.health_check()
            results[provider.name] = status
            
            logger.debug(
                "text_provider_health_check",
                provider=provider.name,
                status=status.value,
            )
        
        return results
