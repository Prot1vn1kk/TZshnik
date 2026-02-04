"""
Обработчики генерации ТЗ.

Содержит:
- Выбор категории
- Запуск генерации с прогресс-баром
- Callback-и результата (PDF, регенерация, фидбек)
"""

from typing import List

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
import structlog

from database import (
    create_generation,
    decrease_balance,
    increase_balance,
    get_generation_by_id,
    create_feedback,
)
from database.crud import update_generation_tz
from database.models import User
from bot.keyboards import (
    get_main_keyboard,
    get_generation_result_keyboard,
    get_after_feedback_keyboard,
    CATEGORY_BUTTONS,
)
from bot.states import GenerationStates
from core.exceptions import GenerationError
from core.generator import GenerationResult, create_generator
from utils.progress import ProgressTracker


logger = structlog.get_logger()
router = Router(name="generation")


# ============================================================
# КОНСТАНТЫ
# ============================================================

MAX_MESSAGE_LENGTH = 4000  # Telegram лимит 4096, оставляем запас для заголовков и эмодзи
PREVIEW_LENGTH = 1000  # Длина превью


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы Markdown для безопасной отправки в Telegram.
    
    Args:
        text: Текст для экранирования
        
    Returns:
        str: Экранированный текст
    """
    # Экранируем специальные Markdown символы
    escape_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text


def clean_markdown_for_telegram(text: str) -> str:
    """
    Очищает текст от markdown-разметки для отправки в Telegram без parse_mode.
    Преобразует markdown в читаемый plaintext.
    
    Args:
        text: Текст с markdown-разметкой
        
    Returns:
        str: Очищенный текст без спецсимволов **
    """
    import re
    
    # Убираем markdown заголовки (## Заголовок -> Заголовок)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Убираем bold/italic маркеры
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold** -> bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)       # *italic* -> italic
    text = re.sub(r'__(.+?)__', r'\1', text)       # __bold__ -> bold
    text = re.sub(r'_(.+?)_', r'\1', text)         # _italic_ -> italic
    
    # Убираем ссылки [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Убираем code блоки
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Убираем горизонтальные линии
    text = re.sub(r'^---+$', '━━━━━━━━━━━━━━━━━━━━━', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*\*+$', '━━━━━━━━━━━━━━━━━━━━━', text, flags=re.MULTILINE)
    
    # Преобразуем markdown списки в простые списки
    text = re.sub(r'^[-*+]\s+', '• ', text, flags=re.MULTILINE)
    
    return text.strip()


def remove_intro_message(text: str) -> str:
    """
    Удаляет вводное сообщение ИИ типа "Вот полное техническое задание...".
    
    Args:
        text: Текст ТЗ с возможным вводным сообщением
        
    Returns:
        str: Текст без вводного сообщения
    """
    import re
    
    # Паттерны вводных сообщений которые нужно удалить
    intro_patterns = [
        r'^Вот\s+(?:полное\s+)?техническое\s+задание[^\n]*\n+',
        r'^Готово[!.]?\s+(?:Вот\s+)?[^\n]*техническое\s+задание[^\n]*\n+',
        r'^Ниже\s+(?:представлено\s+)?(?:полное\s+)?(?:техническое\s+)?задание[^\n]*\n+',
        r'^Техническое\s+задание\s+для\s+создания\s+инфографики[^\n]*\n+',
        r'^Предлагаю\s+(?:вам\s+)?(?:полное\s+)?техническое\s+задание[^\n]*\n+',
        r'^Создаю\s+(?:для\s+вас\s+)?техническое\s+задание[^\n]*\n+',
    ]
    
    for pattern in intro_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    return text.strip()


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Разбивает длинное сообщение на части.
    
    Пытается разбить по абзацам, секциям, иначе по max_length.
    Гарантирует, что весь текст будет включён.
    
    Args:
        text: Текст для разбивки
        max_length: Максимальная длина части
        
    Returns:
        List[str]: Список частей
    """
    if not text:
        return []
    
    if len(text) <= max_length:
        return [text]
    
    parts = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_length:
            # Оставшийся текст помещается целиком
            parts.append(remaining.strip())
            break
        
        # Ищем лучшее место для разрыва в пределах max_length
        chunk = remaining[:max_length]
        split_pos = -1
        
        # Приоритет 1: разбить по двойному переносу строки (новый параграф)
        split_pos = chunk.rfind("\n\n")
        
        # Приоритет 2: разбить по разделителю секции
        if split_pos == -1 or split_pos < max_length // 3:
            section_pos = chunk.rfind("━━━━━")
            if section_pos > max_length // 3:
                split_pos = section_pos
        
        # Приоритет 3: разбить по одиночному переносу строки
        if split_pos == -1 or split_pos < max_length // 3:
            newline_pos = chunk.rfind("\n")
            if newline_pos > max_length // 3:
                split_pos = newline_pos
        
        # Приоритет 4: разбить по точке с пробелом (конец предложения)
        if split_pos == -1 or split_pos < max_length // 3:
            sentence_pos = chunk.rfind(". ")
            if sentence_pos > max_length // 3:
                split_pos = sentence_pos + 1  # Включаем точку
        
        # Приоритет 5: разбить по пробелу (не разрываем слова)
        if split_pos == -1 or split_pos < max_length // 3:
            space_pos = chunk.rfind(" ")
            if space_pos > max_length // 3:
                split_pos = space_pos
        
        # Крайний случай - жёсткий разрыв по max_length
        if split_pos == -1 or split_pos < max_length // 4:
            split_pos = max_length
        
        # Добавляем часть
        part = remaining[:split_pos].strip()
        if part:
            parts.append(part)
        
        # Продолжаем с оставшимся текстом
        remaining = remaining[split_pos:].strip()
    
    return parts


