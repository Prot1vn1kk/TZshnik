"""
Валидация входных данных.

Содержит функции для валидации и санитизации пользовательского ввода,
обеспечивая безопасность и целостность данных.
"""

import re
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

from config.constants import (
    MAX_USERNAME_DISPLAY_LENGTH,
    MIN_CREDIT_OPERATION_AMOUNT,
    MAX_CREDIT_OPERATION_AMOUNT,
    MIN_TZ_TEXT_LENGTH,
)


# ============================================================
# ОШИБКИ ВАЛИДАЦИИ
# ============================================================

class ValidationError(Exception):
    """Базовый класс ошибок валидации."""

    def __init__(self, message: str, field: str = ""):
        self.message = message
        self.field = field
        super().__init__(self.message)


class InvalidCreditAmountError(ValidationError):
    """Ошибка валидации суммы кредитов."""

    pass


class InvalidUsernameError(ValidationError):
    """Ошибка валидации username."""

    pass


class InvalidSearchQueryError(ValidationError):
    """Ошибка валидации поискового запроса."""

    pass


class InvalidTelegramIDError(ValidationError):
    """Ошибка валидации Telegram ID."""

    pass


# ============================================================
# ВАЛИДАТОРЫ
# ============================================================

def validate_credit_amount(amount: int) -> Tuple[bool, Optional[str]]:
    """
    Валидирует сумму кредитов.

    Args:
        amount: Сумма кредитов

    Returns:
        Tuple[is_valid, error_message]
    """
    if not isinstance(amount, (int, float)):
        return False, "Сумма должна быть числом"

    if amount <= 0:
        return False, "Сумма должна быть положительной"

    if amount < MIN_CREDIT_OPERATION_AMOUNT:
        return False, f"Минимальная сумма: {MIN_CREDIT_OPERATION_AMOUNT}"

    if amount > MAX_CREDIT_OPERATION_AMOUNT:
        return False, f"Максимальная сумма: {MAX_CREDIT_OPERATION_AMOUNT}"

    return True, None


