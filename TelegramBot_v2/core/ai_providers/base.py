"""
Базовые классы для AI провайдеров.

Определяет абстрактные интерфейсы для Vision и Text провайдеров,
а также общие структуры данных для ответов.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


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
    
    Унифицированный формат ответа для всех провайдеров.
    
    Attributes:
        success: Успешен ли запрос
        content: Сгенерированный контент (пустой при ошибке)
        provider_name: Имя провайдера который обработал запрос
        tokens_used: Количество использованных токенов (если доступно)
        error_message: Сообщение об ошибке (если success=False)
        metadata: Дополнительные данные (модель, время и т.д.)
    """
    success: bool
    content: str
    provider_name: str
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseVisionProvider(ABC):
    """
    Абстрактный класс для Vision AI провайдеров.
    
    Определяет интерфейс для анализа изображений.
    Все Vision провайдеры должны наследовать этот класс.
    """
    
    name: str = "base_vision"
    
    @abstractmethod
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None,
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
        prompt: Optional[str] = None,
    ) -> ProviderResponse:
        """
        Анализирует несколько изображений вместе.
        
        Args:
            images: Список байтов изображений (до 5 штук)
            prompt: Общий промпт для анализа
            
        Returns:
            ProviderResponse с объединённым результатом
        """
        pass
    
    async def health_check(self) -> ProviderStatus:
        """
        Проверка доступности провайдера.
        
        Выполняет минимальный тестовый запрос для проверки работоспособности.
        
        Returns:
            ProviderStatus указывающий состояние провайдера
        """
        try:
            test_image = self._create_test_image()
            response = await self.analyze_image(test_image, "Describe this image briefly.")
            
            if response.success:
                return ProviderStatus.AVAILABLE
            elif "rate" in response.error_message.lower() if response.error_message else False:
                return ProviderStatus.RATE_LIMITED
            else:
                return ProviderStatus.ERROR
                
        except Exception:
            return ProviderStatus.ERROR
    
    def _create_test_image(self) -> bytes:
        """
        Создаёт минимальное тестовое изображение (1x1 белый PNG).
        
        Returns:
            Байты PNG изображения
        """
        # Минимальный валидный PNG (1x1 белый пиксель)
        return bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82,
        ])


class BaseTextProvider(ABC):
    """
    Абстрактный класс для Text AI провайдеров.
    
    Определяет интерфейс для генерации текста.
    Все Text провайдеры должны наследовать этот класс.
    """
    
    name: str = "base_text"
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """
        Генерирует текст по промпту.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (роль/контекст AI)
            max_tokens: Максимальное количество токенов в ответе
            temperature: Креативность (0.0 - детерминированный, 1.0 - креативный)
            
        Returns:
            ProviderResponse с сгенерированным текстом
        """
        pass
    
    async def health_check(self) -> ProviderStatus:
        """
        Проверка доступности провайдера.
        
        Returns:
            ProviderStatus указывающий состояние провайдера
        """
        try:
            response = await self.generate(
                prompt="Say 'OK' and nothing else.",
                max_tokens=10,
                temperature=0.0,
            )
            
            if response.success:
                return ProviderStatus.AVAILABLE
            elif "rate" in response.error_message.lower() if response.error_message else False:
                return ProviderStatus.RATE_LIMITED
            else:
                return ProviderStatus.ERROR
                
        except Exception:
            return ProviderStatus.ERROR