async def send_tz_result(
    bot,
    chat_id: int,
    tz_text: str,
    category_name: str,
    quality_score: int,
    generation_id: int,
) -> None:
    """
    Отправляет результат ТЗ пользователю.
    Разбивает длинный текст на несколько сообщений.
    Очищает markdown-разметку для корректного отображения.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        tz_text: Текст ТЗ
        category_name: Название категории
        quality_score: Оценка качества (не отображается пользователю)
        generation_id: ID генерации
    """
    import asyncio
    from bot.keyboards import get_generation_result_keyboard
    
    # Удаляем вводное сообщение ИИ
    clean_text = remove_intro_message(tz_text)
    
    # Очищаем от markdown-разметки
    clean_text = clean_markdown_for_telegram(clean_text)
    
    # Логируем длину исходного и очищенного текста
    logger.info(
        "Preparing TZ for sending",
        generation_id=generation_id,
        original_length=len(tz_text),
        clean_length=len(clean_text),
    )
    
    # Проверяем что текст не пустой
    if not clean_text:
        logger.error("Empty TZ text after cleaning", generation_id=generation_id)
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при обработке ТЗ. Попробуйте перегенерировать.",
            reply_markup=get_generation_result_keyboard(generation_id),
        )
        return
    
    # Заголовок для первой части
    header = (
        f"✅ ТЗ успешно создано!\n\n"
        f"📁 Категория: {category_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Рассчитываем максимальную длину для контента (учитываем заголовок и индикатор части)
    content_max_length = MAX_MESSAGE_LENGTH - len(header) - 50  # 50 символов на индикаторы частей
    
    # Разбиваем на части
    parts = split_message(clean_text, content_max_length)
    
    # Проверяем что части не пустые
    parts = [p for p in parts if p.strip()]
    
    if not parts:
        logger.error("No parts after splitting", generation_id=generation_id)
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при обработке ТЗ. Попробуйте перегенерировать.",
            reply_markup=get_generation_result_keyboard(generation_id),
        )
        return
    
    logger.info(
        "TZ split into parts",
        generation_id=generation_id,
        parts_count=len(parts),
        parts_lengths=[len(p) for p in parts],
    )
    
    try:
        if len(parts) == 1:
            # Один кусок - отправляем всё сразу
            full_text = header + clean_text
            
            # Проверяем финальную длину
            if len(full_text) > 4096:
                logger.warning(
                    "Single part too long, re-splitting",
                    generation_id=generation_id,
                    length=len(full_text),
                )
                # Пересплитим с меньшим лимитом
                parts = split_message(clean_text, 3500)
                parts = [p for p in parts if p.strip()]
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=full_text,
                    reply_markup=get_generation_result_keyboard(generation_id),
                )
                return
        
        # Много частей - отправляем по очереди с небольшой задержкой
        total_parts = len(parts)
        
        for i, part in enumerate(parts):
            try:
                if i == 0:
                    text = header + part
                    if total_parts > 1:
                        text += f"\n\n📄 Часть 1/{total_parts} ➡️"
                elif i == total_parts - 1:
                    text = f"📄 Часть {i+1}/{total_parts} (финал)\n━━━━━━━━━━━━━━━━━━━━━\n\n{part}"
                else:
                    text = f"📄 Часть {i+1}/{total_parts} ➡️\n\n{part}"
                
                # Обрезаем если всё ещё слишком длинное
                if len(text) > 4096:
                    text = text[:4090] + "..."
                    logger.warning(
                        "Part truncated",
                        generation_id=generation_id,
                        part_num=i+1,
                        original_length=len(text),
                    )
                
                # Последняя часть с клавиатурой
                if i == total_parts - 1:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=get_generation_result_keyboard(generation_id),
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                    )
                    # Небольшая задержка между сообщениями чтобы не словить rate limit
                    await asyncio.sleep(0.3)
                    
            except Exception as e:
                logger.error(
                    "Failed to send TZ part",
                    generation_id=generation_id,
                    part_num=i+1,
                    error=str(e),
                )
                
    except Exception as e:
        logger.error(
            "Failed to send TZ result",
            generation_id=generation_id,
            error=str(e),
        )
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при отправке ТЗ. Ваше ТЗ сохранено, попробуйте скачать PDF.",
            reply_markup=get_generation_result_keyboard(generation_id),
        )


