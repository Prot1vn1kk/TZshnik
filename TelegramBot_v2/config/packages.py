"""
Конфигурация пакетов кредитов.

Определяет доступные пакеты для покупки через YooKassa.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CreditPackage:
    """
    Пакет кредитов для покупки.
    
    Attributes:
        id: Уникальный идентификатор пакета
        name: Название для отображения
        credits: Количество кредитов
        price_rub: Цена в рублях
        emoji: Эмодзи для отображения
        is_popular: Популярный пакет (бейдж)
        is_best_value: Самый выгодный (бейдж)
    """
    id: str
    name: str
    credits: int
    price_rub: int  # В рублях
    emoji: str
    is_popular: bool = False
    is_best_value: bool = False
    
    @property
    def price_per_credit(self) -> float:
        """Цена за один кредит."""
        return round(self.price_rub / self.credits, 1)
    
    @property
    def price_kopecks(self) -> int:
        """Цена в копейках для Telegram API."""
        return self.price_rub * 100
    
    @property
    def display_name(self) -> str:
        """Название для отображения с бейджем."""
        badge = ""
        if self.is_popular:
            badge = " 🔥"
        elif self.is_best_value:
            badge = " 💎"
        return f"{self.emoji} {self.name}{badge}"
    
    @property
    def button_text(self) -> str:
        """Текст для кнопки выбора пакета."""
        return f"{self.display_name} — {self.credits} ТЗ за {self.price_rub}₽"
    
    @property
    def description(self) -> str:
        """Описание для Invoice."""
        return (
            f"{self.credits} кредитов для генерации ТЗ. "
            f"Цена за кредит: {self.price_per_credit}₽"
        )


# ============================================================
# ДОСТУПНЫЕ ПАКЕТЫ
# ============================================================

PACKAGES: Dict[str, CreditPackage] = {
    "start": CreditPackage(
        id="start",
        name="Старт",
        credits=5,
        price_rub=149,
        emoji="🔹",
    ),
    "optimal": CreditPackage(
        id="optimal",
        name="Оптимальный",
        credits=20,
        price_rub=399,
        emoji="⭐",
        is_popular=True,
    ),
    "pro": CreditPackage(
        id="pro",
        name="Профи",
        credits=50,
        price_rub=699,
        emoji="🚀",
        is_best_value=True,
    ),
}


def get_package(package_id: str) -> Optional[CreditPackage]:
    """
    Получить пакет по ID.
    
    Args:
        package_id: ID пакета (start, optimal, pro)
        
    Returns:
        CreditPackage или None если не найден
    """
    return PACKAGES.get(package_id)


def get_all_packages() -> List[CreditPackage]:
    """
    Получить все доступные пакеты.
    
    Returns:
        List[CreditPackage]: Список всех пакетов
    """
    return list(PACKAGES.values())
