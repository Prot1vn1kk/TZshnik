"""
Модуль бизнес-логики "ТЗшник v2.0".

Содержит:
- ai_providers/ - провайдеры AI (GLM, Gemini)
- generator.py - генерация ТЗ
- validator.py - валидация качества ТЗ
- prompts.py - промпты для AI
- pdf_export.py - экспорт в PDF
- exceptions.py - кастомные исключения
"""

from core.exceptions import (
    TZGeneratorError,
    AIProviderError,
    VisionAnalysisError,
    TextGenerationError,
    ValidationError,
    InsufficientBalanceError,
    PaymentError,
    DatabaseError,
    ConfigurationError,
    RateLimitError,
    GenerationError,
)
from core.validator import TZValidator, ValidationResult, validate_tz
from core.generator import TZGenerator, GenerationResult, create_generator


__all__ = [
    # Exceptions
    "TZGeneratorError",
    "AIProviderError",
    "VisionAnalysisError",
    "TextGenerationError",
    "ValidationError",
    "InsufficientBalanceError",
    "PaymentError",
    "DatabaseError",
    "ConfigurationError",
    "RateLimitError",
    "GenerationError",
    # Generator
    "TZGenerator",
    "GenerationResult",
    "create_generator",
    # Validator
    "TZValidator",
    "ValidationResult",
    "validate_tz",
]