# ============================================================
# ОБРАБОТЧИКИ ВЫБОРА КАТЕГОРИИ
# ============================================================

@router.callback_query(GenerationStates.waiting_category, F.data.startswith("category:"))
async def callback_category_selected(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    user: User,
) -> None:
    """
    Обработка выбора категории.
    
    Запускает генерацию ТЗ с прогресс-баром после выбора категории.
    """
    await callback.answer()
    
    # Извлекаем категорию
    if not callback.data:
        await callback.answer("Ошибка", show_alert=True)
        return
    category = callback.data.split(":")[1]
    category_name = CATEGORY_BUTTONS.get(category, category)
    
    # Получаем фото из состояния
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await callback.message.edit_text("❌ Фотографии не найдены. Начните заново.")
        await state.clear()
        return
    
    # Проверяем баланс
    if user.balance <= 0:
        await callback.message.edit_text(
            "❌ *Недостаточно кредитов!*\n\n"
            "Пополните баланс, чтобы создавать ТЗ.",
            parse_mode="Markdown",
        )
        await state.clear()
        return
    
    # Переходим в состояние генерации
    await state.set_state(GenerationStates.generating)
    
    logger.info(
        "Starting generation",
        telegram_id=callback.from_user.id if callback.from_user else 0,
        category=category,
        photo_count=len(photos),
    )
    
    telegram_id = callback.from_user.id if callback.from_user else 0
    
    # Создаём прогресс-бар
    progress = ProgressTracker(
        bot=bot,
        chat_id=callback.message.chat.id if callback.message else 0,
        message_id=callback.message.message_id if callback.message else 0,
    )
    
    # Списываем кредит
    credit_deducted = await decrease_balance(telegram_id, 1)
    if not credit_deducted:
        if callback.message:
            await callback.message.edit_text("❌ Ошибка списания кредита")
        await state.clear()
        return
    
    generation_id = None
    
    try:
        # Создаём генератор
        generator = create_generator()
        
        # Callback для обновления прогресса
        async def progress_callback(stage: int, substage: str | None = None) -> None:
            await progress.update(stage, substage)
        
        # Запускаем генерацию
        # Извлекаем байты из фото перед передачей в генератор
        photo_bytes_list = [photo_dict["bytes"] for photo_dict in photos]
        result: GenerationResult = await generator.generate(
            photos=photo_bytes_list,
            category=category,
            progress_callback=progress_callback,
        )
        
        if not result.success:
            raise GenerationError(result.error_message or "Generation failed")
        
        # Получаем file_id из фото
        photo_file_ids = [
            (p.get("file_id", ""), p.get("file_unique_id", ""))
            for p in photos
        ]
        
        # Сохраняем результат в БД
        generation = await create_generation(
            user_id=user.id,
            category=category,
            photo_analysis=result.photo_analysis or "",
            tz_text=result.tz_text,
            quality_score=result.quality_score,
            photo_file_ids=photo_file_ids,
        )
        generation_id = generation.id
        
        # Показываем завершение
        await progress.complete()
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем результат с разбиением на части и без markdown
        if callback.message:
            await send_tz_result(
                bot=bot,
                chat_id=callback.message.chat.id,
                tz_text=result.tz_text,
                category_name=category_name,
                quality_score=result.quality_score,
                generation_id=generation_id,
            )
        
        logger.info(
            "Generation completed",
            generation_id=generation_id,
            quality_score=result.quality_score,
        )
        
    except Exception as e:
        # Возвращаем кредит при ошибке
        await increase_balance(telegram_id, 1)
        
        await state.clear()
        await progress.error(str(e)[:200])
        
        logger.error("Generation failed", error=str(e))


