"""
FSM States для управления состояниями диалога.

Определяет состояния для:
- Процесса генерации ТЗ
- Процесса оплаты
- Админ-панели
"""

from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    """
    Состояния процесса генерации ТЗ.
    
    Флоу:
    waiting_photo → waiting_more_photos → confirming_photos → waiting_category → generating → waiting_feedback
    
    Дополнительные состояния для управления фото:
    - confirming_photos: подтверждение загруженных фото
    - deleting_photo: выбор фото для удаления
    """
    
    # Ожидание первого фото товара
    waiting_photo = State()
    
    # Ожидание дополнительных фото (опционально)
    waiting_more_photos = State()
    
    # Подтверждение загруженных фото (список файлов + удаление)
    confirming_photos = State()
    
    # Выбор фото для удаления
    deleting_photo = State()
    
    # Выбор категории товара
    waiting_category = State()
    
    # Процесс генерации ТЗ (прогресс-бар)
    generating = State()
    
    # Ожидание оценки сгенерированного ТЗ
    waiting_feedback = State()


class PaymentStates(StatesGroup):
    """
    Состояния процесса оплаты.
    
    Флоу:
    choosing_package → awaiting_payment → payment_complete
    """
    
    # Выбор пакета кредитов
    choosing_package = State()
    
    # Ожидание подтверждения оплаты
    awaiting_payment = State()


class AdminStates(StatesGroup):
    """
    Состояния админ-панели.
    
    Используются для ввода данных от администратора:
    - Поиск пользователей
    - Ввод количества кредитов
    - Ввод причины блокировки
    """
    
    # Поиск пользователя
    searching_user = State()
    
    # Ввод количества кредитов для начисления/списания
    entering_credits_amount = State()
    
    # Ввод кастомного количества кредитов
    entering_custom_credits = State()
    
    # Ввод причины блокировки
    entering_block_reason = State()
    
    # Ввод количества бесплатных кредитов
    entering_free_credits = State()
    
    # Просмотр полного текста ТЗ
    viewing_full_tz = State()

    # Просмотр полного анализа
    viewing_full_analysis = State()

    # Написание ответа в тикете поддержки
    writing_support_reply = State()


class IdeaStates(StatesGroup):
    """Состояния для отправки идеи модераторам."""
    
    # Ожидание текста идеи от пользователя
    waiting_idea_text = State()
