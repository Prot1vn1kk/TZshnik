# 📱 ШАГ 4: HANDLERS БОТА

> Создание обработчиков команд и сообщений

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать:
- FSM States для управления состояниями
- Handler /start с онбордингом
- Handler для приёма фото
- Клавиатуры (reply и inline)
- Middleware для БД
- Базовый handler для генерации

---

## 📁 СТРУКТУРА ФАЙЛОВ

После этого шага:

```
bot/
├── __init__.py
├── main.py                  # Обновить
├── config.py                # Уже есть
├── keyboards.py             # Клавиатуры
├── states.py                # FSM States
├── middleware.py            # Middleware
└── handlers/
    ├── __init__.py
    ├── start.py             # /start, /help
    ├── photo.py             # Приём фото
    ├── generation.py        # Генерация ТЗ
    └── common.py            # Общие handlers
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай handlers для Telegram-бота на aiogram 3.x.

КОНТЕКСТ:
Бот "ТЗшник" принимает фото товара, анализирует через AI и генерирует ТЗ для инфографики.

ЗАДАЧА:
1. Создай bot/states.py:
   - GenerationStates (StatesGroup):
     * waiting_photo - ожидание фото
     * waiting_more_photos - ожидание доп. фото (опционально)
     * waiting_category - выбор категории
     * generating - процесс генерации
     * waiting_feedback - ожидание оценки

2. Создай bot/keyboards.py:
   - get_main_keyboard() - главное Reply меню
   - get_category_keyboard() - выбор категории (Inline)
   - get_photo_actions_keyboard() - действия с фото (Inline)
   - get_generation_result_keyboard(generation_id) - после генерации
   - get_packages_keyboard() - выбор пакета для покупки
   - get_cancel_keyboard() - кнопка отмены

3. Создай bot/middleware.py:
   - DatabaseMiddleware - инъекция сессии БД в data
   - UserMiddleware - автоматическое получение/создание пользователя

4. Создай bot/handlers/start.py:
   - /start - приветствие, регистрация, показ баланса
   - /help - справка по командам
   - /balance - показать баланс
   - /history - история генераций (кратко)
   - Обработка deep link для реферальной системы (/start ref_123456)

5. Создай bot/handlers/photo.py:
   - Приём фото (message.photo)
   - Сохранение file_id в state
   - Предложение загрузить ещё фото или продолжить
   - Показ выбора категории
   - Максимум 5 фото

6. Создай bot/handlers/generation.py:
   - Callback для выбора категории
   - Проверка баланса
   - Запуск генерации с прогресс-баром
   - Отправка результата
   - Callback для перегенерации
   - Callback для скачивания PDF

7. Создай bot/handlers/common.py:
   - Callback для отмены (/cancel)
   - Обработка неизвестных сообщений
   - Обработка ошибок

8. Обнови bot/handlers/__init__.py:
   - Экспорт всех роутеров

9. Обнови bot/main.py:
   - Подключение middleware
   - Регистрация роутеров
   - Инициализация БД при старте

КАТЕГОРИИ ДЛЯ ВЫБОРА:
{
    "clothes": "👕 Одежда",
    "electronics": "📱 Электроника",
    "cosmetics": "💄 Косметика",
    "home": "🏠 Дом",
    "kids": "👶 Детям",
    "sports": "⚽ Спорт",
    "other": "📦 Другое"
}

ПАКЕТЫ ДЛЯ ПОКУПКИ:
{
    "start": {"name": "Старт", "credits": 5, "price": 149},
    "optimal": {"name": "Оптимальный", "credits": 20, "price": 399},
    "pro": {"name": "Профи", "credits": 50, "price": 699}
}

ФЛОУ ГЕНЕРАЦИИ:
1. Пользователь отправляет фото
2. Бот спрашивает: ещё фото или продолжить?
3. Пользователь нажимает "Продолжить"
4. Бот показывает выбор категории
5. Пользователь выбирает категорию
6. Бот проверяет баланс:
   - Если есть кредиты → начинает генерацию
   - Если нет → предлагает купить пакет
7. Во время генерации показывается прогресс-бар (редактируется сообщение)
8. После генерации отправляется ТЗ + кнопки [PDF] [Перегенерировать] [Оценить]

ПРОГРЕСС-БАР (4 этапа):
- ✅ Анализ фото
- 🔄 Изучение аудитории... (или ✅)
- ⬜ Генерация текстов
- ⬜ Финальная проверка

ПРАВИЛА:
{Вставь правила из docs/01_RULES_FOR_AI.md — секции про aiogram handlers}

ТРЕБОВАНИЯ:
1. Все handlers async
2. Использовать Router (не Dispatcher напрямую)
3. Правильные фильтры (Command, F.photo, CallbackQuery)
4. FSM для управления состояниями
5. Type hints
6. Docstrings
7. Логирование важных действий
8. Обработка ошибок с user-friendly сообщениями

CALLBACK DATA FORMAT:
- category:{category_key} - выбор категории
- regenerate:{generation_id} - перегенерация
- download_pdf:{generation_id} - скачать PDF
- feedback:{generation_id}:{rating} - оценка (1=👍, 0=👎)
- buy_package:{package_key} - купить пакет
- cancel - отмена

Создай полный код всех файлов.
```

