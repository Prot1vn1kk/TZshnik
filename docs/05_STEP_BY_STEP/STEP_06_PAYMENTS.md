# 💳 ШАГ 6: ПЛАТЕЖИ YOOKASSA

> Интеграция оплаты через Telegram Payments + YooKassa

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать:
- Пакеты кредитов для покупки
- Создание инвойса через Telegram Payments
- Обработку pre_checkout_query
- Обработку успешной оплаты
- Начисление кредитов

---

## 💡 ВАЖНО: КАК РАБОТАЕТ YOOKASSA В TELEGRAM

YooKassa интегрируется через **Telegram Payments** — нативный платёжный механизм Telegram.

1. Ты получил токен через @BotFather → Payments → YooKassa
2. Токен выглядит как: `381764678:TEST:...` или `381764678:LIVE:...`
3. Бот создаёт Invoice через Telegram API
4. Telegram показывает платёжную форму (карта, Apple Pay)
5. YooKassa обрабатывает платёж
6. Telegram присылает боту update с `successful_payment`
7. Бот начисляет кредиты

**Плюсы:**
- Не нужен свой сервер для вебхуков
- Безопасная обработка карт (через Telegram)
- Apple Pay / Google Pay из коробки

---

## 📁 СТРУКТУРА ФАЙЛОВ

```
bot/
├── handlers/
│   ├── payments.py         # Обработчики платежей
├── keyboards.py             # + клавиатуры пакетов
```

```
config/
└── packages.py              # Конфигурация пакетов
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай модуль платежей через YooKassa для Telegram-бота.

КОНТЕКСТ:
YooKassa подключена через BotFather → Payments.
Токен: YOOKASSA_PROVIDER_TOKEN в .env

ПАКЕТЫ КРЕДИТОВ:
1. Старт: 5 кредитов за 490₽ (98₽/шт)
2. Оптимальный: 15 кредитов за 990₽ (66₽/шт) — популярный
3. ПРО: 50 кредитов за 2490₽ (49.8₽/шт) — выгодный

ФЛОУ ОПЛАТЫ:
1. Пользователь нажимает "Купить кредиты" или когда баланс = 0
2. Показываем клавиатуру с пакетами
3. При выборе пакета — создаём Invoice
4. Telegram показывает платёжную форму
5. pre_checkout_query — подтверждаем (всегда ok)
6. successful_payment — начисляем кредиты
7. Отправляем подтверждение

ЗАДАЧА:

1. Создай config/packages.py:
   - Dataclass CreditPackage:
     * id: str (start/optimal/pro)
     * name: str
     * credits: int
     * price_rub: int (рубли, не копейки!)
     * price_per_credit: float
     * is_popular: bool
     * is_best_value: bool
     * emoji: str
   - PACKAGES: Dict[str, CreditPackage] — все пакеты

2. Обнови bot/keyboards.py:
   - InlineKeyboardMarkup get_packages_keyboard() — кнопки пакетов
   - Формат кнопки: "{emoji} {name} — {credits} кредитов за {price}₽"
   - Callback: "buy:{package_id}"

3. Создай bot/handlers/payments.py:
   - Callback handler для "buy:{package_id}":
     * Получить пакет по id
     * Создать Invoice через bot.send_invoice()
     * Параметры Invoice:
       - title: "Пакет {name}"
       - description: "{credits} кредитов для генерации ТЗ"
       - payload: "credits:{package_id}:{user_id}"
       - provider_token: settings.YOOKASSA_PROVIDER_TOKEN
       - currency: "RUB"
       - prices: [LabeledPrice(label=name, amount=price * 100)]  # В КОПЕЙКАХ!
   - pre_checkout_query handler:
     * Всегда отвечать answer_pre_checkout_query(ok=True)
   - successful_payment handler:
     * Распарсить payload
     * Начислить кредиты пользователю
     * Сохранить Payment в БД
     * Отправить подтверждение

4. Добавь в .env.example:
   YOOKASSA_PROVIDER_TOKEN=your_token_from_botfather

ФОРМАТ INVOICE:
```python
await bot.send_invoice(
    chat_id=chat_id,
    title="Пакет Оптимальный",
    description="15 кредитов для генерации ТЗ",
    payload=f"credits:optimal:{user_id}",
    provider_token=settings.YOOKASSA_PROVIDER_TOKEN,
    currency="RUB",
    prices=[
        types.LabeledPrice(
            label="15 кредитов",
            amount=99000  # 990 рублей в копейках
        )
    ],
    start_parameter="buy_credits"
)
```

ПРАВИЛА:
{Правила из docs/01_RULES_FOR_AI.md}

ТРЕБОВАНИЯ:
1. Цены в send_invoice всегда в КОПЕЙКАХ (amount * 100)
2. Payload формат: "credits:{package_id}:{user_id}"
3. Логирование всех платежей
4. Сохранение telegram_payment_id из successful_payment

Создай полный код всех файлов.
```

