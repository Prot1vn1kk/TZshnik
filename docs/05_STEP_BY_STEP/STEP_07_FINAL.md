# 🏁 ШАГ 7: ФИНАЛИЗАЦИЯ И PDF ЭКСПОРТ

> Финальная сборка, PDF экспорт, тестирование и деплой

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать:
- PDF экспорт ТЗ
- Финальную сборку main.py
- Команды администратора
- Healthcheck эндпоинт
- Инструкции по деплою

---

## 📁 СТРУКТУРА ФАЙЛОВ (ФИНАЛЬНАЯ)

```
tzshnik_bot/
├── main.py                  # Точка входа
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   ├── settings.py          # Конфигурация
│   └── packages.py          # Пакеты кредитов
│
├── core/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── prompts.py
│   ├── validator.py
│   ├── generator.py
│   └── ai_providers/
│       ├── __init__.py
│       ├── base.py
│       ├── glm.py
│       ├── gemini.py
│       └── chain.py
│
├── database/
│   ├── __init__.py
│   ├── models.py
│   ├── crud.py
│   └── tzshnik.db           # SQLite база
│
├── bot/
│   ├── __init__.py
│   ├── states.py
│   ├── keyboards.py
│   ├── middleware.py
│   └── handlers/
│       ├── __init__.py
│       ├── start.py
│       ├── photo.py
│       ├── generation.py
│       ├── payments.py
│       ├── history.py
│       └── admin.py
│
├── utils/
│   ├── __init__.py
│   ├── progress.py
│   └── pdf_export.py        # PDF экспорт
│
└── docs/                    # Эта документация
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай финальные модули для Telegram-бота ТЗшник.

ЗАДАЧА 1: PDF ЭКСПОРТ

Создай utils/pdf_export.py:
- Класс PDFExporter:
  * async export_tz(tz_text, category, generation_id) -> bytes
  * Форматирование заголовков и текста
  * Добавление логотипа (опционально)
  * Добавление футера с датой
- Использовать библиотеку FPDF2
- Поддержка русского языка (шрифт DejaVu)

Формат PDF:
- Заголовок: "Техническое задание №{id}"
- Подзаголовок: "Категория: {category}"
- Основной текст с форматированием
- Футер: "Создано в ТЗшник • {дата}"

ЗАДАЧА 2: ИСТОРИЯ

Создай bot/handlers/history.py:
- Callback "history" — показать последние 5 генераций
- Кнопка под каждой: "📄 Открыть" → показать ТЗ
- Кнопка "📥 Скачать PDF"
- Если истории нет — показать приглашение

ЗАДАЧА 3: АДМИН КОМАНДЫ

Создай bot/handlers/admin.py:
- /stats — статистика бота (только для админов)
  * Всего пользователей
  * Генераций сегодня/всего
  * Платежей сегодня/всего
  * Сумма платежей
- /broadcast {текст} — рассылка всем (только для админов)
- Проверка admin_ids из settings

ЗАДАЧА 4: ФИНАЛЬНЫЙ main.py

Обнови main.py для продакшена:
- Graceful shutdown
- Сигналы SIGINT, SIGTERM
- Логирование startup/shutdown
- Healthcheck через aiohttp (опционально)

ПРАВИЛА:
{Правила из docs/01_RULES_FOR_AI.md}

ТРЕБОВАНИЯ:
1. PDF должен корректно отображать кириллицу
2. История с пагинацией (по 5 штук)
3. Админ команды только для ADMIN_IDS
4. Graceful shutdown при CTRL+C

Создай полный код всех файлов.
```

---

## 📦 КЛЮЧЕВЫЕ ФАЙЛЫ

### utils/pdf_export.py

