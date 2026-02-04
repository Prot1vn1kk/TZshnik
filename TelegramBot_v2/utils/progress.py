"""
Прогресс-бар для генерации ТЗ.

Показывает пользователю текущий этап генерации
с обновлением сообщения в реальном времени.
"""

from typing import Optional, List, Tuple
import random

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest


logger = structlog.get_logger()


# Анимированные иконки для загрузки
LOADING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Мотивационные фразы
MOTIVATION_PHRASES = [
    "Магия AI в действии ✨",
    "Анализирую каждую деталь 🔍",
    "Создаю продающий контент 📈",
    "Работаю над твоим успехом 🚀",
    "Скоро будет готово 🎯",
]


class ProgressTracker:
    """
    Отслеживание и отображение прогресса генерации.
    
    Обновляет сообщение в Telegram с текущим статусом.
    Показывает 4 этапа генерации с визуальной индикацией.
    """
    
    STAGES: List[Tuple[str, str, str]] = [
        ("📷", "Анализ фото", "Распознаю товар и его особенности"),
        ("🎯", "Целевая аудитория", "Определяю, кому продавать"),
        ("✍️", "Генерация текстов", "Пишу продающий контент"),
        ("🔍", "Финальная проверка", "Проверяю качество"),
    ]
    
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        category_name: str = "",
        photo_count: int = 1,
    ):
        """
        Инициализация трекера прогресса.
        
        Args:
            bot: Инстанс бота aiogram
            chat_id: ID чата для обновления
            message_id: ID сообщения для редактирования
            category_name: Название категории товара
            photo_count: Количество фото
        """
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.category_name = category_name
        self.photo_count = photo_count
        self.current_stage = 0
        self.frame_index = 0
    
    async def update(self, stage: int, substage: Optional[str] = None) -> None:
        """
        Обновить прогресс-бар.
        
        Args:
            stage: Номер текущего этапа (0-3)
            substage: Дополнительная информация (например, "попытка 2")
        """
        self.current_stage = stage
        self.frame_index = (self.frame_index + 1) % len(LOADING_FRAMES)
        text = self._build_progress_text(substage)
        
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id,
                parse_mode="HTML",
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку "message is not modified"
            if "message is not modified" not in str(e):
                logger.warning("progress_update_failed", error=str(e))
    
    async def complete(self) -> None:
        """Показать что генерация успешно завершена."""
        progress_bar = "█" * 10
        text = (
            "🎉 <b>ТЗ готово!</b>\n\n"
            f"<code>[{progress_bar}] 100%</code>\n\n"
            "✅ Анализ фото\n"
            "✅ Целевая аудитория\n"
            "✅ Генерация текстов\n"
            "✅ Финальная проверка\n\n"
            "📄 <i>Формирую документ...</i>"
        )
        
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id,
                parse_mode="HTML",
            )
        except TelegramBadRequest:
            pass
    
    async def error(self, message: str) -> None:
        """
        Показать сообщение об ошибке.
        
        Args:
            message: Текст ошибки для отображения
        """
        text = (
            "❌ <b>Упс! Что-то пошло не так</b>\n\n"
            f"⚠️ {message}\n\n"
            "💡 <i>Попробуй ещё раз или обратись в @TZshnik_support_bot</i>"
        )
        
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id,
                parse_mode="HTML",
            )
        except TelegramBadRequest:
            pass
    
    def _build_progress_text(self, substage: Optional[str] = None) -> str:
        """
        Построить текст прогресс-бара.
        
        Args:
            substage: Дополнительная информация о текущем этапе
            
        Returns:
            str: Форматированный текст прогресса
        """
        # Заголовок
        loader = LOADING_FRAMES[self.frame_index]
        lines = [f"🪄 <b>Создаю ТЗ для твоего товара</b> {loader}\n"]
        
        # Прогресс-бар
        progress = (self.current_stage / len(self.STAGES)) * 100
        filled = int(progress / 10)
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        lines.append(f"<code>[{bar}] {int(progress)}%</code>\n")
        
        # Этапы
        for i, (emoji, title, desc) in enumerate(self.STAGES):
            if i < self.current_stage:
                # Завершённый этап
                lines.append(f"✅ <s>{title}</s>")
            elif i == self.current_stage:
                # Текущий этап
                if substage:
                    lines.append(f"🔄 <b>{title}</b> <i>({substage})</i>")
                else:
                    lines.append(f"🔄 <b>{title}</b>")
                lines.append(f"   └ <i>{desc}</i>")
            else:
                # Будущий этап
                lines.append(f"⬜ {title}")
        
        # Оценка времени и мотивация
        remaining = (len(self.STAGES) - self.current_stage) * 8
        phrase = random.choice(MOTIVATION_PHRASES)
        
        if remaining > 0:
            lines.append(f"\n⏱ <i>~{remaining} сек · {phrase}</i>")
        else:
            lines.append(f"\n✨ <i>Почти готово! {phrase}</i>")
        
        return "\n".join(lines)


async def create_progress_message(
    bot: Bot,
    chat_id: int,
    category_name: str,
    photo_count: int,
) -> ProgressTracker:
    """
    Создать сообщение прогресса и вернуть трекер.
    
    Удобная функция для начала отслеживания.
    
    Args:
        bot: Инстанс бота
        chat_id: ID чата
        category_name: Название категории
        photo_count: Количество фото
        
    Returns:
        ProgressTracker: Готовый трекер для обновления
    """
    # Начальный прогресс-бар
    bar = "░" * 10
    loader = LOADING_FRAMES[0]
    
    initial_text = (
        f"🪄 <b>Создаю ТЗ для твоего товара</b> {loader}\n\n"
        f"<code>[{bar}] 0%</code>\n\n"
        f"📷 Фото: <b>{photo_count} шт.</b>\n"
        f"📁 Категория: <b>{category_name}</b>\n\n"
        f"🔄 <b>Анализ фото</b>\n"
        f"   └ <i>Распознаю товар и его особенности</i>\n"
        f"⬜ Целевая аудитория\n"
        f"⬜ Генерация текстов\n"
        f"⬜ Финальная проверка\n\n"
        f"⏱ <i>~30 сек · Магия AI в действии ✨</i>"
    )
    
    message = await bot.send_message(
        chat_id=chat_id,
        text=initial_text,
        parse_mode="HTML",
    )
    
    tracker = ProgressTracker(
        bot=bot,
        chat_id=chat_id,
        message_id=message.message_id,
        category_name=category_name,
        photo_count=photo_count,
    )
    
    return tracker
