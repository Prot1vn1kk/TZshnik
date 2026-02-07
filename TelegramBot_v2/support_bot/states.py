"""
FSM состояния для бота поддержки.

Определяет flow диалогов для создания тикетов и обмена сообщениями.
"""

from aiogram.fsm.state import State, StatesGroup


class TicketCreationStates(StatesGroup):
    """
    Состояния для создания тикета.

    Flow: start → choose_category → describe_problem → ticket_created
    """

    # Выбор категории проблемы
    choosing_category = State()

    # Ввод описания проблемы
    entering_description = State()


class TicketMessagingStates(StatesGroup):
    """
    Состояния для ведения диалога в тикете.

    Flow: пользователь получает сообщение от админа → может ответить
    """

    # Ответ на сообщение админа
    replying_to_admin = State()