```python
"""
PDF экспорт технических заданий.
"""

import io
from datetime import datetime
from typing import Optional
import structlog

from fpdf import FPDF

logger = structlog.get_logger()

# Категории на русском
CATEGORY_NAMES = {
    "electronics": "Электроника",
    "clothing": "Одежда и обувь",
    "beauty": "Красота и здоровье",
    "home": "Дом и сад",
    "kids": "Детские товары",
    "food": "Продукты питания",
    "sport": "Спорт и отдых",
    "auto": "Авто и мото",
    "other": "Другое"
}


class PDFExporter:
    """
    Экспорт ТЗ в PDF формат.
    
    Использует FPDF2 с поддержкой Unicode (кириллица).
    """
    
    # Путь к шрифту DejaVu (поддерживает кириллицу)
    # Скачай: https://dejavu-fonts.github.io/
    FONT_PATH = "assets/fonts/DejaVuSans.ttf"
    FONT_BOLD_PATH = "assets/fonts/DejaVuSans-Bold.ttf"
    
    def __init__(self):
        self._font_loaded = False
    
    async def export_tz(
        self,
        tz_text: str,
        category: str,
        generation_id: int,
        created_at: Optional[datetime] = None
    ) -> bytes:
        """
        Экспортировать ТЗ в PDF.
        
        Args:
            tz_text: Текст технического задания
            category: Категория товара
            generation_id: ID генерации
            created_at: Дата создания
            
        Returns:
            bytes: PDF файл
        """
        if created_at is None:
            created_at = datetime.now()
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Добавляем шрифт с поддержкой кириллицы
        try:
            pdf.add_font("DejaVu", "", self.FONT_PATH, uni=True)
            pdf.add_font("DejaVu", "B", self.FONT_BOLD_PATH, uni=True)
            font_name = "DejaVu"
        except Exception as e:
            # Фолбек на встроенный шрифт (без кириллицы)
            logger.warning("font_load_failed", error=str(e))
            font_name = "Helvetica"
        
        pdf.add_page()
        
        # Заголовок
        pdf.set_font(font_name, "B", 16)
        pdf.cell(0, 10, f"Техническое задание №{generation_id}", ln=True, align="C")
        
        # Категория
        category_name = CATEGORY_NAMES.get(category, category)
        pdf.set_font(font_name, "", 12)
        pdf.cell(0, 8, f"Категория: {category_name}", ln=True, align="C")
        
        # Дата
        pdf.set_font(font_name, "", 10)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 6, f"Дата создания: {created_at.strftime('%d.%m.%Y %H:%M')}", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        
        # Разделитель
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Основной текст
        pdf.set_font(font_name, "", 11)
        
        # Парсим текст по секциям
        lines = tz_text.split("\n")
        for line in lines:
            line = line.strip()
            
            if not line:
                pdf.ln(3)
                continue
            
            # Заголовки секций
            if line.startswith("## "):
                pdf.ln(5)
                pdf.set_font(font_name, "B", 13)
                pdf.multi_cell(0, 7, line[3:])
                pdf.set_font(font_name, "", 11)
            elif line.startswith("### "):
                pdf.ln(3)
                pdf.set_font(font_name, "B", 12)
                pdf.multi_cell(0, 6, line[4:])
                pdf.set_font(font_name, "", 11)
            elif line.startswith("**") and line.endswith("**"):
                pdf.set_font(font_name, "B", 11)
                pdf.multi_cell(0, 6, line[2:-2])
                pdf.set_font(font_name, "", 11)
            elif line.startswith("- ") or line.startswith("• "):
                pdf.multi_cell(0, 6, f"  • {line[2:]}")
            else:
                pdf.multi_cell(0, 6, line)
        
        # Футер
        pdf.ln(10)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, "Создано в ТЗшник — генератор ТЗ для маркетплейсов", align="C")
        
        # Сохраняем в bytes
        output = io.BytesIO()
        pdf.output(output)
        return output.getvalue()


# Синглтон экспортера
pdf_exporter = PDFExporter()


async def export_generation_to_pdf(
    tz_text: str,
    category: str,
    generation_id: int,
    created_at: Optional[datetime] = None
) -> bytes:
    """
    Функция-обёртка для экспорта в PDF.
    
    Использование:
        pdf_bytes = await export_generation_to_pdf(tz_text, category, gen_id)
    """
    return await pdf_exporter.export_tz(
        tz_text=tz_text,
        category=category,
        generation_id=generation_id,
        created_at=created_at
    )
```

### bot/handlers/history.py