---

## 📦 КЛЮЧЕВЫЕ ФАЙЛЫ

### bot/states.py

```python
"""
FSM States для управления состояниями диалога.
"""

from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    """Состояния процесса генерации ТЗ."""
    
    waiting_photo = State()       # Ожидание первого фото
    waiting_more_photos = State() # Ожидание дополнительных фото
    waiting_category = State()    # Выбор категории товара
    generating = State()          # Процесс генерации
    waiting_feedback = State()    # Ожидание оценки ТЗ


class PaymentStates(StatesGroup):
    """Состояния процесса оплаты."""
    
    choosing_package = State()    # Выбор пакета
    awaiting_payment = State()    # Ожидание оплаты
```

### bot/keyboards.py

```python
"""
Клавиатуры бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.prompts import CATEGORIES


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Создать ТЗ")],
            [
                KeyboardButton(text="💰 Баланс"),
                KeyboardButton(text="📋 История")
            ],
            [KeyboardButton(text="💳 Купить кредиты")]
        ],
        resize_keyboard=True
    )


def get_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора категории товара."""
    builder = InlineKeyboardBuilder()
    
    for key, data in CATEGORIES.items():
        builder.button(
            text=data["name"],
            callback_data=f"category:{key}"
        )
    
    builder.adjust(2)  # По 2 кнопки в ряд
    return builder.as_markup()


def get_photo_actions_keyboard(photo_count: int) -> InlineKeyboardMarkup:
    """Клавиатура действий после загрузки фото."""
    builder = InlineKeyboardBuilder()
    
    if photo_count < 5:
        builder.button(
            text=f"📷 Добавить ещё фото ({photo_count}/5)",
            callback_data="add_more_photos"
        )
    
    builder.button(
        text="✅ Продолжить",
        callback_data="continue_generation"
    )
    builder.button(
        text="❌ Отмена",
        callback_data="cancel"
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_generation_result_keyboard(generation_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после генерации ТЗ."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="📄 Скачать PDF",
        callback_data=f"download_pdf:{generation_id}"
    )
    builder.button(
        text="🔄 Перегенерировать",
        callback_data=f"regenerate:{generation_id}"
    )
    builder.row()
    builder.button(
        text="👍",
        callback_data=f"feedback:{generation_id}:1"
    )
    builder.button(
        text="👎",
        callback_data=f"feedback:{generation_id}:0"
    )
    
    builder.adjust(2, 2)
    return builder.as_markup()


def get_packages_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пакета."""
    builder = InlineKeyboardBuilder()
    
    packages = [
        ("start", "🔹 Старт: 5 ТЗ за 149₽"),
        ("optimal", "⭐ Оптимальный: 20 ТЗ за 399₽"),
        ("pro", "🚀 Профи: 50 ТЗ за 699₽")
    ]
    
    for key, text in packages:
        builder.button(
            text=text,
            callback_data=f"buy_package:{key}"
        )
    
    builder.button(
        text="❌ Отмена",
        callback_data="cancel"
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура на экране баланса."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="💳 Пополнить баланс",
        callback_data="show_packages"
    )
    builder.button(
        text="📋 История покупок",
        callback_data="payment_history"
    )
    
    builder.adjust(1)
    return builder.as_markup()
```

### bot/handlers/start.py

