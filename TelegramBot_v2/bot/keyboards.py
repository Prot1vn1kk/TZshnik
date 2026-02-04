"""
Клавиатуры бота.

Содержит все Reply и Inline клавиатуры:
- Главное меню
- Выбор категории
- Действия с фото
- Результат генерации
- Выбор пакета
"""

from typing import Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ============================================================
# КОНСТАНТЫ
# ============================================================

# Категории товаров для выбора
CATEGORY_BUTTONS = {
    "clothes": "👕 Одежда",
    "electronics": "📱 Электроника",
    "cosmetics": "💄 Косметика",
    "home": "🏠 Дом",
    "kids": "👶 Детям",
    "sports": "⚽ Спорт",
    "other": "📦 Другое",
}

# Пакеты для покупки
PACKAGES = {
    "start": {"name": "🔹 Старт", "credits": 5, "price": 149},
    "optimal": {"name": "⭐ Оптимальный", "credits": 20, "price": 399},
    "pro": {"name": "🚀 Профи", "credits": 50, "price": 699},
}


# ============================================================
# REPLY КЛАВИАТУРЫ
# ============================================================

def get_main_keyboard() -> ReplyKeyboardRemove:
    """
    Убирает reply-клавиатуру, оставляя только inline-кнопки.
    
    Теперь бот использует только inline-клавиатуры для чистого интерфейса.
    """
    return ReplyKeyboardRemove()


def get_start_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Inline клавиатура для стартового сообщения.
    
    Показывает быстрые действия после /start.
    """
    builder = InlineKeyboardBuilder()
    
    # Главное действие
    builder.button(
        text="🚀 Создать ТЗ",
        callback_data="start_generation",
    )
    
    # Быстрый доступ
    builder.button(
        text="📝 Примеры работ",
        callback_data="show_examples",
    )
    builder.button(
        text="💳 Тарифы",
        callback_data="show_packages",
    )
    
    builder.adjust(1, 2)
    return builder.as_markup()


def get_remove_keyboard() -> ReplyKeyboardRemove:
    """Удалить Reply клавиатуру."""
    return ReplyKeyboardRemove()


# ============================================================
# INLINE КЛАВИАТУРЫ - КАТЕГОРИИ
# ============================================================

def get_category_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора категории товара.
    
    Показывается после загрузки фото.
    """
    builder = InlineKeyboardBuilder()
    
    for key, name in CATEGORY_BUTTONS.items():
        builder.button(
            text=name,
            callback_data=f"category:{key}",
        )
    
    # По 2 кнопки в ряд
    builder.adjust(2)
    return builder.as_markup()


# ============================================================
# INLINE КЛАВИАТУРЫ - ФОТО
# ============================================================

def get_photo_actions_keyboard(photo_count: int) -> InlineKeyboardMarkup:
    """
    Клавиатура действий после загрузки фото.
    
    Args:
        photo_count: Текущее количество загруженных фото
    """
    builder = InlineKeyboardBuilder()
    
    # Если можно загрузить ещё фото
    if photo_count < 5:
        builder.button(
            text=f"📷 Добавить ещё фото ({photo_count}/5)",
            callback_data="add_more_photos",
        )
    
    builder.button(
        text="✅ Продолжить",
        callback_data="continue_generation",
    )
    builder.button(
        text="❌ Отмена",
        callback_data="cancel",
    )
    
    builder.adjust(1)
    return builder.as_markup()


# ============================================================
# INLINE КЛАВИАТУРЫ - РЕЗУЛЬТАТ ГЕНЕРАЦИИ
# ============================================================

def get_generation_result_keyboard(
    generation_id: int,
    can_regenerate: bool = True,
) -> InlineKeyboardMarkup:
    """
    Клавиатура после успешной генерации ТЗ.
    
    Args:
        generation_id: ID генерации в БД
        can_regenerate: Доступна ли перегенерация
    """
    builder = InlineKeyboardBuilder()
    
    # Первый ряд: PDF и перегенерация
    builder.button(
        text="📄 Скачать PDF",
        callback_data=f"download_pdf:{generation_id}",
    )
    
    if can_regenerate:
        builder.button(
            text="🔄 Перегенерировать",
            callback_data=f"regenerate:{generation_id}",
        )
    
    # Второй ряд: оценка
    builder.button(
        text="👍",
        callback_data=f"feedback:{generation_id}:1",
    )
    builder.button(
        text="👎",
        callback_data=f"feedback:{generation_id}:0",
    )
    
    builder.adjust(2, 2)
    return builder.as_markup()


def get_after_feedback_keyboard(generation_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после оценки (только PDF)."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="📄 Скачать PDF",
        callback_data=f"download_pdf:{generation_id}",
    )
    builder.button(
        text="📸 Создать ещё ТЗ",
        callback_data="new_generation",
    )
    
    builder.adjust(1)
    return builder.as_markup()


# ============================================================
# INLINE КЛАВИАТУРЫ - ПЛАТЕЖИ
# ============================================================