```python
"""
Обработчик истории генераций.
"""

import structlog
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile

from database import crud
from database.models import User
from utils.pdf_export import export_generation_to_pdf
from bot.keyboards import get_generation_result_keyboard

router = Router(name="history")
logger = structlog.get_logger()

# Сколько показывать на странице
PAGE_SIZE = 5


@router.callback_query(F.data == "history")
async def show_history(callback: CallbackQuery, user: User) -> None:
    """Показать историю генераций пользователя."""
    await callback.answer()
    
    generations = await crud.get_user_generations(
        user_id=user.id,
        limit=PAGE_SIZE
    )
    
    if not generations:
        await callback.message.edit_text(
            "📭 <b>История пуста</b>\n\n"
            "Ты ещё не создавал ТЗ.\n\n"
            "📷 Загрузи фото товара и создай своё первое ТЗ!",
            reply_markup=get_upload_keyboard()
        )
        return
    
    text = "📜 <b>История генераций</b>\n\n"
    
    for gen in generations:
        category_emoji = get_category_emoji(gen.category)
        date_str = gen.created_at.strftime("%d.%m.%Y")
        
        text += (
            f"{category_emoji} <b>ТЗ #{gen.id}</b> — {date_str}\n"
            f"   Качество: {gen.quality_score}/100\n\n"
        )
    
    text += f"\n📊 Всего создано: {user.total_generated} ТЗ"
    
    # Создаём клавиатуру с кнопками для каждой генерации
    keyboard = get_history_keyboard(generations)
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("view_tz:"))
async def view_generation(callback: CallbackQuery, user: User) -> None:
    """Показать конкретное ТЗ из истории."""
    await callback.answer()
    
    generation_id = int(callback.data.split(":")[1])
    
    generation = await crud.get_generation_by_id(generation_id)
    
    if not generation or generation.user_id != user.id:
        await callback.message.edit_text("⚠️ ТЗ не найдено")
        return
    
    # Разбиваем текст если длинный
    tz_text = generation.tz_text
    
    if len(tz_text) > 3500:
        # Отправляем несколько сообщений
        parts = split_text(tz_text, 3500)
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                await callback.message.answer(
                    part,
                    reply_markup=get_generation_result_keyboard(generation.id)
                )
            else:
                await callback.message.answer(part)
    else:
        await callback.message.answer(
            tz_text,
            reply_markup=get_generation_result_keyboard(generation.id)
        )


@router.callback_query(F.data.startswith("download_pdf:"))
async def download_pdf(callback: CallbackQuery, user: User) -> None:
    """Скачать ТЗ в формате PDF."""
    await callback.answer("📄 Готовлю PDF...")
    
    generation_id = int(callback.data.split(":")[1])
    
    generation = await crud.get_generation_by_id(generation_id)
    
    if not generation or generation.user_id != user.id:
        await callback.message.answer("⚠️ ТЗ не найдено")
        return
    
    try:
        # Генерируем PDF
        pdf_bytes = await export_generation_to_pdf(
            tz_text=generation.tz_text,
            category=generation.category,
            generation_id=generation.id,
            created_at=generation.created_at
        )
        
        # Отправляем как документ
        filename = f"TZ_{generation.id}_{generation.category}.pdf"
        
        await callback.message.answer_document(
            document=BufferedInputFile(pdf_bytes, filename=filename),
            caption=(
                f"📄 <b>Техническое задание №{generation.id}</b>\n\n"
                f"Категория: {generation.category}\n"
                f"Качество: {generation.quality_score}/100"
            )
        )
        
        logger.info(
            "pdf_exported",
            user_id=user.id,
            generation_id=generation.id
        )
        
    except Exception as e:
        logger.error("pdf_export_error", error=str(e))
        await callback.message.answer(
            "⚠️ Ошибка при создании PDF. Попробуй позже."
        )


# Вспомогательные функции

def get_category_emoji(category: str) -> str:
    """Получить эмодзи для категории."""
    emojis = {
        "electronics": "📱",
        "clothing": "👕",
        "beauty": "💄",
        "home": "🏠",
        "kids": "🧸",
        "food": "🍎",
        "sport": "⚽",
        "auto": "🚗",
        "other": "📦"
    }
    return emojis.get(category, "📦")


def split_text(text: str, max_length: int) -> list[str]:
    """Разбить текст на части."""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current = ""
    
    for line in text.split("\n"):
        if len(current) + len(line) + 1 <= max_length:
            current += ("\n" if current else "") + line
        else:
            if current:
                parts.append(current)
            current = line
    
    if current:
        parts.append(current)
    
    return parts


def get_history_keyboard(generations):
    """Создать клавиатуру с кнопками генераций."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    
    for gen in generations:
        emoji = get_category_emoji(gen.category)
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} ТЗ #{gen.id}",
                callback_data=f"view_tz:{gen.id}"
            ),
            InlineKeyboardButton(
                text="📥 PDF",
                callback_data=f"download_pdf:{gen.id}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="main_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_upload_keyboard():
    """Клавиатура с кнопкой загрузки."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📷 Загрузить фото",
                    callback_data="upload_photo"
                )
            ]
        ]
    )
```

