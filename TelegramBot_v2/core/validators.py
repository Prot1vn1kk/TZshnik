"""
Валидация и санитизация пользовательского ввода.

Модуль обеспечивает безопасность входных данных:
- Экранирование HTML/XSS
- Ограничение длины текста
- Фильтрация опасных символов
- Валидация специфичных форматов
"""

import html
import re
from typing import Optional, Tuple


# ============================================================
# КОНСТАНТЫ
# ============================================================

# Максимальные длины текста
MAX_MESSAGE_LENGTH = 4000       # Лимит Telegram
MAX_FEEDBACK_LENGTH = 1000      # Отзыв
MAX_TEXT_INPUT_LENGTH = 500     # Обычный ввод
MAX_CATEGORY_LENGTH = 50        # Категория
MAX_USERNAME_LENGTH = 255       # Username

# Паттерны для фильтрации
DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',   # XSS скрипты
    r'javascript:',                  # javascript: URL
    r'on\w+\s*=',                    # onload, onclick и т.д.
    r'data:text/html',               # data URI XSS
]

# Разрешённые символы для разных типов ввода
ALLOWED_USERNAME_CHARS = re.compile(r'^[a-zA-Z0-9_]+$')
ALLOWED_CATEGORY_CHARS = re.compile(r'^[a-zA-Zа-яА-ЯёЁ0-9_\-\s]+$')


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ САНИТИЗАЦИИ
# ============================================================

def sanitize_html(text: str) -> str:
    """
    Экранирование HTML символов для предотвращения XSS.
    
    Args:
        text: Исходный текст
        
    Returns:
        Текст с экранированными HTML символами
    """
    if not text:
        return ""
    return html.escape(text, quote=True)


def remove_dangerous_patterns(text: str) -> str:
    """
    Удаление потенциально опасных паттернов.
    
    Args:
        text: Исходный текст
        
    Returns:
        Очищенный текст
    """
    if not text:
        return ""
    
    result = text
    for pattern in DANGEROUS_PATTERNS:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE | re.DOTALL)
    
    return result


def truncate_text(text: str, max_length: int) -> str:
    """
    Обрезание текста до максимальной длины.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        
    Returns:
        Обрезанный текст
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def normalize_whitespace(text: str) -> str:
    """
    Нормализация пробелов и переносов строк.
    
    Args:
        text: Исходный текст
        
    Returns:
        Текст с нормализованными пробелами
    """
    if not text:
        return ""
    
    # Убираем множественные пробелы
    text = re.sub(r' +', ' ', text)
    
    # Убираем множественные переносы строк (более 2 подряд)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


# ============================================================
# КОМПЛЕКСНАЯ САНИТИЗАЦИЯ
# ============================================================

def sanitize_text_input(
    text: str,
    max_length: int = MAX_TEXT_INPUT_LENGTH,
    allow_html: bool = False,
    strip_newlines: bool = False,
) -> str:
    """
    Полная санитизация текстового ввода.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        allow_html: Разрешить HTML теги (по умолчанию False)
        strip_newlines: Удалить переносы строк
        
    Returns:
        Санитизированный текст
    """
    if not text:
        return ""
    
    result = text
    
    # Удаляем опасные паттерны
    result = remove_dangerous_patterns(result)
    
    # Экранируем HTML если нужно
    if not allow_html:
        result = sanitize_html(result)
    
    # Удаляем переносы если нужно
    if strip_newlines:
        result = result.replace('\n', ' ').replace('\r', '')
    
    # Нормализуем пробелы
    result = normalize_whitespace(result)
    
    # Обрезаем до максимальной длины
    result = truncate_text(result, max_length)
    
    return result


def sanitize_feedback(text: str) -> Tuple[str, bool]:
    """
    Санитизация текста отзыва.
    
    Args:
        text: Текст отзыва
        
    Returns:
        Tuple[очищенный_текст, is_valid]
    """
    if not text or not text.strip():
        return "", False
    
    sanitized = sanitize_text_input(text, max_length=MAX_FEEDBACK_LENGTH)
    
    # Проверяем минимальную длину
    if len(sanitized) < 3:
        return "", False
    
    return sanitized, True


def sanitize_category(category: str) -> Tuple[str, bool]:
    """
    Санитизация названия категории.
    
    Args:
        category: Название категории
        
    Returns:
        Tuple[очищенная_категория, is_valid]
    """
    if not category or not category.strip():
        return "", False
    
    category = category.strip()[:MAX_CATEGORY_LENGTH]
    
    # Проверяем допустимые символы
    if not ALLOWED_CATEGORY_CHARS.match(category):
        # Удаляем недопустимые символы
        category = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9_\-\s]', '', category)
    
    if len(category) < 2:
        return "", False
    
    return category, True


def sanitize_username(username: Optional[str]) -> Optional[str]:
    """
    Санитизация Telegram username.
    
    Args:
        username: Username пользователя
        
    Returns:
        Очищенный username или None
    """
    if not username:
        return None
    
    # Убираем @ в начале
    username = username.lstrip('@')
    
    # Обрезаем до максимума
    username = username[:MAX_USERNAME_LENGTH]
    
    # Проверяем формат
    if not ALLOWED_USERNAME_CHARS.match(username):
        return None
    
    return username


# ============================================================
# ВАЛИДАЦИЯ СПЕЦИФИЧНЫХ ФОРМАТОВ
# ============================================================

def validate_telegram_id(telegram_id: int) -> bool:
    """
    Проверка валидности Telegram ID.
    
    Args:
        telegram_id: ID пользователя
        
    Returns:
        True если ID валидный
    """
    # Telegram ID - положительное число
    return isinstance(telegram_id, int) and telegram_id > 0


def validate_amount(amount: int, min_val: int = 1, max_val: int = 1000000) -> bool:
    """
    Проверка валидности числового значения (суммы, количества).
    
    Args:
        amount: Значение для проверки
        min_val: Минимальное значение
        max_val: Максимальное значение
        
    Returns:
        True если значение валидно
    """
    return isinstance(amount, int) and min_val <= amount <= max_val


def validate_photo_count(count: int, max_photos: int = 5) -> bool:
    """
    Проверка количества фотографий.
    
    Args:
        count: Количество фото
        max_photos: Максимум фото
        
    Returns:
        True если количество валидно
    """
    return isinstance(count, int) and 1 <= count <= max_photos


def is_safe_file_path(path: str) -> bool:
    """
    Проверка безопасности пути к файлу (защита от path traversal).
    
    Args:
        path: Путь к файлу
        
    Returns:
        True если путь безопасен
    """
    if not path:
        return False
    
    # Проверяем на path traversal
    dangerous = [
        '..',
        '~',
        '/etc/',
        '/root/',
        'C:\\Windows',
        'C:\\System32',
    ]
    
    for d in dangerous:
        if d in path:
            return False
    
    return True


# ============================================================
# УТИЛИТЫ ДЛЯ ОБРАБОТЧИКОВ
# ============================================================

def get_safe_display_name(
    first_name: Optional[str],
    username: Optional[str],
    telegram_id: int,
) -> str:
    """
    Получить безопасное отображаемое имя пользователя.
    
    Args:
        first_name: Имя пользователя
        username: Username
        telegram_id: Telegram ID
        
    Returns:
        Безопасное имя для отображения
    """
    if first_name:
        safe_name = sanitize_text_input(first_name, max_length=100, strip_newlines=True)
        if safe_name:
            return safe_name
    
    if username:
        safe_username = sanitize_username(username)
        if safe_username:
            return f"@{safe_username}"
    
    return f"User {telegram_id}"