---

## 📦 КЛЮЧЕВЫЕ ФАЙЛЫ

### config/packages.py

```python
"""
Конфигурация пакетов кредитов.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CreditPackage:
    """Пакет кредитов для покупки."""
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
        """Название для отображения."""
        badge = ""
        if self.is_popular:
            badge = " 🔥"
        elif self.is_best_value:
            badge = " 💎"
        return f"{self.emoji} {self.name}{badge}"
    
    @property
    def button_text(self) -> str:
        """Текст для кнопки."""
        return f"{self.display_name} — {self.credits} кредитов за {self.price_rub}₽"
    
    @property
    def description(self) -> str:
        """Описание для Invoice."""
        return (
            f"{self.credits} кредитов для генерации ТЗ. "
            f"Цена за кредит: {self.price_per_credit}₽"
        )


# Все доступные пакеты
PACKAGES: Dict[str, CreditPackage] = {
    "start": CreditPackage(
        id="start",
        name="Старт",
        credits=5,
        price_rub=490,
        emoji="⭐"
    ),
    "optimal": CreditPackage(
        id="optimal",
        name="Оптимальный",
        credits=15,
        price_rub=990,
        emoji="🚀",
        is_popular=True
    ),
    "pro": CreditPackage(
        id="pro",
        name="ПРО",
        credits=50,
        price_rub=2490,
        emoji="👑",
        is_best_value=True
    )
}


def get_package(package_id: str) -> CreditPackage | None:
    """Получить пакет по ID."""
    return PACKAGES.get(package_id)


def get_all_packages() -> list[CreditPackage]:
    """Получить все пакеты."""
    return list(PACKAGES.values())
```

### bot/keyboards.py (дополнение)

```python
# Добавить к существующим импортам и функциям:

from config.packages import get_all_packages, CreditPackage


def get_packages_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора пакета кредитов.
    
    Показывает все пакеты с ценами и бейджами.
    """
    buttons = []
    
    for package in get_all_packages():
        buttons.append([
            InlineKeyboardButton(
                text=package.button_text,
                callback_data=f"buy:{package.id}"
            )
        ])
    
    # Кнопка отмены
    buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешной оплаты."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📷 Загрузить фото",
                    callback_data="upload_photo"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Мой баланс",
                    callback_data="balance"
                )
            ]
        ]
    )
```

### bot/handlers/payments.py

