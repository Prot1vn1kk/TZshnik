"""
Инициализация модуля handlers.

Экспортирует все роутеры для регистрации в диспетчере.
"""

from aiogram import Router

from .start import router as start_router
from .photo import router as photo_router
from .generation import router as generation_router
from .payments import router as payments_router
from .admin import router as admin_router
from .admin_panel import router as admin_panel_router
from .common import router as common_router


def get_main_router() -> Router:
    """
    Создаёт и настраивает главный роутер.
    
    Включает все дочерние роутеры в правильном порядке.
    Порядок важен: более специфичные обработчики должны быть первыми.
    
    Returns:
        Router: Настроенный главный роутер
    """
    main_router = Router(name="main")
    
    # Порядок регистрации важен!
    # 1. Обработчики команд администратора (админ-панель)
    # 2. Старые обработчики админа (для обратной совместимости)
    # 3. Обработчики команд (start)
    # 4. Обработчики платежей (pre_checkout, successful_payment)
    # 5. Обработчики фото
    # 6. Обработчики генерации и callback
    # 7. Общие обработчики (catch-all)
    
    main_router.include_router(admin_panel_router)  # Новая админ-панель
    main_router.include_router(admin_router)        # Старые команды /stats, /users
    main_router.include_router(start_router)
    main_router.include_router(payments_router)
    main_router.include_router(photo_router)
    main_router.include_router(generation_router)
    main_router.include_router(common_router)
    
    return main_router


__all__ = [
    "get_main_router",
    "admin_router",
    "admin_panel_router",
    "start_router",
    "photo_router",
    "generation_router",
    "payments_router",
    "common_router",
]
