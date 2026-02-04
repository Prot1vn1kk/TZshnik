"""
Обработчики для работы с фотографиями.

Содержит:
- Приём фото от пользователя
- Валидация и скачивание
- Управление списком фото (добавить ещё / продолжить)
"""

from typing import List, Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
import structlog

from database.models import User
from bot.keyboards import get_photo_actions_keyboard, get_category_keyboard, get_main_keyboard
from bot.states import GenerationStates


logger = structlog.get_logger()
router = Router(name="photo")


# ============================================================
# КОНСТАНТЫ
# ============================================================

MAX_PHOTOS = 5  # Максимум фото для одной генерации


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

async def download_photo(bot: Bot, photo: PhotoSize) -> Optional[bytes]:
    """
    Скачивает фото из Telegram.
    
    Args:
        bot: Экземпляр бота
        photo: Объект PhotoSize (лучшее качество)
        
    Returns:
        bytes: Бинарные данные фото или None при ошибке
    """
    file = await bot.get_file(photo.file_id)
    if not file.file_path:
        return None
    file_bytes = await bot.download_file(file.file_path)
    if file_bytes is None:
        return None
    return file_bytes.read()


def get_best_photo(photos: Optional[List[PhotoSize]]) -> Optional[PhotoSize]:
    """
    Выбирает фото с лучшим качеством из списка.
    
    Telegram присылает несколько версий фото в разных разрешениях.
    Выбираем последнюю (самое высокое разрешение).
    
    Args:
        photos: Список PhotoSize из сообщения
        
    Returns:
        PhotoSize: Фото с максимальным разрешением или None
    """
    if not photos:
        return None
    return max(photos, key=lambda p: p.width * p.height)


# ============================================================
# ОБРАБОТЧИКИ ФОТО
# ============================================================

@router.message(GenerationStates.waiting_photo, F.photo)
async def handle_first_photo(
    message: Message,
    bot: Bot,
    state: FSMContext,
    user: User,
) -> None:
    """
    Обработка первого фото от пользователя.
    
    Скачивает фото и предлагает добавить ещё или продолжить.
    """
    # Получаем лучшее качество
    photo = get_best_photo(message.photo)
    if not photo:
        await message.answer("❌ Не удалось получить фото. Попробуйте ещё раз.")
        return
    
    # Скачиваем фото
    try:
        photo_bytes = await download_photo(bot, photo)
        if not photo_bytes:
            raise ValueError("Empty photo data")
    except Exception as e:
        logger.error("Failed to download photo", error=str(e))
        await message.answer(
            "❌ Не удалось загрузить фото. Попробуйте ещё раз.",
        )
        return
    
    # Сохраняем в состояние (включая file_id для записи в БД)
    data = await state.get_data()
    photos: List[dict] = data.get("photos", [])
    photos.append({
        "bytes": photo_bytes,
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
    })
    
    await state.update_data(photos=photos)
    await state.set_state(GenerationStates.waiting_more_photos)
    
    logger.info(
        "Photo received",
        telegram_id=message.from_user.id if message.from_user else 0,
        photo_count=len(photos),
        photo_size=len(photo_bytes),
    )
    
    # Показываем опции
    await message.answer(
        f"✅ *Фото загружено!* ({len(photos)}/{MAX_PHOTOS})\n\n"
        "Вы можете добавить ещё фото или продолжить.",
        reply_markup=get_photo_actions_keyboard(len(photos)),
        parse_mode="Markdown",
    )