def get_packages_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пакета для покупки."""
    builder = InlineKeyboardBuilder()
    
    for key, package in PACKAGES.items():
        builder.button(
            text=f"{package['name']}: {package['credits']} ТЗ за {package['price']}₽",
            callback_data=f"buy_package:{key}",
        )
    
    # Навигация
    builder.button(
        text="⬅️ Назад в меню",
        callback_data="show_main_menu",
    )
    builder.button(
        text="❌ Отмена",
        callback_data="cancel",
    )
    
    builder.adjust(1, 2)
    return builder.as_markup()


def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура на экране баланса."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="💳 Пополнить баланс",
        callback_data="show_packages",
    )
    builder.button(
        text="📋 История покупок",
        callback_data="payment_history",
    )
    
    # Навигация
    builder.button(
        text="📖 В главное меню",
        callback_data="show_main_menu",
    )
    
    builder.adjust(2, 1)
    return builder.as_markup()


# ============================================================
# INLINE КЛАВИАТУРЫ - ОБЩИЕ
# ============================================================

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


def get_confirm_keyboard(
    confirm_callback: str,
    cancel_callback: str = "cancel",
) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия.
    
    Args:
        confirm_callback: callback_data для подтверждения
        cancel_callback: callback_data для отмены
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Подтвердить", callback_data=confirm_callback)
    builder.button(text="❌ Отмена", callback_data=cancel_callback)
    
    builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)]
        ]
    )


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура для главного меню с навигацией."""
    builder = InlineKeyboardBuilder()
    
    # Основные действия
    builder.button(text="🚀 Создать ТЗ", callback_data="start_generation")
    builder.button(text="💰 Баланс", callback_data="show_balance")
    
    # Информационные разделы
    builder.button(text="📋 Мои ТЗ", callback_data="show_history")
    builder.button(text="📝 Примеры", callback_data="show_examples")
    
    # Тарифы
    builder.button(text="💳 Тарифы", callback_data="show_packages")
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_examples_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура для раздела примеров с выбором категорий."""
    builder = InlineKeyboardBuilder()
    
    # Кнопки категорий для просмотра примеров
    builder.button(text="👕 Одежда", callback_data="example:clothes")
    builder.button(text="📱 Электроника", callback_data="example:electronics")
    builder.button(text="💄 Косметика", callback_data="example:cosmetics")
    builder.button(text="🏠 Дом", callback_data="example:home")
    builder.button(text="👶 Детские", callback_data="example:kids")
    builder.button(text="⚽ Спорт", callback_data="example:sports")
    
    # Действия
    builder.button(text="🚀 Создать своё ТЗ", callback_data="start_generation")
    
    # Навигация
    builder.button(text="📖 В главное меню", callback_data="show_main_menu")
    
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def get_example_detail_keyboard(category: str) -> InlineKeyboardMarkup:
    """
    Inline клавиатура для детального просмотра примера.
    
    Args:
        category: Категория текущего примера
    """
    builder = InlineKeyboardBuilder()
    
    # Действия
    builder.button(text="🚀 Создать такое ТЗ", callback_data="start_generation")
    builder.button(text="💳 Купить кредиты", callback_data="show_packages")
    
    # Навигация
    builder.button(text="⬅️ Все примеры", callback_data="show_examples")
    builder.button(text="📖 Главное меню", callback_data="show_main_menu")
    
    builder.adjust(2, 2)
    return builder.as_markup()


def get_history_keyboard(generations: list = None) -> InlineKeyboardMarkup:
    """
    Inline клавиатура для раздела истории с навигацией.
    
    Args:
        generations: Список генераций пользователя (опционально)
    """
    builder = InlineKeyboardBuilder()
    
    # Если есть генерации, добавляем кнопки для каждой
    if generations:
        for gen in generations[:5]:  # Показываем последние 5
            category = gen.category or "other"
            date_str = gen.created_at.strftime("%d.%m %H:%M")
            builder.button(
                text=f"📄 {date_str} — {category}",
                callback_data=f"view_tz:{gen.id}",
            )
    
    # Действия
    builder.button(text="🚀 Создать ещё ТЗ", callback_data="start_generation")
    builder.button(text="💰 Пополнить баланс", callback_data="show_packages")
    
    # Навигация
    builder.button(text="📖 В главное меню", callback_data="show_main_menu")
    
    # Располагаем: по 1 кнопке для генераций, потом 2+1 для остальных
    if generations:
        adjust = [1] * min(len(generations), 5) + [2, 1]
    else:
        adjust = [2, 1]
    builder.adjust(*adjust)
    return builder.as_markup()


def get_tz_detail_keyboard(generation_id: int) -> InlineKeyboardMarkup:
    """
    Inline клавиатура для просмотра конкретного ТЗ.
    
    Args:
        generation_id: ID генерации
    """
    builder = InlineKeyboardBuilder()
    
    # Действия с ТЗ
    builder.button(text="📥 Скачать PDF", callback_data=f"download_pdf:{generation_id}")
    builder.button(text="💡 Предложить идею", callback_data="suggest_idea")
    
    # Навигация
    builder.button(text="⬅️ Мои ТЗ", callback_data="show_history")
    builder.button(text="📖 Главное меню", callback_data="show_main_menu")
    
    builder.adjust(2, 2)
    return builder.as_markup()