# ============================================================
# CALLBACK ОБРАБОТЧИКИ РЕЗУЛЬТАТА
# ============================================================

@router.callback_query(F.data.startswith("download_pdf:"))
async def callback_download_pdf(
    callback: CallbackQuery,
) -> None:
    """Скачивание PDF с ТЗ."""
    await callback.answer("Генерирую PDF...")
    
    if not callback.data:
        await callback.answer("Ошибка", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[1])
    generation = await get_generation_by_id(generation_id)
    
    if not generation or not generation.tz_text:
        await callback.answer("ТЗ не найдено", show_alert=True)
        return
    
    try:
        from utils.pdf_export import export_generation_to_pdf
        
        # Генерируем PDF
        pdf_content = await export_generation_to_pdf(
            tz_text=generation.tz_text,
            category=generation.category or "other",
            generation_id=generation_id,
            created_at=generation.created_at,
        )
        
        filename = f"TZ_{generation_id}_{generation.category}.pdf"
        
        if callback.message:
            await callback.message.answer_document(
                document=BufferedInputFile(pdf_content, filename=filename),
                caption=f"📄 Техническое задание #{generation_id}",
            )
        
        logger.info(
            "PDF downloaded",
            generation_id=generation_id,
            user_id=callback.from_user.id if callback.from_user else 0,
        )
        
    except Exception as e:
        logger.error("PDF generation failed", error=str(e))
        await callback.answer("Ошибка при создании файла", show_alert=True)


