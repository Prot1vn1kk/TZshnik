"""
Модуль AI провайдеров.

Содержит:
- base.py - абстрактные базовые классы
- gemini.py - Google Gemini провайдер
- chain.py - цепочки провайдеров с fallback

Фабричные функции:
- create_vision_chain() - создаёт цепочку Vision провайдеров
- create_text_chain() - создаёт цепочку Text провайдеров
"""

from typing import Optional

from core.ai_providers.base import (
    BaseTextProvider,
    BaseVisionProvider,
    ProviderResponse,
    ProviderStatus,
)
from core.ai_providers.chain import (
    ChainConfig,
    TextProviderChain,
    VisionProviderChain,
)


def create_vision_chain(
    gemini_api_key: Optional[str] = None,
    use_fast_models: bool = True,
    config: Optional[ChainConfig] = None,
) -> VisionProviderChain:
    """
    Создаёт цепочку Vision провайдеров.
    
    Args:
        gemini_api_key: API ключ Google Gemini
        use_fast_models: Использовать быстрые модели
        config: Конфигурация цепочки
        
    Returns:
        VisionProviderChain с настроенными провайдерами
    """
    from bot.config import settings
    
    # Используем ключ из settings если не передан
    gemini_key = gemini_api_key or settings.gemini_api_key
    
    providers = []
    
    # Добавляем Gemini если есть валидный ключ
    if gemini_key and not gemini_key.startswith('your_'):
        from core.ai_providers.gemini import GeminiProvider
        providers.append(GeminiProvider(api_key=gemini_key))
    
    if not providers:
        raise ValueError("Не указан API ключ для AI провайдера")
    
    return VisionProviderChain(providers=providers, config=config)


def create_text_chain(
    gemini_api_key: Optional[str] = None,
    use_fast_models: bool = True,
    config: Optional[ChainConfig] = None,
) -> TextProviderChain:
    """
    Создаёт цепочку Text провайдеров.
    
    Args:
        gemini_api_key: API ключ Google Gemini
        use_fast_models: Использовать быстрые модели
        config: Конфигурация цепочки
        
    Returns:
        TextProviderChain с настроенными провайдерами
    """
    from bot.config import settings
    
    # Используем ключ из settings если не передан
    gemini_key = gemini_api_key or settings.gemini_api_key
    
    providers = []
    
    # Добавляем Gemini если есть валидный ключ
    if gemini_key and not gemini_key.startswith('your_'):
        from core.ai_providers.gemini import GeminiProvider
        providers.append(GeminiProvider(api_key=gemini_key))
    
    if not providers:
        raise ValueError("Не указан API ключ для AI провайдера")
    
    return TextProviderChain(providers=providers, config=config)


__all__ = [
    # Base classes
    "BaseVisionProvider",
    "BaseTextProvider",
    "ProviderResponse",
    "ProviderStatus",
    # Chains
    "VisionProviderChain",
    "TextProviderChain",
    "ChainConfig",
    # Factory functions
    "create_vision_chain",
    "create_text_chain",
]