### bot/handlers/admin.py

```python
"""
Административные команды бота.
"""

from datetime import datetime, timedelta
import structlog
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config.settings import settings
from database import crud

router = Router(name="admin")
logger = structlog.get_logger()


def is_admin(user_id: int) -> bool:
    """Проверить является ли пользователь админом."""
    return user_id in settings.admin_ids


@router.message(Command("stats"))
async def admin_stats(message: Message) -> None:
    """Показать статистику бота (только для админов)."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return
    
    logger.info("admin_stats_requested", admin_id=message.from_user.id)
    
    # Собираем статистику
    stats = await crud.get_bot_statistics()
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        
        f"👥 <b>Пользователи</b>\n"
        f"• Всего: {stats['total_users']}\n"
        f"• За сегодня: {stats['users_today']}\n"
        f"• За неделю: {stats['users_week']}\n\n"
        
        f"📝 <b>Генерации</b>\n"
        f"• Всего: {stats['total_generations']}\n"
        f"• За сегодня: {stats['generations_today']}\n"
        f"• За неделю: {stats['generations_week']}\n"
        f"• Ср. качество: {stats['avg_quality_score']}/100\n\n"
        
        f"💰 <b>Платежи</b>\n"
        f"• Всего: {stats['total_payments']} шт\n"
        f"• За сегодня: {stats['payments_today']} шт\n"
        f"• Сумма всего: {stats['total_revenue']:,.0f}₽\n"
        f"• Сумма сегодня: {stats['revenue_today']:,.0f}₽\n\n"
        
        f"📈 <b>Конверсия</b>\n"
        f"• Платящих: {stats['paying_users']} ({stats['paying_rate']:.1f}%)\n"
        f"• ARPU: {stats['arpu']:.0f}₽\n\n"
        
        f"<i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    )
    
    await message.answer(text)


@router.message(Command("broadcast"))
async def admin_broadcast(message: Message) -> None:
    """Рассылка всем пользователям (только для админов)."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return
    
    # Получаем текст рассылки
    broadcast_text = message.text.replace("/broadcast", "").strip()
    
    if not broadcast_text:
        await message.answer(
            "📢 <b>Рассылка</b>\n\n"
            "Использование:\n"
            "/broadcast Текст сообщения\n\n"
            "Можно использовать HTML форматирование."
        )
        return
    
    logger.info(
        "broadcast_started",
        admin_id=message.from_user.id,
        text_length=len(broadcast_text)
    )
    
    # Получаем всех пользователей
    users = await crud.get_all_users()
    
    sent = 0
    failed = 0
    
    progress_msg = await message.answer(
        f"📢 Начинаю рассылку {len(users)} пользователям..."
    )
    
    from aiogram import Bot
    bot = Bot.get_current()
    
    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=broadcast_text
            )
            sent += 1
        except Exception as e:
            logger.warning(
                "broadcast_send_failed",
                user_id=user.telegram_id,
                error=str(e)
            )
            failed += 1
        
        # Обновляем прогресс каждые 50 сообщений
        if (sent + failed) % 50 == 0:
            try:
                await progress_msg.edit_text(
                    f"📢 Рассылка: {sent + failed}/{len(users)}..."
                )
            except:
                pass
    
    await progress_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    
    logger.info(
        "broadcast_completed",
        sent=sent,
        failed=failed
    )


@router.message(Command("user"))
async def admin_user_info(message: Message) -> None:
    """Информация о пользователе (только для админов)."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return
    
    # Получаем ID или username
    args = message.text.replace("/user", "").strip()
    
    if not args:
        await message.answer(
            "👤 <b>Информация о пользователе</b>\n\n"
            "Использование:\n"
            "/user 123456789 (telegram_id)\n"
            "/user @username"
        )
        return
    
    # Ищем пользователя
    if args.startswith("@"):
        user = await crud.get_user_by_username(args[1:])
    else:
        try:
            telegram_id = int(args)
            user = await crud.get_user_by_telegram_id(telegram_id)
        except ValueError:
            await message.answer("⚠️ Некорректный ID")
            return
    
    if not user:
        await message.answer("⚠️ Пользователь не найден")
        return
    
    # Получаем статистику пользователя
    generations = await crud.get_user_generations(user.id, limit=3)
    payments = await crud.get_user_payments(user.id, limit=3)
    
    text = (
        f"👤 <b>Пользователь #{user.id}</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Имя: {user.full_name or 'нет'}\n\n"
        
        f"💰 Баланс: {user.balance} кредитов\n"
        f"📝 Генераций: {user.total_generated}\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
    )
    
    if generations:
        text += "<b>Последние ТЗ:</b>\n"
        for gen in generations:
            text += f"• #{gen.id} ({gen.category}) — {gen.quality_score}/100\n"
        text += "\n"
    
    if payments:
        text += "<b>Последние платежи:</b>\n"
        for pay in payments:
            text += f"• {pay.amount}₽ — {pay.created_at.strftime('%d.%m')}\n"
    
    await message.answer(text)
```