def validate_username(username: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Валидирует username Telegram.

    Args:
        username: Username (с @ или без)

    Returns:
        Tuple[is_valid, error_message]
    """
    if not username:
        return True, None  # Username опционален

    # Удаляем @ если есть
    clean_username = username.lstrip("@")

    # Проверяем длину
    if len(clean_username) > MAX_USERNAME_DISPLAY_LENGTH:
        return False, f"Username слишком длинный (максимум {MAX_USERNAME_DISPLAY_LENGTH})"

    # Проверяем формат (только буквы, цифры, подчеркивания)
    if not re.match(r'^[a-zA-Z0-9_]+$', clean_username):
        return False, "Username может содержать только буквы, цифры и подчеркивания"

    # Проверяем, что не начинается с цифры
    if clean_username[0].isdigit():
        return False, "Username не может начинаться с цифры"

    return True, None


def validate_telegram_id(telegram_id: Any) -> Tuple[bool, Optional[str]]:
    """
    Валидирует Telegram ID.

    Args:
        telegram_id: Telegram ID

    Returns:
        Tuple[is_valid, error_message]
    """
    # Пытаемся преобразовать в int
    try:
        tid = int(telegram_id)
    except (ValueError, TypeError):
        return False, "Telegram ID должен быть числом"

    # Проверяем диапазон (Telegram ID обычно от 1 до 2^31)
    if tid < 1:
        return False, "Telegram ID должен быть положительным"

    if tid > 2_147_483_647:  # 2^31 - 1
        return False, "Некорректный Telegram ID"

    return True, None


def validate_search_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует поисковый запрос.

    Args:
        query: Поисковая строка

    Returns:
        Tuple[is_valid, error_message]
    """
    if not query or not query.strip():
        return False, "Поисковый запрос не может быть пустым"

    clean_query = query.strip()

    # Проверяем длину
    if len(clean_query) < 2:
        return False, "Запрос слишком короткий"

    if len(clean_query) > 100:
        return False, "Запрос слишком длинный"

    # Проверяем на потенциально опасные символы
    # Разрешаем: буквы, цифры, @, _, -, пробелы
    if not re.match(r'^[a-zA-Z0-9@_\-\s\.]+$', clean_query):
        return False, "Запрос содержит недопустимые символы"

    return True, None


def validate_category(category: str, allowed_categories: Optional[set] = None) -> Tuple[bool, Optional[str]]:
    """
    Валидирует категорию товара.

    Args:
        category: Категория
        allowed_categories: Разрешённые категории

    Returns:
        Tuple[is_valid, error_message]
    """
    if not category:
        return False, "Категория не указана"

    if allowed_categories and category not in allowed_categories:
        return False, f"Категория '{category}' не разрешена"

    # Проверяем формат (только буквы, цифры, подчеркивания, дефисы)
    if not re.match(r'^[a-z0-9_\-]+$', category):
        return False, "Категория может содержать только строчные буквы, цифры, _ и -"

    return True, None


def validate_tz_text(text: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует текст технического задания.

    Args:
        text: Текст ТЗ

    Returns:
        Tuple[is_valid, error_message]
    """
    if not text or not text.strip():
        return False, "Текст не может быть пустым"

    clean_text = text.strip()

    if len(clean_text) < MIN_TZ_TEXT_LENGTH:
        return False, f"Текст слишком короткий (минимум {MIN_TZ_TEXT_LENGTH} символов)"

    # Проверяем на наличие вредоносного контента (базовая проверка)
    suspicious_patterns = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',  # JavaScript URLs
        r'onerror=',  # Обработчики ошибок
        r'onload=',  # Обработчики загрузки
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return False, "Текст содержит недопустимое содержимое"

    return True, None


def validate_package_id(package_id: str, available_packages: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Валидирует ID пакета кредитов.

    Args:
        package_id: ID пакета
        available_packages: Доступные пакеты

    Returns:
        Tuple[is_valid, error_message]
    """
    if not package_id:
        return False, "ID пакета не указан"

    if package_id not in available_packages:
        available = ', '.join(available_packages.keys())
        return False, f"Неизвестный пакет. Доступно: {available}"

    return True, None


def validate_sort_field(field: str, allowed_fields: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Валидирует поле сортировки.

    Args:
        field: Поле сортировки
        allowed_fields: Разрешённые поля

    Returns:
        Tuple[is_valid, error_message]
    """
    if not field:
        return True, None  # Поле опционально

    if field not in allowed_fields:
        return False, f"Некорректное поле сортировки. Разрешено: {', '.join(allowed_fields)}"

    return True, None


def validate_page_number(page: int, max_pages: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Валидирует номер страницы.

    Args:
        page: Номер страницы
        max_pages: Максимальный номер страницы

    Returns:
        Tuple[is_valid, error_message]
    """
    try:
        page_num = int(page)
    except (ValueError, TypeError):
        return False, "Номер страницы должен быть числом"

    if page_num < 1:
        return False, "Номер страницы должен быть положительным"

    if max_pages and page_num > max_pages:
        return False, f"Страница не существует (максимум: {max_pages})"

    return True, None


def sanitize_string(text: str, max_length: Optional[int] = None, remove_html: bool = True) -> str:
    """
    Санитизирует строку пользовательского ввода.

    Args:
        text: Исходный текст
        max_length: Максимальная длина
        remove_html: Удалять ли HTML теги

    Returns:
        Санитизированная строка
    """
    if not text:
        return ""

    # Удаляем лишние пробелы
    clean = text.strip()

    # Удаляем HTML если нужно
    if remove_html:
        clean = re.sub(r'<[^>]+>', '', clean)

    # Удаляем спецсимволы
    clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean)

    # Обрезаем если слишком длинно
    if max_length and len(clean) > max_length:
        clean = clean[:max_length]

    return clean


# ============================================================
# КОМПОЗИТНЫЕ ВАЛИДАТОРЫ
# ============================================================

def validate_admin_credit_operation(
    telegram_id: Any,
    amount: Any,
) -> Tuple[bool, List[str]]:
    """
    Валидирует операцию с кредитами в админ-панели.

    Args:
        telegram_id: Telegram ID пользователя
        amount: Сумма кредитов

    Returns:
        Tuple[is_valid, list_of_errors]
    """
    errors = []

    # Валидируем Telegram ID
    valid, error = validate_telegram_id(telegram_id)
    if not valid:
        errors.append(error)

    # Валидируем сумму
    try:
        amount_int = int(amount)
    except (ValueError, TypeError):
        errors.append("Сумма должна быть числом")
    else:
        valid, error = validate_credit_amount(amount_int)
        if not valid:
            errors.append(error)

    return len(errors) == 0, errors


def validate_user_search(query: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Валидирует поисковый запрос пользователя.

    Args:
        query: Поисковый запрос (telegram_id или username)

    Returns:
        Tuple[is_valid, error_message, telegram_id_if_found]
    """
    if not query:
        return False, "Запрос не может быть пустым", None

    clean_query = query.strip()

    # Проверяем, это Telegram ID или username
    if clean_query.isdigit():
        # Это ID
        valid, error = validate_telegram_id(clean_query)
        if not valid:
            return False, error, None
        return True, None, int(clean_query)
    else:
        # Это username
        valid, error = validate_username(clean_query)
        if not valid:
            return False, error, None
        return True, None, None


# ============================================================
# УТИЛИТЫ
# ============================================================

def format_validation_errors(errors: List[str]) -> str:
    """
    Форматирует список ошибок валидации.

    Args:
        errors: Список ошибок

    Returns:
        Форматированная строка
    """
    if not errors:
        return "Нет ошибок"

    lines = ["❌ Ошибки валидации:"]
    for i, error in enumerate(errors, 1):
        lines.append(f"  {i}. {error}")

    return "\n".join(lines)
