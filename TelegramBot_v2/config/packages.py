"""
Конфигурация пакетов кредитов.

Определяет доступные пакеты для покупки через YooKassa.
Включает стандартные пакеты и безлимитную подписку.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CreditPackage:
    """
    Пакет кредитов для покупки.
    
    Attributes:
        id: Уникальный идентификатор пакета
        name: Название для отображения
        credits: Количество кредитов (-1 для безлимита)
        price_rub: Цена в рублях
        emoji: Эмодзи для отображения
        is_popular: Популярный пакет (бейдж)
        is_best_value: Самый выгодный (бейдж)
        is_unlimited: Безлимитный тариф
        duration_days: Длительность подписки в днях (для безлимита)
        savings_percent: Процент экономии по сравнению с базовой ценой
    """
    id: str
    name: str
    credits: int
    price_rub: int  # В рублях
    emoji: str
    is_popular: bool = False
    is_best_value: bool = False
    is_unlimited: bool = False
    duration_days: int = 0  # Для безлимитных тарифов
    savings_percent: int = 0  # Процент экономии
    
    @property
    def price_per_credit(self) -> float:
        """Цена за один кредит."""
        if self.is_unlimited or self.credits <= 0:
            return 0.0
        return round(self.price_rub / self.credits, 1)
    
    @property
    def price_kopecks(self) -> int:
        """Цена в копейках для Telegram API."""
        return self.price_rub * 100
    
    @property
    def display_name(self) -> str:
        """Название для отображения с бейджем."""
        badge = ""
        if self.is_unlimited:
            badge = " ♾️"
        elif self.is_popular:
            badge = " 🔥"
        elif self.is_best_value:
            badge = " 💎"
        return f"{self.emoji} {self.name}{badge}"
    
    @property
    def button_text(self) -> str:
        """Текст для кнопки выбора пакета."""
        if self.is_unlimited:
            return f"{self.display_name} — {self.duration_days} дней за {self.price_rub}₽"
        return f"{self.display_name} — {self.credits} ТЗ за {self.price_rub}₽"
    
    @property
    def short_button_text(self) -> str:
        """Короткий текст для компактных кнопок."""
        if self.is_unlimited:
            return f"∞ {self.duration_days}д • {self.price_rub}₽"
        return f"{self.credits} ТЗ • {self.price_rub}₽"
    
    @property
    def description(self) -> str:
        """Описание для Invoice."""
        if self.is_unlimited:
            return (
                f"Безлимитная подписка на {self.duration_days} дней. "
                f"Неограниченное количество генераций ТЗ."
            )
        return (
            f"{self.credits} кредитов для генерации ТЗ. "
            f"Цена за кредит: {self.price_per_credit}₽"
        )
    
    @property
    def credits_display(self) -> str:
        """Отображение количества кредитов."""
        if self.is_unlimited:
            return "∞ Безлимит"
        return f"{self.credits} ТЗ"
    
    def get_expiry_date(self) -> Optional[datetime]:
        """Получить дату окончания подписки (для безлимита)."""
        if self.is_unlimited and self.duration_days > 0:
            return datetime.utcnow() + timedelta(days=self.duration_days)
        return None


# ============================================================
# БАЗОВАЯ ЦЕНА ЗА КРЕДИТ (для расчёта экономии)
# ============================================================
BASE_PRICE_PER_CREDIT = 30.0  # Базовая цена за 1 ТЗ


# ============================================================
# ДОСТУПНЫЕ ПАКЕТЫ
# ============================================================

PACKAGES: Dict[str, CreditPackage] = {
    # Пробный пакет для новичков
    "trial": CreditPackage(
        id="trial",
        name="Пробный",
        credits=3,
        price_rub=79,
        emoji="🎁",
        savings_percent=0,
    ),
    
    # Стартовый пакет
    "start": CreditPackage(
        id="start",
        name="Старт",
        credits=5,
        price_rub=129,
        emoji="🔹",
        savings_percent=14,
    ),
    
    # Базовый пакет
    "basic": CreditPackage(
        id="basic",
        name="Базовый",
        credits=10,
        price_rub=229,
        emoji="📦",
        savings_percent=24,
    ),
    
    # Оптимальный — самый популярный
    "optimal": CreditPackage(
        id="optimal",
        name="Оптимальный",
        credits=25,
        price_rub=449,
        emoji="⭐",
        is_popular=True,
        savings_percent=40,
    ),
    
    # Профессиональный
    "pro": CreditPackage(
        id="pro",
        name="Профи",
        credits=50,
        price_rub=749,
        emoji="🚀",
        savings_percent=50,
    ),
    
    # Бизнес пакет
    "business": CreditPackage(
        id="business",
        name="Бизнес",
        credits=100,
        price_rub=1290,
        emoji="💼",
        is_best_value=True,
        savings_percent=57,
    ),
    
    # Корпоративный пакет
    "enterprise": CreditPackage(
        id="enterprise",
        name="Корпоративный",
        credits=250,
        price_rub=2790,
        emoji="🏢",
        savings_percent=63,
    ),
    
    # БЕЗЛИМИТНЫЙ ТАРИФ
    "unlimited": CreditPackage(
        id="unlimited",
        name="Безлимит",
        credits=-1,  # -1 означает безлимит
        price_rub=1790,
        emoji="👑",
        is_unlimited=True,
        duration_days=30,
        savings_percent=100,
    ),
}


# Группировка пакетов для отображения в меню
PACKAGE_CATEGORIES = {
    "starter": ["trial", "start", "basic"],  # Для новичков
    "popular": ["optimal", "pro"],            # Популярные
    "business": ["business", "enterprise"],   # Для бизнеса
    "premium": ["unlimited"],                 # Премиум
}


def get_package(package_id: str) -> Optional[CreditPackage]:
    """
    Получить пакет по ID.
    
    Args:
        package_id: ID пакета
        
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


def get_regular_packages() -> List[CreditPackage]:
    """Получить только обычные пакеты (без безлимита)."""
    return [p for p in PACKAGES.values() if not p.is_unlimited]


def get_unlimited_packages() -> List[CreditPackage]:
    """Получить только безлимитные пакеты."""
    return [p for p in PACKAGES.values() if p.is_unlimited]


def get_packages_by_category(category: str) -> List[CreditPackage]:
    """Получить пакеты по категории."""
    package_ids = PACKAGE_CATEGORIES.get(category, [])
    return [PACKAGES[pid] for pid in package_ids if pid in PACKAGES]


def calculate_savings(package: CreditPackage) -> int:
    """Рассчитать экономию в рублях."""
    if package.is_unlimited:
        return 0
    base_cost = package.credits * BASE_PRICE_PER_CREDIT
    return int(base_cost - package.price_rub)