@router.callback_query(F.data.startswith("regenerate:"))
async def callback_regenerate(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    user: User,
) -> None:
    """Перегенерация ТЗ с использованием сохранённого анализа."""
    if not callback.data:
        await callback.answer("Ошибка", show_alert=True)
        return
    
    generation_id = int(callback.data.split(":")[1])
    generation = await get_generation_by_id(generation_id)
    
    if not generation:
        await callback.answer("ТЗ не найдено", show_alert=True)
        return
    
    # Проверяем баланс
    if user.balance <= 0:
        await callback.answer("Недостаточно кредитов для перегенерации!", show_alert=True)
        return
    
    await callback.answer()
    
    telegram_id = callback.from_user.id if callback.from_user else 0
    
    # Создаём прогресс-бар
    progress = ProgressTracker(
        bot=bot,
        chat_id=callback.message.chat.id if callback.message else 0,
        message_id=callback.message.message_id if callback.message else 0,
    )
    
    # Списываем кредит
    credit_deducted = await decrease_balance(telegram_id, 1)
    if not credit_deducted:
        await callback.answer("Ошибка списания кредита", show_alert=True)
        return
    
    try:
        # Создаём генератор
        generator = create_generator()
        
        # Callback для прогресса
        async def progress_callback(stage: int, substage: str | None = None) -> None:
            await progress.update(stage, substage)
        
        # Перегенерируем (используем сохранённый анализ)
        result = await generator.regenerate(
            photo_analysis=generation.photo_analysis or "",
            category=generation.category or "other",
            previous_tz=generation.tz_text or "",
            progress_callback=progress_callback,
        )
        
        if not result.success:
            raise GenerationError(result.error_message or "Regeneration failed")
        
        # Обновляем в БД
        await update_generation_tz(
            generation_id=generation_id,
            tz_text=result.tz_text,
            quality_score=result.quality_score,
        )
        
        await progress.complete()
        
        # Получаем название категории
        category_name = CATEGORY_BUTTONS.get(generation.category or "other", generation.category or "Другое")
        
        # Отправляем результат с разбиением и без markdown
        if callback.message:
            await send_tz_result(
                bot=bot,
                chat_id=callback.message.chat.id,
                tz_text=result.tz_text,
                category_name=f"{category_name} (перегенерация)",
                quality_score=result.quality_score,
                generation_id=generation_id,
            )
        
        logger.info(
            "Regeneration completed",
            generation_id=generation_id,
            quality_score=result.quality_score,
        )
        
    except Exception as e:
        # Возвращаем кредит
        await increase_balance(telegram_id, 1)
        
        await progress.error(str(e)[:200])
        logger.error("Regeneration failed", error=str(e))


@router.callback_query(F.data.startswith("feedback:"))
async def callback_feedback(
    callback: CallbackQuery,
    user: User,
) -> None:
    """Обработка фидбека (лайк/дизлайк)."""
    if not callback.data:
        await callback.answer("Ошибка", show_alert=True)
        return
    
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Неверный формат", show_alert=True)
        return
        
    generation_id = int(parts[1])
    is_positive = parts[2] == "1"
    
    try:
        # Сохраняем фидбек
        await create_feedback(
            generation_id=generation_id,
            user_id=user.id,
            rating=1 if is_positive else 0,
        )
        
        emoji = "👍" if is_positive else "👎"
        await callback.answer(f"Спасибо за отзыв! {emoji}")
        
        # Обновляем клавиатуру (убираем кнопки оценки)
        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=get_after_feedback_keyboard(generation_id),
            )
        
        logger.info(
            "Feedback received",
            generation_id=generation_id,
            is_positive=is_positive,
        )
        
    except Exception as e:
        logger.error("Feedback save failed", error=str(e))
        await callback.answer("Ошибка сохранения отзыва")


@router.callback_query(F.data == "new_generation")
async def callback_new_generation(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
) -> None:
    """Начать новую генерацию."""
    await callback.answer()
    
    # Проверяем баланс
    if user.balance <= 0:
        if callback.message:
            await callback.message.answer(
                "❌ *У вас закончились кредиты!*\n\n"
                "Нажмите 💳 *Купить кредиты* для пополнения.",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown",
            )
        return
    
    # Переводим в режим ожидания фото
    await state.set_state(GenerationStates.waiting_photo)
    await state.update_data(photos=[])
    
    if callback.message:
        await callback.message.answer(
            "📷 *Отправьте фото товара*\n\n"
            "Вы можете отправить от 1 до 5 фотографий.",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )
