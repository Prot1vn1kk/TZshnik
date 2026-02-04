"""
Кастомные исключения проекта "ТЗшник v2.0".

Иерархия исключений позволяет обрабатывать ошибки на разных уровнях:
- TZGeneratorError - базовое исключение для всех ошибок генератора
  - AIProviderError - ошибки AI провайдеров
    - VisionAnalysisError - ошибки анализа изображений
    - TextGenerationError - ошибки генерации текста
  - ValidationError - ошибки валидации ТЗ
  - InsufficientBalanceError - недостаточно кредитов
  - PaymentError - ошибки платежей
  - DatabaseError - ошибки базы данных
"""


class TZGeneratorError(Exception):
    """
    Базовое исключение генератора ТЗ.
    
    Все кастомные исключения проекта наследуются от этого класса.
    Позволяет ловить все ошибки генератора одним except блоком.
    """
    pass


class AIProviderError(TZGeneratorError):
    """
    Ошибка AI провайдера.
    
    Возникает при проблемах с API провайдеров (GLM, Gemini).
    Включает таймауты, HTTP ошибки, невалидные ответы.
    """
    pass


class VisionAnalysisError(AIProviderError):
    """
    Ошибка анализа изображения.
    
    Возникает когда Vision AI не может проанализировать фото:
    - Изображение повреждено или нечитаемо
    - API вернул ошибку
    - Таймаут при анализе
    """
    pass


class TextGenerationError(AIProviderError):
    """
    Ошибка генерации текста.
    
    Возникает когда AI не может сгенерировать ТЗ:
    - API вернул пустой ответ
    - Превышен лимит токенов
    - Таймаут при генерации
    """
    pass


class GenerationError(TZGeneratorError):
    """
    Общая ошибка генерации ТЗ.
    
    Возникает при любых проблемах в процессе генерации:
    - Ошибка анализа фото
    - Ошибка генерации текста
    - Ошибка валидации
    """
    pass


class ValidationError(TZGeneratorError):
    """
    ТЗ не прошло валидацию.
    
    Возникает когда сгенерированное ТЗ не соответствует требованиям:
    - Отсутствуют обязательные секции
    - Слишком короткое содержание
    - Некорректный формат
    """
    
    def __init__(self, message: str, missing_sections: list[str] | None = None):
        """
        Инициализация исключения валидации.
        
        Args:
            message: Текст ошибки
            missing_sections: Список отсутствующих секций ТЗ
        """
        super().__init__(message)
        self.missing_sections = missing_sections or []


class InsufficientBalanceError(TZGeneratorError):
    """
    Недостаточно кредитов на балансе.
    
    Возникает когда пользователь пытается сгенерировать ТЗ,
    но у него закончились кредиты.
    """
    
    def __init__(self, message: str = "Недостаточно кредитов", balance: int = 0):
        """
        Инициализация исключения баланса.
        
        Args:
            message: Текст ошибки
            balance: Текущий баланс пользователя
        """
        super().__init__(message)
        self.balance = balance


class PaymentError(TZGeneratorError):
    """
    Ошибка платежа.
    
    Возникает при проблемах с оплатой через YooKassa:
    - Отклонённый платёж
    - Таймаут платежа
    - Ошибка провайдера платежей
    """
    pass


class DatabaseError(TZGeneratorError):
    """
    Ошибка базы данных.
    
    Возникает при проблемах с SQLite:
    - Ошибка подключения
    - Ошибка запроса
    - Нарушение целостности данных
    """
    pass


class ConfigurationError(TZGeneratorError):
    """
    Ошибка конфигурации.
    
    Возникает при отсутствии или неверных настройках:
    - Отсутствует API ключ
    - Неверный формат токена
    - Невалидные настройки
    """
    pass


class RateLimitError(AIProviderError):
    """
    Превышен лимит запросов к API.
    
    Возникает когда AI провайдер возвращает ошибку rate limit.
    Требует ожидания перед повторным запросом.
    """
    
    def __init__(self, message: str = "Превышен лимит запросов", retry_after: int | None = None):
        """
        Инициализация исключения rate limit.
        
        Args:
            message: Текст ошибки
            retry_after: Время ожидания в секундах
        """
        super().__init__(message)
        self.retry_after = retry_after
