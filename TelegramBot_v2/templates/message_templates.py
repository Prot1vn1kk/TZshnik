"""
Шаблоны сообщений бота.

Содержит унифицированные функции для форматирования HTML-сообщений,
обеспечивая согласованный стиль и структуру во всех частях бота.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from config.constants import (
    MAX_MESSAGE_LENGTH,
    MAX_USERNAME_DISPLAY_LENGTH,
)


# ============================================================
# БАЗОВЫЕ ФУНКЦИИ ФОРМАТИРОВАНИЯ
# ============================================================

def escape_html(text: str) -> str:
    """
    Экранирует HTML-специальные символы.

    Args:
        text: Исходный текст

    Returns:
        Экранированный текст
    """
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def bold(text: str) -> str:
    """Оборачивает текст в тег <b>."""
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    """Оборачивает текст в тег <i>."""
    return f"<i>{text}</i>"


def code(text: str) -> str:
    """Оборачивает текст в тег <code>."""
    return f"<code>{escape_html(text)}</code>"


def underline(text: str) -> str:
    """Оборачивает текст в тег <u>."""
    return f"<u>{text}</u>"


def spoiler(text: str) -> str:
    """Оборачивает текст в тег <tg-spoiler>."""
    return f"<tg-spoiler>{text}</tg-spoiler>"


def link(text: str, url: str) -> str:
    """Создаёт ссылку."""
    return f'<a href="{url}">{escape_html(text)}</a>'


# ============================================================
# ШАБЛОНЫ СООБЩЕНИЙ
# ============================================================

def format_section_header(text: str, icon: str = "") -> str:
    """
    Форматирует заголовок секции.

    Args:
        text: Текст заголовка
        icon: Необязательный эмодзи

    Returns:
        Форматированный заголовок
    """
    if icon:
        return f"{icon} {bold(text)}"
    return bold(text)


def format_separator(length: int = 20) -> str:
    """Возвращает строку-разделитель."""
    return "━" * length


def format_list_item(item: str, index: Optional[int] = None, bullet: str = "•") -> str:
    """
    Форматирует элемент списка.

    Args:
        item: Текст элемента
        index: Необязательный номер
        bullet: Символ маркера

    Returns:
        Форматированный элемент
    """
    if index is not None:
        return f"{index}. {item}"
    return f"{bullet} {item}"


def format_key_value(key: str, value: Any, separator: str = ": ") -> str:
    """
    Форматирует пару ключ-значение.

    Args:
        key: Ключ
        value: Значение
        separator: Разделитель

    Returns:
        Форматированная пара
    """
    return f"{bold(key)}{separator}{value}"


# ============================================================
# ШАБЛОНЫ ПОЛЬЗОВАТЕЛЬСКИХ СООБЩЕНИЙ
# ============================================================

def welcome_message(username: Optional[str] = None) -> str:
    """
    Приветственное сообщение.

    Args:
        username: Имя пользователя

    Returns:
        Форматированное сообщение
    """
    greeting = "Добро пожаловать" if username else "Привет"
    name = username or "!"

    return (
        f"{greeting}{', ' if username else ''}{bold(name)}!\n\n"
        f"🤖 Я — {bold('ТЗшник')}, бот для создания технических заданий "
        f"для маркетплейсов (Wildberries, Ozon, Яндекс.Маркет).\n\n"
        f"Загрузите фото товара, и я составлю профессиональное ТЗ "
        f"с SEO-оптимизированным описанием, характеристиками и требованиями.\n\n"
        f"{format_section_header('Начало работы', '🚀')}\n"
        f"{format_list_item('Нажмите «Создать ТЗ»')}\n"
        f"{format_list_item('Загрузите 1-5 фото товара')}\n"
        f"{format_list_item('Выберите категорию')}\n"
        f"{format_list_item('Получите готовое ТЗ')}\n\n"
        f"Каждая генерация стоит 1 кредит. "
        f"Новые пользователи получают бесплатные кредиты!"
    )


def balance_message(
    credits: int,
    is_unlimited: bool = False,
    unlimited_until: Optional[datetime] = None,
) -> str:
    """
    Сообщение о балансе пользователя.

    Args:
        credits: Количество кредитов
        is_unlimited: Включен ли безлимит
        unlimited_until: Дата окончания безлимита

    Returns:
        Форматированное сообщение
    """
    lines: List[str] = [
        format_section_header("💰 Ваш баланс"),
        format_separator(20),
        "",
    ]

    if is_unlimited:
        if unlimited_until:
            date_str = unlimited_until.strftime("%d.%m.%Y %H:%M")
            lines.append(f"{bold('Статус:')} ♾️ Безлимит")
            lines.append(f"{bold('До:')} {date_str}")
        else:
            lines.append(f"{bold('Статус:')} ♾️ Безлимит (навсегда)")
    else:
        lines.append(f"{bold('Кредитов:')} {credits}")

    lines.extend([
        "",
        italic("Генерация одного ТЗ стоит 1 кредит."),
        "",
        "Используйте кнопки ниже для управления:",
    ])

    return "\n".join(lines)


def generation_success_message(
    generation_id: int,
    category: str,
    remaining_credits: int,
) -> str:
    """
    Сообщение об успешной генерации.

    Args:
        generation_id: ID генерации
        category: Категория товара
        remaining_credits: Оставшиеся кредиты

    Returns:
        Форматированное сообщение
    """
    return (
        f"✅ {bold('Техническое задание готово!')}\n\n"
        f"{format_key_value('ID ТЗ', code(str(generation_id)))}\n"
        f"{format_key_value('Категория', category)}\n"
        f"{format_key_value('Осталось кредитов', str(remaining_credits))}\n\n"
        f"Вы можете скачать PDF или перегенерировать ТЗ."
    )


def error_message(
    error_text: str,
    error_id: Optional[str] = None,
    can_retry: bool = True,
) -> str:
    """
    Сообщение об ошибке.

    Args:
        error_text: Текст ошибки
        error_id: ID ошибки для репорта
        can_retry: Можно ли повторить

    Returns:
        Форматированное сообщение
    """
    lines: List[str] = [
        f"❌ {bold('Произошла ошибка')}",
        "",
        escape_html(error_text),
    ]

    if error_id:
        lines.extend([
            "",
            italic(f"ID ошибки: {code(error_id)}"),
        ])

    if can_retry:
        lines.append(
            "\nВы можете попробовать снова или связаться с поддержкой."
        )

    return "\n".join(lines)


def not_enough_credits_message(
    current_credits: int,
    required_credits: int = 1,
) -> str:
    """
    Сообщение о недостатке кредитов.

    Args:
        current_credits: Текущее количество
        required_credits: Требуемое количество

    Returns:
        Форматированное сообщение
    """
    return (
        f"⚠️ {bold('Недостаточно кредитов')}\n\n"
        f"{format_key_value('Ваш баланс', str(current_credits))}\n"
        f"{format_key_value('Требуется', str(required_credits))}\n\n"
        f"Для генерации ТЗ необходимо пополнить баланс.\n"
        f"Нажмите «Тарифы» ниже для выбора пакета."
    )


def photo_limit_message(current_count: int, max_count: int) -> str:
    """
    Сообщение о достижении лимита фото.

    Args:
        current_count: Текущее количество
        max_count: Максимум

    Returns:
        Форматированное сообщение
    """
    return (
        f"⚠️ {bold('Достигнут лимит фото')}\n\n"
        f"Вы загрузили {bold(str(current_count))} из {bold(str(max_count))} возможных.\n\n"
        f"Нажмите «Готово» для продолжения или удалите лишние фото."
    )


def file_validation_error(
    filename: str,
    error_reason: str,
    allowed_formats: Optional[List[str]] = None,
) -> str:
    """
    Сообщение об ошибке валидации файла.

    Args:
        filename: Имя файла
        error_reason: Причина ошибки
        allowed_formats: Разрешённые форматы

    Returns:
        Форматированное сообщение
    """
    lines: List[str] = [
        f"❌ {bold('Ошибка загрузки файла')}",
        "",
        f"{format_key_value('Файл', escape_html(filename[:50]))}",
        f"{format_key_value('Причина', error_reason)}",
    ]

    if allowed_formats:
        lines.append(
            f"{format_key_value('Разрешено', ', '.join(allowed_formats))}"
        )

    return "\n".join(lines)


# ============================================================
# АДМИН-ПАНЕЛЬ ШАБЛОНЫ
# ============================================================

def admin_dashboard_header() -> str:
    """Заголовок админ-панели."""
    return (
        f"🔐 {bold('АДМИН-ПАНЕЛЬ')}\n"
        f"{format_separator(20)}\n"
    )


def admin_user_card_header(telegram_id: int, username: Optional[str]) -> str:
    """
    Заголовок карточки пользователя.

    Args:
        telegram_id: Telegram ID
        username: Username

    Returns:
        Форматированный заголовок
    """
    display_name = username or "Без имени"
    return (
        f"👤 {bold('ПОЛЬЗОВАТЕЛЬ')}\n"
        f"{format_separator(20)}\n\n"
        f"{format_key_value('Имя', display_name)}\n"
        f"{format_key_value('Telegram ID', code(str(telegram_id)))}"
    )


def admin_stats_row(label: str, value: Any, icon: str = "") -> str:
    """
    Форматирует строку статистики.

    Args:
        label: Метка
        value: Значение
        icon: Эмодзи

    Returns:
        Форматированная строка
    """
    prefix = f"{icon} " if icon else ""
    return f"{prefix}{bold(label + ':')} {value}"


# ============================================================
# УТИЛИТЫ
# ============================================================

def truncate_message(
    text: str,
    max_length: Optional[int] = None,
    add_ellipsis: bool = True,
) -> str:
    """
    Обрезает сообщение до максимальной длины.

    Args:
        text: Исходный текст
        max_length: Максимальная длина
        add_ellipsis: Добавлять ли многоточие

    Returns:
        Обрезанный текст
    """
    max_len = max_length or MAX_MESSAGE_LENGTH

    if len(text) <= max_len:
        return text

    if add_ellipsis:
        return text[: max_len - 3] + "..."
    return text[:max_len]


def split_long_message(text: str, max_length: Optional[int] = None) -> List[str]:
    """
    Разбивает длинное сообщение на части.

    Args:
        text: Исходный текст
        max_length: Максимальная длина части

    Returns:
        Список частей
    """
    max_len = max_length or MAX_MESSAGE_LENGTH

    if len(text) <= max_len:
        return [text]

    parts: List[str] = []
    while len(text) > max_len:
        # Ищем последний перенос строки
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()

    if text:
        parts.append(text)

    return parts


def sanitize_username(username: Optional[str]) -> str:
    """
    Очищает username для отображения.

    Args:
        username: Исходный username

    Returns:
        Очищенный username
    """
    if not username:
        return "Без имени"

    # Удаляем @ если есть
    clean = username.lstrip("@")

    # Обрезаем если слишком длинный
    if len(clean) > MAX_USERNAME_DISPLAY_LENGTH:
        clean = clean[: MAX_USERNAME_DISPLAY_LENGTH - 3] + "..."

    return clean


def format_datetime(
    dt: Optional[datetime],
    format_str: str = "%d.%m.%Y %H:%M",
    include_time: bool = True,
) -> str:
    """
    Форматирует дату и время.

    Args:
        dt: Дата/время
        format_str: Строка формата
        include_time: Включать ли время

    Returns:
        Форматированная строка
    """
    if not dt:
        return "Не указано"
    return dt.strftime(format_str)


def format_file_size(size_bytes: int) -> str:
    """
    Форматирует размер файла.

    Args:
        size_bytes: Размер в байтах

    Returns:
        Форматированная строка
    """
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} ТБ"


def bold(text: str) -> str:
    """Оборачивает текст в тег <b>."""
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    """Оборачивает текст в тег <i>."""
    return f"<i>{text}</i>"


def code(text: str) -> str:
    """Оборачивает текст в тег <code>."""
    return f"<code>{escape_html(text)}</code>"


def underline(text: str) -> str:
    """Оборачивает текст в тег <u>."""
    return f"<u>{text}</u>"


def spoiler(text: str) -> str:
    """Оборачивает текст в тег <tg-spoiler>."""
    return f"<tg-spoiler>{text}</tg-spoiler>"


def link(text: str, url: str) -> str:
    """Создаёт ссылку."""
    return f'<a href="{url}">{escape_html(text)}</a>'


# ============================================================
# ШАБЛОНЫ СООБЩЕНИЙ
# ============================================================

def format_section_header(text: str, icon: str = "") -> str:
    """
    Форматирует заголовок секции.

    Args:
        text: Текст заголовка
        icon: Необязательный эмодзи

    Returns:
        Форматированный заголовок
    """
    if icon:
        return f"{icon} {bold(text)}"
    return bold(text)


def format_separator(length: int = 20) -> str:
    """Возвращает строку-разделитель."""
    return "━" * length


def format_list_item(item: str, index: Optional[int] = None, bullet: str = "•") -> str:
    """
    Форматирует элемент списка.

    Args:
        item: Текст элемента
        index: Необязательный номер
        bullet: Символ маркера

    Returns:
        Форматированный элемент
    """
    if index is not None:
        return f"{index}. {item}"
    return f"{bullet} {item}"


def format_key_value(key: str, value: str, separator: str = ": ") -> str:
    """
    Форматирует пару ключ-значение.

    Args:
        key: Ключ
        value: Значение
        separator: Разделитель

    Returns:
        Форматированная пара
    """
    return f"{bold(key)}{separator}{value}"


# ============================================================
# ШАБЛОНЫ ПОЛЬЗОВАТЕЛЬСКИХ СООБЩЕНИЙ
# ============================================================

def welcome_message(username: Optional[str] = None) -> str:
    """
    Приветственное сообщение.

    Args:
        username: Имя пользователя

    Returns:
        Форматированное сообщение
    """
    greeting = "Добро пожаловать" if username else "Привет"
    name = username or "!"

    return (
        f"{greeting}{', ' if username else ''}{bold(name)}!\n\n"
        f"🤖 Я — {bold('ТЗшник')}, бот для создания технических заданий "
        f"для маркетплейсов (Wildberries, Ozon, Яндекс.Маркет).\n\n"
        f"Загрузите фото товара, и я составлю профессиональное ТЗ "
        f"с SEO-оптимизированным описанием, характеристиками и требованиями.\n\n"
        f"{format_section_header('Начало работы', '🚀')}\n"
        f"{format_list_item('Нажмите «Создать ТЗ»')}\n"
        f"{format_list_item('Загрузите 1-5 фото товара')}\n"
        f"{format_list_item('Выберите категорию')}\n"
        f"{format_list_item('Получите готовое ТЗ')}\n\n"
        f"Каждая генерация стоит 1 кредит. "
        f"Новые пользователи получают бесплатные кредиты!"
    )


def balance_message(
    credits: int,
    is_unlimited: bool = False,
    unlimited_until: Optional[datetime] = None,
) -> str:
    """
    Сообщение о балансе пользователя.

    Args:
        credits: Количество кредитов
        is_unlimited: Включен ли безлимит
        unlimited_until: Дата окончания безлимита

    Returns:
        Форматированное сообщение
    """
    lines = [
        format_section_header("💰 Ваш баланс"),
        format_separator(20),
        "",
    ]

    if is_unlimited:
        if unlimited_until:
            date_str = unlimited_until.strftime("%d.%m.%Y %H:%M")
            lines.append(f"{bold('Статус:')} ♾️ Безлимит")
            lines.append(f"{bold('До:')} {date_str}")
        else:
            lines.append(f"{bold('Статус:')} ♾️ Безлимит (навсегда)")
    else:
        lines.append(f"{bold('Кредитов:')} {credits}")

    lines.extend([
        "",
        italic("Генерация одного ТЗ стоит 1 кредит."),
        "",
        "Используйте кнопки ниже для управления:",
    ])

    return "\n".join(lines)


def generation_success_message(
    generation_id: int,
    category: str,
    remaining_credits: int,
) -> str:
    """
    Сообщение об успешной генерации.

    Args:
        generation_id: ID генерации
        category: Категория товара
        remaining_credits: Оставшиеся кредиты

    Returns:
        Форматированное сообщение
    """
    return (
        f"✅ {bold('Техническое задание готово!')}\n\n"
        f"{format_key_value('ID ТЗ', code(str(generation_id)))}\n"
        f"{format_key_value('Категория', category)}\n"
        f"{format_key_value('Осталось кредитов', str(remaining_credits))}\n\n"
        f"Вы можете скачать PDF или перегенерировать ТЗ."
    )


def error_message(
    error_text: str,
    error_id: Optional[str] = None,
    can_retry: bool = True,
) -> str:
    """
    Сообщение об ошибке.

    Args:
        error_text: Текст ошибки
        error_id: ID ошибки для репорта
        can_retry: Можно ли повторить

    Returns:
        Форматированное сообщение
    """
    lines = [
        f"❌ {bold('Произошла ошибка')}",
        "",
        escape_html(error_text),
    ]

    if error_id:
        lines.extend([
            "",
            italic(f"ID ошибки: {code(error_id)}"),
        ])

    if can_retry:
        lines.append(
            "\nВы можете попробовать снова или связаться с поддержкой."
        )

    return "\n".join(lines)


def not_enough_credits_message(
    current_credits: int,
    required_credits: int = 1,
) -> str:
    """
    Сообщение о недостатке кредитов.

    Args:
        current_credits: Текущее количество
        required_credits: Требуемое количество

    Returns:
        Форматированное сообщение
    """
    return (
        f"⚠️ {bold('Недостаточно кредитов')}\n\n"
        f"{format_key_value('Ваш баланс', str(current_credits))}\n"
        f"{format_key_value('Требуется', str(required_credits))}\n\n"
        f"Для генерации ТЗ необходимо пополнить баланс.\n"
        f"Нажмите «Тарифы» ниже для выбора пакета."
    )


def photo_limit_message(current_count: int, max_count: int) -> str:
    """
    Сообщение о достижении лимита фото.

    Args:
        current_count: Текущее количество
        max_count: Максимум

    Returns:
        Форматированное сообщение
    """
    return (
        f"⚠️ {bold('Достигнут лимит фото')}\n\n"
        f"Вы загрузили {bold(str(current_count))} из {bold(str(max_count))} возможных.\n\n"
        f"Нажмите «Готово» для продолжения или удалите лишние фото."
    )


def file_validation_error(
    filename: str,
    error_reason: str,
    allowed_formats: Optional[List[str]] = None,
) -> str:
    """
    Сообщение об ошибке валидации файла.

    Args:
        filename: Имя файла
        error_reason: Причина ошибки
        allowed_formats: Разрешённые форматы

    Returns:
        Форматированное сообщение
    """
    lines = [
        f"❌ {bold('Ошибка загрузки файла')}",
        "",
        f"{format_key_value('Файл', escape_html(filename[:50]))}",
        f"{format_key_value('Причина', error_reason)}",
    ]

    if allowed_formats:
        lines.append(
            f"{format_key_value('Разрешено', ', '.join(allowed_formats))}"
        )

    return "\n".join(lines)


# ============================================================
# АДМИН-ПАНЕЛЬ ШАБЛОНЫ
# ============================================================

def admin_dashboard_header() -> str:
    """Заголовок админ-панели."""
    return (
        f"🔐 {bold('АДМИН-ПАНЕЛЬ')}\n"
        f"{format_separator(20)}\n"
    )


def admin_user_card_header(telegram_id: int, username: Optional[str]) -> str:
    """
    Заголовок карточки пользователя.

    Args:
        telegram_id: Telegram ID
        username: Username

    Returns:
        Форматированный заголовок
    """
    display_name = username or "Без имени"
    return (
        f"👤 {bold('ПОЛЬЗОВАТЕЛЬ')}\n"
        f"{format_separator(20)}\n\n"
        f"{format_key_value('Имя', display_name)}\n"
        f"{format_key_value('Telegram ID', code(str(telegram_id)))}"
    )


def admin_stats_row(label: str, value: Any, icon: str = "") -> str:
    """
    Форматирует строку статистики.

    Args:
        label: Метка
        value: Значение
        icon: Эмодзи

    Returns:
        Форматированная строка
    """
    prefix = f"{icon} " if icon else ""
    return f"{prefix}{bold(label + ':')} {value}"


# ============================================================
# УТИЛИТЫ
# ============================================================

def truncate_message(
    text: str,
    max_length: Optional[int] = None,
    add_ellipsis: bool = True,
) -> str:
    """
    Обрезает сообщение до максимальной длины.

    Args:
        text: Исходный текст
        max_length: Максимальная длина
        add_ellipsis: Добавлять ли многоточие

    Returns:
        Обрезанный текст
    """
    max_len = max_length or MAX_MESSAGE_LENGTH

    if len(text) <= max_len:
        return text

    if add_ellipsis:
        return text[: max_len - 3] + "..."
    return text[:max_len]


def split_long_message(text: str, max_length: Optional[int] = None) -> List[str]:
    """
    Разбивает длинное сообщение на части.

    Args:
        text: Исходный текст
        max_length: Максимальная длина части

    Returns:
        Список частей
    """
    max_len = max_length or MAX_MESSAGE_LENGTH

    if len(text) <= max_len:
        return [text]

    parts = []
    while len(text) > max_len:
        # Ищем последний перенос строки
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()

    if text:
        parts.append(text)

    return parts


def sanitize_username(username: Optional[str]) -> str:
    """
    Очищает username для отображения.

    Args:
        username: Исходный username

    Returns:
        Очищенный username
    """
    if not username:
        return "Без имени"

    # Удаляем @ если есть
    clean = username.lstrip("@")

    # Обрезаем если слишком длинный
    if len(clean) > MAX_USERNAME_DISPLAY_LENGTH:
        clean = clean[: MAX_USERNAME_DISPLAY_LENGTH - 3] + "..."

    return clean


def format_datetime(
    dt: datetime,
    format_str: str = "%d.%m.%Y %H:%M",
    include_time: bool = True,
) -> str:
    """
    Форматирует дату и время.

    Args:
        dt: Дата/время
        format_str: Строка формата
        include_time: Включать ли время

    Returns:
        Форматированная строка
    """
    if not dt:
        return "Не указано"
    return dt.strftime(format_str)


def format_file_size(size_bytes: int) -> str:
    """
    Форматирует размер файла.

    Args:
        size_bytes: Размер в байтах

    Returns:
        Форматированная строка
    """
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} ТБ"