```python
"""
Обработчики платежей через YooKassa + Telegram Payments.
"""

import structlog
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    Message,
    LabeledPrice,
    PreCheckoutQuery
)

from config.settings import settings
from config.packages import get_package, PACKAGES
from database import crud
from database.models import User
from bot.keyboards import get_packages_keyboard, get_payment_success_keyboard

router = Router(name="payments")
logger = structlog.get_logger()


@router.callback_query(F.data == "buy_credits")
async def show_packages(callback: CallbackQuery, user: User) -> None:
    """Показать доступные пакеты для покупки."""
    await callback.answer()
    
    text = (
        "💳 <b>Выбери пакет кредитов</b>\n\n"
        "Один кредит = одно ТЗ\n\n"
    )
    
    for package in PACKAGES.values():
        badge = ""
        if package.is_popular:
            badge = "🔥 Популярный"
        elif package.is_best_value:
            badge = "💎 Выгодный"
        
        text += (
            f"{package.emoji} <b>{package.name}</b> {badge}\n"
            f"   {package.credits} кредитов за {package.price_rub}₽ "
            f"({package.price_per_credit}₽/шт)\n\n"
        )
    
    text += f"\n💰 Твой баланс: {user.balance} кредитов"
    
    await callback.message.edit_text(
        text=text,
        reply_markup=get_packages_keyboard()
    )


@router.callback_query(F.data.startswith("buy:"))
async def handle_buy_package(
    callback: CallbackQuery,
    bot: Bot,
    user: User
) -> None:
    """Обработка выбора пакета — создание Invoice."""
    await callback.answer()
    
    package_id = callback.data.split(":")[1]
    package = get_package(package_id)
    
    if not package:
        await callback.message.edit_text("⚠️ Пакет не найден")
        return
    
    logger.info(
        "payment_invoice_creating",
        user_id=callback.from_user.id,
        package=package_id,
        amount=package.price_rub
    )
    
    # Удаляем сообщение с выбором
    await callback.message.delete()
    
    # Создаём Invoice через Telegram Payments
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"Пакет {package.name}",
        description=package.description,
        payload=f"credits:{package.id}:{callback.from_user.id}",
        provider_token=settings.YOOKASSA_PROVIDER_TOKEN,
        currency="RUB",
        prices=[
            LabeledPrice(
                label=f"{package.credits} кредитов",
                amount=package.price_kopecks  # В копейках!
            )
        ],
        start_parameter=f"buy_{package.id}",
        # Опциональные параметры для красивого отображения
        photo_url="https://example.com/credits_image.png",  # Замени на свою картинку
        photo_width=600,
        photo_height=400,
        need_name=False,
        need_phone_number=False,
        need_email=False,
        send_phone_number_to_provider=False,
        send_email_to_provider=False,
        is_flexible=False  # Фиксированная цена
    )


@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout: PreCheckoutQuery) -> None:
    """
    Обработка pre_checkout_query.
    
    Telegram спрашивает: "Можно проводить оплату?"
    Мы отвечаем: "Да, всё ок"
    
    Здесь можно проверить:
    - Доступность товара
    - Актуальность цены
    - Лимиты пользователя
    """
    logger.info(
        "pre_checkout_query",
        user_id=pre_checkout.from_user.id,
        total_amount=pre_checkout.total_amount,
        payload=pre_checkout.invoice_payload
    )
    
    # Валидируем payload
    try:
        parts = pre_checkout.invoice_payload.split(":")
        if len(parts) != 3 or parts[0] != "credits":
            await pre_checkout.answer(
                ok=False,
                error_message="Некорректный запрос. Попробуй заново."
            )
            return
        
        package_id = parts[1]
        package = get_package(package_id)
        
        if not package:
            await pre_checkout.answer(
                ok=False,
                error_message="Пакет не найден. Попробуй заново."
            )
            return
        
        # Проверяем что цена не изменилась
        if pre_checkout.total_amount != package.price_kopecks:
            await pre_checkout.answer(
                ok=False,
                error_message="Цена изменилась. Попробуй заново."
            )
            return
        
    except Exception as e:
        logger.error("pre_checkout_validation_error", error=str(e))
        await pre_checkout.answer(
            ok=False,
            error_message="Ошибка валидации. Попробуй заново."
        )
        return
    
    # Всё ок — разрешаем оплату
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def handle_successful_payment(message: Message, user: User) -> None:
    """
    Обработка успешной оплаты.
    
    Telegram присылает это сообщение после того как:
    1. Пользователь оплатил через форму
    2. YooKassa подтвердила платёж
    """
    payment = message.successful_payment
    
    logger.info(
        "payment_successful",
        user_id=message.from_user.id,
        telegram_payment_id=payment.telegram_payment_charge_id,
        provider_payment_id=payment.provider_payment_charge_id,
        total_amount=payment.total_amount,
        currency=payment.currency,
        payload=payment.invoice_payload
    )
    
    try:
        # Парсим payload
        parts = payment.invoice_payload.split(":")
        package_id = parts[1]
        payload_user_id = int(parts[2])
        
        # Проверяем что это тот же пользователь
        if message.from_user.id != payload_user_id:
            logger.error(
                "payment_user_mismatch",
                expected=payload_user_id,
                actual=message.from_user.id
            )
        
        package = get_package(package_id)
        if not package:
            logger.error("payment_package_not_found", package_id=package_id)
            await message.answer(
                "⚠️ Ошибка: пакет не найден. "
                "Обратись в поддержку с ID платежа: "
                f"{payment.telegram_payment_charge_id}"
            )
            return
        
        # Сохраняем платёж в БД
        db_payment = await crud.create_payment(
            user_id=user.id,
            amount=payment.total_amount / 100,  # Конвертируем в рубли
            currency=payment.currency,
            package_id=package.id,
            credits_amount=package.credits,
            telegram_payment_id=payment.telegram_payment_charge_id,
            provider_payment_id=payment.provider_payment_charge_id
        )
        
        # Начисляем кредиты
        await crud.increase_balance(
            telegram_id=message.from_user.id,
            amount=package.credits
        )
        
        # Обновляем пользователя для актуального баланса
        updated_user = await crud.get_user_by_telegram_id(message.from_user.id)
        new_balance = updated_user.balance if updated_user else user.balance + package.credits
        
        logger.info(
            "credits_added",
            user_id=user.id,
            credits=package.credits,
            new_balance=new_balance
        )
        
        # Отправляем подтверждение
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"📦 Пакет: {package.display_name}\n"
            f"💰 Сумма: {package.price_rub}₽\n"
            f"➕ Начислено: +{package.credits} кредитов\n\n"
            f"💳 Твой баланс: <b>{new_balance}</b> кредитов\n\n"
            f"Теперь ты можешь создать {new_balance} ТЗ! 🎉",
            reply_markup=get_payment_success_keyboard()
        )
        
    except Exception as e:
        logger.error(
            "payment_processing_error",
            error=str(e),
            payment_id=payment.telegram_payment_charge_id
        )
        
        await message.answer(
            "⚠️ Произошла ошибка при обработке платежа.\n\n"
            "Не переживай — платёж прошёл, кредиты будут начислены.\n"
            "Если через 5 минут баланс не обновится, "
            f"напиши в поддержку с ID: {payment.telegram_payment_charge_id}"
        )


@router.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery, user: User) -> None:
    """Показать текущий баланс."""
    await callback.answer()
    
    # Получаем историю платежей
    payments = await crud.get_user_payments(user.id, limit=3)
    
    text = (
        f"💰 <b>Твой баланс</b>\n\n"
        f"Кредитов: <b>{user.balance}</b>\n"
        f"Создано ТЗ: {user.total_generated}\n"
    )
    
    if payments:
        text += "\n📜 <b>Последние пополнения:</b>\n"
        for payment in payments:
            text += f"• {payment.created_at.strftime('%d.%m')} — +{payment.credits_amount} кредитов\n"
    
    if user.balance == 0:
        text += "\n⬇️ Выбери пакет для пополнения:"
        keyboard = get_packages_keyboard()
    else:
        from bot.keyboards import get_main_keyboard
        keyboard = get_main_keyboard()
        text += "\n📷 Загрузи фото товара для генерации ТЗ"
    
    await callback.message.edit_text(text, reply_markup=keyboard)
```