```python
"""
Обработчики команды /start и базовых команд.
"""

import structlog
from aiogram import Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.keyboards import get_main_keyboard, get_balance_keyboard
from bot.states import GenerationStates
from database import crud
from database.models import User

router = Router(name="start")
logger = structlog.get_logger()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    command: CommandObject,
    user: User,
    is_new_user: bool
) -> None:
    """
    Обработчик команды /start.
    
    Поддерживает deep link для реферальной системы:
    /start ref_123456789
    """
    await state.clear()
    
    # Обработка реферальной ссылки
    if command.args and command.args.startswith("ref_"):
        referrer_id = command.args.replace("ref_", "")
        logger.info(
            "referral_link_used",
            user_id=message.from_user.id,
            referrer_id=referrer_id
        )
    
    # Приветствие
    if is_new_user:
        welcome_text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"Я — <b>ТЗшник</b>, помогу создать техническое задание "
            f"для инфографики твоего товара на Wildberries и Ozon.\n\n"
            f"🎁 <b>Тебе доступно 1 бесплатное ТЗ!</b>\n\n"
            f"📸 Просто отправь фото товара и получи готовое ТЗ за 30 секунд.\n\n"
            f"💰 Твой баланс: <b>{user.balance} ТЗ</b>"
        )
    else:
        welcome_text = (
            f"👋 С возвращением, {message.from_user.first_name}!\n\n"
            f"💰 Твой баланс: <b>{user.balance} ТЗ</b>\n\n"
            f"📸 Отправь фото товара, чтобы создать ТЗ."
        )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    
    logger.info(
        "user_started_bot",
        user_id=message.from_user.id,
        is_new=is_new_user,
        balance=user.balance
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка по командам."""
    help_text = (
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Отправь фото товара (можно до 5 фото)\n"
        "2️⃣ Выбери категорию товара\n"
        "3️⃣ Получи готовое ТЗ!\n\n"
        "📋 <b>Команды:</b>\n"
        "/start — начать сначала\n"
        "/balance — проверить баланс\n"
        "/history — история ТЗ\n"
        "/buy — купить кредиты\n"
        "/help — эта справка\n\n"
        "❓ Вопросы? Пиши @support"
    )
    
    await message.answer(help_text)


@router.message(Command("balance"))
@router.message(F.text == "💰 Баланс")
async def cmd_balance(message: Message, user: User) -> None:
    """Показать баланс пользователя."""
    stats = await crud.get_user_stats(message.from_user.id)
    
    balance_text = (
        f"💰 <b>Твой баланс:</b> {user.balance} ТЗ\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Создано ТЗ: {stats.get('total_generated', 0)}\n"
        f"• За этот месяц: {stats.get('generations_this_month', 0)}\n"
    )
    
    if stats.get('total_spent_rub', 0) > 0:
        balance_text += f"• Потрачено: {stats['total_spent_rub']:.0f}₽\n"
    
    # Расчёт экономии
    saved_hours = stats.get('total_generated', 0) * 2.5
    if saved_hours > 0:
        balance_text += f"\n⏱ Ты сэкономил примерно <b>{saved_hours:.0f} часов</b> работы!"
    
    await message.answer(
        balance_text,
        reply_markup=get_balance_keyboard()
    )


@router.message(Command("history"))
@router.message(F.text == "📋 История")
async def cmd_history(message: Message) -> None:
    """Показать историю генераций."""
    generations = await crud.get_user_generations(
        telegram_id=message.from_user.id,
        limit=5
    )
    
    if not generations:
        await message.answer(
            "📋 У тебя пока нет сгенерированных ТЗ.\n\n"
            "📸 Отправь фото товара, чтобы создать первое!"
        )
        return
    
    history_text = "📋 <b>Последние ТЗ:</b>\n\n"
    
    for i, gen in enumerate(generations, 1):
        date_str = gen.created_at.strftime("%d.%m.%Y %H:%M")
        category = gen.category.capitalize()
        
        history_text += (
            f"{i}. {category} — {date_str}\n"
            f"   Качество: {gen.quality_score}/100\n\n"
        )
    
    await message.answer(history_text)


@router.message(F.text == "📸 Создать ТЗ")
async def start_generation(message: Message, state: FSMContext, user: User) -> None:
    """Начать процесс создания ТЗ."""
    await state.set_state(GenerationStates.waiting_photo)
    await state.update_data(photos=[])
    
    await message.answer(
        "📸 <b>Отправь фото товара</b>\n\n"
        "Можно загрузить от 1 до 5 фото с разных ракурсов.\n"
        "Чем больше фото — тем точнее будет ТЗ!"
    )
```

### bot/handlers/photo.py

```python
"""
Обработчик загрузки фото.
"""

import structlog
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards import get_photo_actions_keyboard, get_category_keyboard
from bot.states import GenerationStates
from bot.config import settings

router = Router(name="photo")
logger = structlog.get_logger()


@router.message(
    GenerationStates.waiting_photo,
    F.photo
)
@router.message(
    GenerationStates.waiting_more_photos,
    F.photo
)
async def handle_photo(message: Message, state: FSMContext) -> None:
    """Обработка загруженного фото."""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    # Проверяем лимит
    if len(photos) >= settings.max_photos:
        await message.answer(
            f"⚠️ Максимум {settings.max_photos} фото.\n"
            "Нажми «Продолжить» для генерации ТЗ."
        )
        return
    
    # Сохраняем фото (берём самое большое разрешение)
    photo = message.photo[-1]
    photos.append({
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id
    })
    
    await state.update_data(photos=photos)
    await state.set_state(GenerationStates.waiting_more_photos)
    
    logger.info(
        "photo_received",
        user_id=message.from_user.id,
        photo_count=len(photos)
    )
    
    await message.answer(
        f"✅ Фото получено! ({len(photos)}/{settings.max_photos})\n\n"
        "Можешь добавить ещё фото или нажми «Продолжить».",
        reply_markup=get_photo_actions_keyboard(len(photos))
    )


@router.callback_query(F.data == "add_more_photos")
async def add_more_photos(callback: CallbackQuery, state: FSMContext) -> None:
    """Пользователь хочет добавить ещё фото."""
    await callback.answer()
    
    data = await state.get_data()
    photo_count = len(data.get("photos", []))
    
    await callback.message.edit_text(
        f"📷 Отправь ещё фото ({photo_count}/{settings.max_photos})"
    )


@router.callback_query(F.data == "continue_generation")
async def continue_to_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Переход к выбору категории."""
    await callback.answer()
    
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await callback.message.edit_text(
            "⚠️ Сначала отправь хотя бы одно фото товара."
        )
        return
    
    await state.set_state(GenerationStates.waiting_category)
    
    await callback.message.edit_text(
        f"📸 Загружено фото: {len(photos)}\n\n"
        "📂 <b>Выбери категорию товара:</b>",
        reply_markup=get_category_keyboard()
    )


@router.message(
    GenerationStates.waiting_photo,
    ~F.photo
)
@router.message(
    GenerationStates.waiting_more_photos,
    ~F.photo
)
async def not_a_photo(message: Message) -> None:
    """Получено не фото."""
    await message.answer(
        "⚠️ Пожалуйста, отправь фото товара.\n"
        "Если хочешь отменить — напиши /cancel"
    )
```

### bot/middleware.py

```python
"""
Middleware для бота.
"""

from typing import Callable, Awaitable, Dict, Any
import structlog

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database import crud
from database.models import User

logger = structlog.get_logger()


class UserMiddleware(BaseMiddleware):
    """
    Middleware для автоматического получения/создания пользователя.
    
    Добавляет в data:
    - user: User — объект пользователя
    - is_new_user: bool — новый ли пользователь
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем telegram_id в зависимости от типа события
        user_data = None
        
        if isinstance(event, Message) and event.from_user:
            user_data = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_data = event.from_user
        
        if user_data:
            # Получаем или создаём пользователя
            user, is_new = await crud.get_or_create_user(
                telegram_id=user_data.id,
                username=user_data.username,
                first_name=user_data.first_name
            )
            
            data["user"] = user
            data["is_new_user"] = is_new
            
            if is_new:
                logger.info(
                    "new_user_registered",
                    telegram_id=user_data.id,
                    username=user_data.username
                )
        
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех событий."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        event_type = type(event).__name__
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            if event.text:
                logger.debug(
                    "message_received",
                    user_id=user_id,
                    text=event.text[:50]
                )
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            logger.debug(
                "callback_received",
                user_id=user_id,
                data=event.data
            )
        
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(
                "handler_error",
                event_type=event_type,
                user_id=user_id,
                error=str(e)
            )
            raise
```

---

## 🔄 ОБНОВЛЕНИЕ main.py

```python
# bot/main.py (обновлённая версия)

async def main() -> None:
    """Главная функция запуска бота."""
    
    setup_logging()
    logger.info("starting_bot", debug=settings.debug)
    
    # Создание директорий
    Path("data").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    
    # Инициализация БД
    from database import init_db
    await init_db()
    logger.info("database_initialized")
    
    # Создание бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Регистрация middleware
    from bot.middleware import UserMiddleware, LoggingMiddleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    
    # Регистрация роутеров
    from bot.handlers import start, photo, generation, common
    dp.include_routers(
        start.router,
        photo.router,
        generation.router,
        common.router
    )
    
    # Запуск
    logger.info("bot_started")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("bot_stopped")
```

---

## ✅ ЧЕКЛИСТ ВЫПОЛНЕНИЯ

- [ ] `bot/states.py` создан с FSM states
- [ ] `bot/keyboards.py` содержит все клавиатуры
- [ ] `bot/middleware.py` работает
- [ ] `/start` регистрирует пользователя
- [ ] Фото принимаются и сохраняются в state
- [ ] Выбор категории работает
- [ ] Бот не падает при ошибках

---

## 🧪 ТЕСТИРОВАНИЕ

1. Запусти бота: `python bot/main.py`
2. Отправь `/start` — должно появиться приветствие
3. Отправь фото — должно сохраниться
4. Нажми "Продолжить" — должен появиться выбор категории
5. Проверь `/balance` и `/history`

---

## ➡️ СЛЕДУЮЩИЙ ШАГ

После успешного выполнения переходи к [STEP_05_GENERATION.md](STEP_05_GENERATION.md)

---

*Шаг 4 из 7*
