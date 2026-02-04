"""
Модуль конфигурации.

Содержит:
- packages.py - конфигурация пакетов кредитов
"""

from .packages import (
    CreditPackage,
    PACKAGES,
    get_package,
    get_all_packages,
)


__all__ = [
    "CreditPackage",
    "PACKAGES",
    "get_package",
    "get_all_packages",
]