### database/crud.py (дополнения для платежей)

```python
# Добавить к существующим функциям:

async def create_payment(
    user_id: int,
    amount: float,
    currency: str,
    package_id: str,
    credits_amount: int,
    telegram_payment_id: str,
    provider_payment_id: str
) -> Payment:
    """Создать запись о платеже."""
    async with async_session() as session:
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency=currency,
            package_id=package_id,
            credits_amount=credits_amount,
            telegram_payment_id=telegram_payment_id,
            provider_payment_id=provider_payment_id,
            status="completed"
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment


async def get_user_payments(
    user_id: int,
    limit: int = 10
) -> list[Payment]:
    """Получить платежи пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(Payment)
            .filter(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def increase_balance(telegram_id: int, amount: int) -> bool:
    """Увеличить баланс пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(User).filter(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        user.balance += amount
        await session.commit()
        return True


async def decrease_balance(telegram_id: int, amount: int = 1) -> bool:
    """Уменьшить баланс пользователя (списать кредиты)."""
    async with async_session() as session:
        result = await session.execute(
            select(User).filter(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or user.balance < amount:
            return False
        
        user.balance -= amount
        await session.commit()
        return True
```

---

## ⚙️ КОНФИГУРАЦИЯ

### .env

```bash
# YooKassa Token (получен через BotFather → Payments)
YOOKASSA_PROVIDER_TOKEN=381764678:LIVE:xxx

# Для тестирования используй TEST токен
# YOOKASSA_PROVIDER_TOKEN=381764678:TEST:xxx
```

