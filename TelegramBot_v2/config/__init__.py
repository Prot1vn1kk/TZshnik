"""
Модуль конфигурации.

Содержит:
- packages.py - конфигурация пакетов кредитов
- constants.py - константы приложения
"""

from .packages import (
    CreditPackage,
    PACKAGES,
    get_package,
    get_all_packages,
)
from .constants import (
    MAX_PHOTOS_PER_GENERATION,
    ITEMS_PER_PAGE,
    MAX_CREDIT_OPERATION_AMOUNT,
    MIN_CREDIT_OPERATION_AMOUNT,
)


__all__ = [
    "CreditPackage",
    "PACKAGES",
    "get_package",
    "get_all_packages",
    "MAX_PHOTOS_PER_GENERATION",
    "ITEMS_PER_PAGE",
    "MAX_CREDIT_OPERATION_AMOUNT",
    "MIN_CREDIT_OPERATION_AMOUNT",
]