@router.message(GenerationStates.waiting_more_photos, F.photo)
async def handle_additional_photo(
    message: Message,
    bot: Bot,
    state: FSMContext,
) -> None:
    """
    Обработка дополнительных фото.
    
    Добавляет фото к списку, проверяет лимит.
    """
    data = await state.get_data()
    photos: List[dict] = data.get("photos", [])
    
    # Проверяем лимит
    if len(photos) >= MAX_PHOTOS:
        await message.answer(
            f"⚠️ *Достигнут лимит в {MAX_PHOTOS} фото!*\n\n"
            "Нажмите «Продолжить» для выбора категории.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="Markdown",
        )
        return
    
    # Скачиваем фото
    photo = get_best_photo(message.photo)
    if not photo:
        await message.answer("❌ Не удалось получить фото.")
        return
    
    try:
        photo_bytes = await download_photo(bot, photo)
        if not photo_bytes:
            raise ValueError("Empty photo data")
    except Exception as e:
        logger.error("Failed to download additional photo", error=str(e))
        await message.answer(
            "❌ Не удалось загрузить фото. Попробуйте ещё раз.",
        )
        return
    
    # Добавляем в список
    photos.append({
        "bytes": photo_bytes,
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
    })
    await state.update_data(photos=photos)
    
    logger.info(
        "Additional photo received",
        telegram_id=message.from_user.id if message.from_user else 0,
        photo_count=len(photos),
    )
    
    # Обновляем сообщение
    if len(photos) >= MAX_PHOTOS:
        await message.answer(
            f"✅ *Загружено {len(photos)}/{MAX_PHOTOS} фото* (максимум)\n\n"
            "Нажмите «Продолжить» для выбора категории.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            f"✅ *Фото добавлено!* ({len(photos)}/{MAX_PHOTOS})\n\n"
            "Добавьте ещё или продолжите.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="Markdown",
        )


# ============================================================
# CALLBACK ОБРАБОТЧИКИ
# ============================================================

@router.callback_query(GenerationStates.waiting_more_photos, F.data == "add_more_photos")
async def callback_add_more(callback: CallbackQuery) -> None:
    """Кнопка "Добавить ещё фото"."""
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "📷 *Отправьте ещё фото товара*\n\n"
            "Покажите товар с разных сторон для лучшего результата.",
            parse_mode="Markdown",
        )


@router.callback_query(GenerationStates.waiting_more_photos, F.data == "continue_generation")
async def callback_continue(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Кнопка "Продолжить" - переход к выбору категории.
    
    Проверяет что есть хотя бы одно фото.
    """
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await callback.answer("❌ Сначала загрузите хотя бы одно фото!", show_alert=True)
        return
    
    await callback.answer()
    
    # Переходим к выбору категории
    await state.set_state(GenerationStates.waiting_category)
    
    if callback.message:
        await callback.message.edit_text(
            f"📸 *Загружено фото: {len(photos)}*\n\n"
            "Выберите категорию товара:",
            reply_markup=get_category_keyboard(),
            parse_mode="Markdown",
        )
    
    logger.info(
        "Photos confirmed, waiting for category",
        telegram_id=callback.from_user.id if callback.from_user else 0,
        photo_count=len(photos),
    )


@router.callback_query(F.data == "cancel")
async def callback_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Отмена текущего действия."""
    current_state = await state.get_state()
    
    if current_state:
        await state.clear()
        await callback.answer("Действие отменено")
        if callback.message:
            await callback.message.edit_text("❌ Генерация отменена.")
            await callback.message.answer(
                "Нажмите 📸 *Создать ТЗ*, чтобы начать заново.",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown",
            )
    else:
        await callback.answer("Нечего отменять")


# ============================================================
# ОБРАБОТЧИКИ ОШИБОК ВВОДА
# ============================================================

@router.message(GenerationStates.waiting_photo, ~F.photo)
async def handle_not_photo_first(message: Message) -> None:
    """Если вместо первого фото пришло что-то другое."""
    await message.answer(
        "📷 Пожалуйста, отправьте *фото* товара.\n\n"
        "Поддерживаются только изображения.",
        parse_mode="Markdown",
    )


@router.message(GenerationStates.waiting_more_photos, ~F.photo)
async def handle_not_photo_more(
    message: Message,
    state: FSMContext,
) -> None:
    """Если вместо дополнительного фото пришло что-то другое."""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    await message.answer(
        f"📷 Отправьте *фото* или нажмите кнопку ниже.\n\n"
        f"Загружено: {len(photos)}/{MAX_PHOTOS}",
        reply_markup=get_photo_actions_keyboard(len(photos)),
        parse_mode="Markdown",
    )