### config/settings.py (дополнение)

```python
# Добавить поле:
yookassa_provider_token: str = Field(
    alias="YOOKASSA_PROVIDER_TOKEN",
    description="Provider token from BotFather for YooKassa"
)
```

---

## 🧪 ТЕСТИРОВАНИЕ ПЛАТЕЖЕЙ

### Тестовый режим

1. Получи TEST токен в BotFather → Payments → YooKassa
2. Используй тестовые карты:
   - **Успешный платёж**: 5555 5555 5555 4477
   - **Отклонённый платёж**: 5555 5555 5555 4444
   - CVV: любые 3 цифры
   - Срок: любой в будущем

### Проверка флоу

```
1. /start
2. Нажми "💰 Купить кредиты"
3. Выбери пакет "Старт"
4. Telegram откроет платёжную форму
5. Введи тестовую карту
6. Подтверди оплату
7. Получи сообщение о начислении кредитов
8. Проверь баланс через "📊 Баланс"
```

---

## ✅ ЧЕКЛИСТ ВЫПОЛНЕНИЯ

- [ ] config/packages.py создан
- [ ] Клавиатура пакетов работает
- [ ] Invoice создаётся корректно
- [ ] pre_checkout_query обрабатывается
- [ ] successful_payment начисляет кредиты
- [ ] Платёж сохраняется в БД
- [ ] Баланс обновляется

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

1. **ЦЕНЫ В КОПЕЙКАХ**: В `send_invoice` параметр `amount` всегда в копейках!
   - 990₽ = `amount=99000`

2. **УНИКАЛЬНЫЙ PAYLOAD**: Payload должен быть уникальным для каждого платежа.
   Используем формат: `credits:{package}:{user_id}`

3. **ОБРАБОТКА ОШИБОК**: Если ошибка после оплаты — не теряй платёж!
   Сохраняй `telegram_payment_charge_id` для разбора.

4. **ТЕСТИРОВАНИЕ**: Всегда тестируй с TEST токеном перед продакшеном.

---

## ➡️ СЛЕДУЮЩИЙ ШАГ

После успешного выполнения переходи к [STEP_07_FINAL.md](STEP_07_FINAL.md)

---

*Шаг 6 из 7*