### database/crud.py (дополнения для статистики)

```python
# Добавить функцию статистики:

async def get_bot_statistics() -> dict:
    """Получить статистику бота для админа."""
    from datetime import datetime, timedelta
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    
    async with async_session() as session:
        # Пользователи
        total_users = await session.scalar(
            select(func.count(User.id))
        )
        
        users_today = await session.scalar(
            select(func.count(User.id))
            .filter(User.created_at >= today)
        )
        
        users_week = await session.scalar(
            select(func.count(User.id))
            .filter(User.created_at >= week_ago)
        )
        
        # Генерации
        total_generations = await session.scalar(
            select(func.count(Generation.id))
        )
        
        generations_today = await session.scalar(
            select(func.count(Generation.id))
            .filter(Generation.created_at >= today)
        )
        
        generations_week = await session.scalar(
            select(func.count(Generation.id))
            .filter(Generation.created_at >= week_ago)
        )
        
        avg_quality = await session.scalar(
            select(func.avg(Generation.quality_score))
        ) or 0
        
        # Платежи
        total_payments = await session.scalar(
            select(func.count(Payment.id))
        )
        
        payments_today = await session.scalar(
            select(func.count(Payment.id))
            .filter(Payment.created_at >= today)
        )
        
        total_revenue = await session.scalar(
            select(func.sum(Payment.amount))
        ) or 0
        
        revenue_today = await session.scalar(
            select(func.sum(Payment.amount))
            .filter(Payment.created_at >= today)
        ) or 0
        
        # Платящие
        paying_users = await session.scalar(
            select(func.count(func.distinct(Payment.user_id)))
        )
        
        paying_rate = (paying_users / total_users * 100) if total_users > 0 else 0
        arpu = (total_revenue / total_users) if total_users > 0 else 0
        
        return {
            "total_users": total_users,
            "users_today": users_today,
            "users_week": users_week,
            "total_generations": total_generations,
            "generations_today": generations_today,
            "generations_week": generations_week,
            "avg_quality_score": round(avg_quality),
            "total_payments": total_payments,
            "payments_today": payments_today,
            "total_revenue": total_revenue,
            "revenue_today": revenue_today,
            "paying_users": paying_users,
            "paying_rate": paying_rate,
            "arpu": arpu
        }


async def get_all_users() -> list[User]:
    """Получить всех пользователей для рассылки."""
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()
```

### main.py (финальная версия)

```python
"""
ТЗшник — Telegram бот для генерации технических заданий.

Точка входа приложения.
"""

import asyncio
import signal
import sys
import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import settings
from database import init_database
from bot.middleware import UserMiddleware, LoggingMiddleware
from bot.handlers import (
    start,
    photo,
    generation,
    payments,
    history,
    admin
)

# Настраиваем логирование
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger()


async def main():
    """Главная функция запуска бота."""
    logger.info(
        "starting_bot",
        environment="development" if settings.debug else "production"
    )
    
    # Инициализируем базу данных
    await init_database()
    logger.info("database_initialized")
    
    # Создаём бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )
    
    # Создаём диспетчер
    dp = Dispatcher()
    
    # Регистрируем middleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    
    # Регистрируем роутеры (порядок важен!)
    dp.include_router(admin.router)      # Админ команды первыми
    dp.include_router(start.router)      # /start, /help
    dp.include_router(payments.router)   # Платежи
    dp.include_router(photo.router)      # Загрузка фото
    dp.include_router(generation.router) # Генерация ТЗ
    dp.include_router(history.router)    # История
    
    logger.info("handlers_registered")
    
    # Graceful shutdown
    shutdown_event = asyncio.Event()
    
    def shutdown_handler(sig):
        logger.info("shutdown_signal_received", signal=sig.name)
        shutdown_event.set()
    
    # Регистрируем обработчики сигналов
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: shutdown_handler(s)
            )
    
    try:
        # Удаляем вебхук если был
        await bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("bot_started", username=(await bot.me()).username)
        
        # Запускаем polling
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
                "pre_checkout_query"
            ]
        )
        
    except asyncio.CancelledError:
        logger.info("bot_cancelled")
    except Exception as e:
        logger.error("bot_error", error=str(e))
        raise
    finally:
        # Закрываем соединения
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
```

---

## 📋 ФИНАЛЬНЫЙ requirements.txt

```
aiogram==3.13.0
aiosqlite==0.19.0
sqlalchemy[asyncio]==2.0.23
httpx==0.27.0
pydantic-settings==2.1.0
structlog==23.3.0
fpdf2==2.7.6
python-dotenv==1.0.0
```

---

## 🚀 ДЕПЛОЙ

### Вариант 1: Простой VPS

```bash
# 1. Подключаемся к серверу
ssh user@your-server

# 2. Клонируем репозиторий
git clone https://github.com/you/tzshnik-bot.git
cd tzshnik-bot

# 3. Создаём виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate

# 4. Устанавливаем зависимости
pip install -r requirements.txt

# 5. Копируем .env
cp .env.example .env
nano .env  # Заполняем токены

# 6. Запускаем
python main.py

# 7. Для фонового запуска используем screen или systemd
screen -S tzbot
python main.py
# Ctrl+A, D для выхода
```

### Вариант 2: Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

```bash
docker build -t tzshnik-bot .
docker run -d --env-file .env --name tzbot tzshnik-bot
```

### Вариант 3: Railway/Render/Fly.io

1. Подключи GitHub репозиторий
2. Добавь переменные окружения
3. Деплой автоматически

---

## ✅ ФИНАЛЬНЫЙ ЧЕКЛИСТ

### Перед запуском:

- [ ] `.env` заполнен всеми токенами
- [ ] Шрифт DejaVu скачан в `assets/fonts/`
- [ ] База данных создаётся без ошибок
- [ ] Тестовый платёж проходит

### Тестирование:

- [ ] /start работает
- [ ] Загрузка 1-5 фото работает
- [ ] Категории отображаются
- [ ] Генерация с прогресс-баром работает
- [ ] ТЗ сохраняется в историю
- [ ] PDF экспорт работает
- [ ] Платёж проходит (TEST токен)
- [ ] Кредиты начисляются
- [ ] /stats для админов работает

### Продакшен:

- [ ] Заменить TEST токен на LIVE
- [ ] Настроить мониторинг
- [ ] Настроить бэкапы БД
- [ ] Добавить Sentry для ошибок

---

## 🎉 ПОЗДРАВЛЯЮ!

Ты создал полноценного бота ТЗшник!

**Что он умеет:**
- ✅ Анализировать 1-5 фото товара
- ✅ Генерировать ТЗ для 9 категорий
- ✅ Показывать прогресс в реальном времени
- ✅ Валидировать качество ТЗ
- ✅ Принимать оплату через YooKassa
- ✅ Экспортировать в PDF
- ✅ Хранить историю

**Что дальше:**
- Добавить реферальную систему
- Добавить подписную модель
- Интегрировать A/B тестирование
- Добавить шаблоны для дизайнеров

---

*Шаг 7 из 7 — ФИНАЛ! 🏆*
