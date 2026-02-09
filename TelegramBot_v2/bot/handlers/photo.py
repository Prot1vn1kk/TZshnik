"""
Обработчики для работы с фотографиями.

Содержит:
- Приём фото от пользователя (включая альбомы/медиагруппы)
- Валидация форматов (только .jpeg и .png)
- Сохранение во временную папку
- Подтверждение и удаление загруженных фото
- Управление списком фото (добавить ещё / продолжить)
"""

from typing import List, Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PhotoSize, Document
from aiogram.fsm.context import FSMContext
import structlog

from database.models import User
from bot.keyboards import (
    get_photo_actions_keyboard,
    get_photo_confirmation_keyboard,
    get_photo_delete_keyboard,
    get_category_keyboard,
    get_main_menu_keyboard,
)
from bot.states import GenerationStates
from utils.temp_files import (
    TempPhoto,
    save_temp_photo,
    delete_temp_photo,
    clear_user_temp_files,
    read_temp_photo,
    ALLOWED_EXTENSIONS,
)
from config.constants import MAX_PHOTOS_PER_GENERATION as MAX_PHOTOS


logger = structlog.get_logger()
router = Router(name="photo")


# ============================================================
# КОНСТАНТЫ
# ============================================================

# Сообщения для пользователя
INVALID_FORMAT_MESSAGE = (
    "⚠️ <b>Неподдерживаемый формат!</b>\n\n"
    "Допустимые форматы: <b>JPEG</b> и <b>PNG</b>\n\n"
    "Пожалуйста, отправьте изображение в правильном формате."
)

PHOTO_UPLOAD_PROMPT = (
    "📷 <b>Отправьте фото товара</b>\n\n"
    "• Поддерживаемые форматы: JPEG, PNG\n"
    "• Можно отправить до 5 фото\n"
    "• Для лучшего результата покажите товар с разных сторон"
)


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
    try:
        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            return None
        file_bytes = await bot.download_file(file.file_path)
        if file_bytes is None:
            return None
        return file_bytes.read()
    except Exception as e:
        logger.error("photo_download_failed", error=str(e))
        return None


async def download_document(bot: Bot, document: Document) -> Optional[bytes]:
    """
    Скачивает документ (файл) из Telegram.
    
    Args:
        bot: Экземпляр бота
        document: Объект Document
        
    Returns:
        bytes: Бинарные данные файла или None при ошибке
    """
    try:
        file = await bot.get_file(document.file_id)
        if not file.file_path:
            return None
        file_bytes = await bot.download_file(file.file_path)
        if file_bytes is None:
            return None
        return file_bytes.read()
    except Exception as e:
        logger.error("document_download_failed", error=str(e))
        return None


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


def get_photos_from_state(data: dict) -> List[TempPhoto]:
    """
    Извлекает список TempPhoto из FSM state data.
    
    Args:
        data: Данные из state.get_data()
        
    Returns:
        Список TempPhoto объектов
    """
    photos_data = data.get("photos", [])
    photos = [TempPhoto.from_dict(p) for p in photos_data]
    return normalize_photo_orders(photos)


def photos_to_state(photos: List[TempPhoto]) -> List[dict]:
    """
    Конвертирует список TempPhoto в формат для FSM state.
    
    Args:
        photos: Список TempPhoto объектов
        
    Returns:
        Список словарей для сохранения в state
    """
    return [p.to_dict() for p in photos]


def normalize_photo_orders(photos: List[TempPhoto]) -> List[TempPhoto]:
    """
    Устанавливает порядковые номера, если они отсутствуют.
    """
    if not photos:
        return photos

    if any(p.order == 0 for p in photos):
        for idx, photo in enumerate(photos, 1):
            if photo.order == 0:
                photo.order = idx

    return photos


def get_next_photo_order(photos: List[TempPhoto]) -> int:
    """
    Возвращает следующий стабильный номер для нового фото.
    """
    if not photos:
        return 1

    max_order = max((p.order or 0) for p in photos)
    return max_order + 1


async def process_and_save_photo(
    bot: Bot,
    user_id: int,
    photo: PhotoSize,
    existing_photos: List[TempPhoto],
) -> tuple[Optional[TempPhoto], str]:
    """
    Обрабатывает и сохраняет одно фото.
    
    Args:
        bot: Экземпляр бота
        user_id: Telegram ID пользователя
        photo: Объект PhotoSize
        existing_photos: Уже загруженные фото
        
    Returns:
        Tuple[TempPhoto или None, сообщение об ошибке]
    """
    # Проверяем лимит
    if len(existing_photos) >= MAX_PHOTOS:
        return None, f"Достигнут лимит в {MAX_PHOTOS} фото"
    
    # Скачиваем фото
    photo_bytes = await download_photo(bot, photo)
    if not photo_bytes:
        return None, "Не удалось загрузить фото"
    
    # Сохраняем во временную папку (валидация формата внутри)
    temp_photo, error = save_temp_photo(
        user_id=user_id,
        file_bytes=photo_bytes,
        mime_type="image/jpeg",  # Telegram всегда отправляет JPEG для сжатых фото
    )
    
    return temp_photo, error


async def process_album_photos(
    bot: Bot,
    user_id: int,
    album: List[Message],
    existing_photos: List[TempPhoto],
) -> tuple[List[TempPhoto], int, int]:
    """
    Обрабатывает альбом фотографий.
    
    Args:
        bot: Экземпляр бота
        user_id: Telegram ID пользователя
        album: Список сообщений с фото
        existing_photos: Уже загруженные фото
        
    Returns:
        tuple: (обновлённый список фото, успешно загружено, ошибок)
    """
    photos = existing_photos.copy()
    success_count = 0
    error_count = 0
    
    for msg in album:
        # Проверяем лимит
        if len(photos) >= MAX_PHOTOS:
            break
            
        if not msg.photo:
            continue
            
        photo = get_best_photo(msg.photo)
        if not photo:
            error_count += 1
            continue
        
        temp_photo, error = await process_and_save_photo(
            bot, user_id, photo, photos
        )
        
        if temp_photo:
            temp_photo.order = get_next_photo_order(photos)
            photos.append(temp_photo)
            success_count += 1
        else:
            error_count += 1
            logger.warning("album_photo_failed", user_id=user_id, error=error)
    
    return photos, success_count, error_count


def format_confirmation_message(photo_count: int) -> str:
    """
    Формирует сообщение подтверждения загруженных фото (без списка файлов).
    
    Args:
        photo_count: Количество фото
        
    Returns:
        Форматированное сообщение
    """
    plural = "фото" if photo_count in [1, 5] else "фотографии" if photo_count < 5 else "фото"
    
    return (
        f"📸 <b>Вы загрузили {photo_count} {plural}</b>\n\n"
        f"Посмотрите превью выше 👆 (номер соответствует подписи на фото)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Если вы случайно добавили лишний файл — нажмите <b>«Удалить»</b>\n"
        "Если всё верно — нажмите <b>«Подтвердить»</b>"
    )


# ============================================================
# ОБРАБОТЧИКИ ФОТО (сжатые изображения)
# ============================================================

@router.message(GenerationStates.waiting_photo, F.photo)
async def handle_first_photo(
    message: Message,
    bot: Bot,
    state: FSMContext,
    user: User,
    album: Optional[List[Message]] = None,
    is_album: bool = False,
) -> None:
    """
    Обработка первого фото от пользователя.
    
    Поддерживает как одиночные фото, так и альбомы (медиагруппы).
    """
    user_id = message.from_user.id if message.from_user else 0
    
    # Очищаем предыдущие временные файлы
    clear_user_temp_files(user_id)
    
    data = await state.get_data()
    existing_photos = get_photos_from_state(data)
    
    # Если это альбом - обрабатываем все фото сразу
    if is_album and album:
        photos, success_count, error_count = await process_album_photos(
            bot, user_id, album, existing_photos
        )
        
        if success_count == 0:
            await message.answer(
                "❌ Не удалось загрузить фотографии. Попробуйте ещё раз.",
                parse_mode="HTML",
            )
            return
        
        await state.update_data(photos=photos_to_state(photos))
        await state.set_state(GenerationStates.waiting_more_photos)
        
        logger.info(
            "album_photos_received",
            telegram_id=user_id,
            album_size=len(album),
            success=success_count,
            errors=error_count,
            total_photos=len(photos),
        )
        
        # Формируем сообщение
        status = f"✅ <b>Загружено {success_count} фото!</b>"
        if error_count > 0:
            status += f" (⚠️ {error_count} не удалось загрузить)"
        
        if len(photos) >= MAX_PHOTOS:
            await message.answer(
                f"{status} ({len(photos)}/{MAX_PHOTOS} — максимум)\n\n"
                "Нажмите «Готово» для проверки файлов.",
                reply_markup=get_photo_actions_keyboard(len(photos)),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"{status} ({len(photos)}/{MAX_PHOTOS})\n\n"
                "Вы можете добавить ещё фото или проверить загруженные.",
                reply_markup=get_photo_actions_keyboard(len(photos)),
                parse_mode="HTML",
            )
        return
    
    # Одиночное фото
    photo = get_best_photo(message.photo)
    if not photo:
        await message.answer("❌ Не удалось получить фото. Попробуйте ещё раз.")
        return
    
    temp_photo, error = await process_and_save_photo(
        bot, user_id, photo, existing_photos
    )
    
    if not temp_photo:
        await message.answer(
            f"❌ {error or 'Не удалось загрузить фото'}. Попробуйте ещё раз.",
            parse_mode="HTML",
        )
        return
    
    temp_photo.order = get_next_photo_order(existing_photos)
    photos = existing_photos + [temp_photo]
    await state.update_data(photos=photos_to_state(photos))
    await state.set_state(GenerationStates.waiting_more_photos)
    
    logger.info(
        "photo_received",
        telegram_id=user_id,
        photo_count=len(photos),
        filename=temp_photo.filename,
    )
    
    await message.answer(
        f"✅ <b>Фото загружено!</b> ({len(photos)}/{MAX_PHOTOS})\n\n"
        "Вы можете добавить ещё фото или проверить загруженные.",
        reply_markup=get_photo_actions_keyboard(len(photos)),
        parse_mode="HTML",
    )


@router.message(GenerationStates.waiting_more_photos, F.photo)
async def handle_additional_photo(
    message: Message,
    bot: Bot,
    state: FSMContext,
    album: Optional[List[Message]] = None,
    is_album: bool = False,
) -> None:
    """
    Обработка дополнительных фото.
    
    Поддерживает как одиночные фото, так и альбомы.
    """
    user_id = message.from_user.id if message.from_user else 0
    data = await state.get_data()
    existing_photos = get_photos_from_state(data)
    
    # Проверяем лимит
    if len(existing_photos) >= MAX_PHOTOS:
        await message.answer(
            f"⚠️ <b>Достигнут лимит в {MAX_PHOTOS} фото!</b>\n\n"
            "Нажмите «Готово» для проверки файлов.",
            reply_markup=get_photo_actions_keyboard(len(existing_photos)),
            parse_mode="HTML",
        )
        return
    
    # Если это альбом - обрабатываем все фото сразу
    if is_album and album:
        photos, success_count, error_count = await process_album_photos(
            bot, user_id, album, existing_photos
        )
        
        if success_count == 0:
            await message.answer(
                "❌ Не удалось загрузить фотографии.\n\n"
                f"Загружено: {len(existing_photos)}/{MAX_PHOTOS}",
                reply_markup=get_photo_actions_keyboard(len(existing_photos)),
                parse_mode="HTML",
            )
            return
        
        await state.update_data(photos=photos_to_state(photos))
        
        logger.info(
            "additional_album_received",
            telegram_id=user_id,
            album_size=len(album),
            success=success_count,
            total_photos=len(photos),
        )
        
        if len(photos) >= MAX_PHOTOS:
            await message.answer(
                f"✅ <b>Загружено {len(photos)}/{MAX_PHOTOS} фото</b> (максимум)\n\n"
                "Нажмите «Готово» для проверки файлов.",
                reply_markup=get_photo_actions_keyboard(len(photos)),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"✅ <b>Добавлено {success_count} фото!</b> ({len(photos)}/{MAX_PHOTOS})\n\n"
                "Добавьте ещё или проверьте загруженные.",
                reply_markup=get_photo_actions_keyboard(len(photos)),
                parse_mode="HTML",
            )
        return
    
    # Одиночное фото
    photo = get_best_photo(message.photo)
    if not photo:
        await message.answer("❌ Не удалось получить фото.")
        return
    
    temp_photo, error = await process_and_save_photo(
        bot, user_id, photo, existing_photos
    )
    
    if not temp_photo:
        await message.answer(
            f"❌ {error or 'Не удалось загрузить фото'}. Попробуйте ещё раз.",
            parse_mode="HTML",
        )
        return
    
    temp_photo.order = get_next_photo_order(existing_photos)
    photos = existing_photos + [temp_photo]
    await state.update_data(photos=photos_to_state(photos))
    
    logger.info(
        "additional_photo_received",
        telegram_id=user_id,
        photo_count=len(photos),
    )
    
    if len(photos) >= MAX_PHOTOS:
        await message.answer(
            f"✅ <b>Загружено {len(photos)}/{MAX_PHOTOS} фото</b> (максимум)\n\n"
            "Нажмите «Готово» для проверки файлов.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"✅ <b>Фото добавлено!</b> ({len(photos)}/{MAX_PHOTOS})\n\n"
            "Добавьте ещё или проверьте загруженные.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="HTML",
        )


# ============================================================
# ОБРАБОТЧИКИ ДОКУМЕНТОВ (для PNG без сжатия)
# ============================================================

@router.message(GenerationStates.waiting_photo, F.document)
async def handle_first_document(
    message: Message,
    bot: Bot,
    state: FSMContext,
    user: User,
) -> None:
    """
    Обработка первого фото как документа.
    
    Позволяет загружать PNG без сжатия.
    """
    document = message.document
    if not document:
        return
    
    user_id = message.from_user.id if message.from_user else 0
    
    # Проверяем MIME-type
    mime_type = document.mime_type or ""
    if mime_type not in ("image/jpeg", "image/png"):
        # Проверяем расширение файла
        filename = document.file_name or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext not in ("jpeg", "jpg", "png"):
            await message.answer(INVALID_FORMAT_MESSAGE, parse_mode="HTML")
            return
    
    # Очищаем предыдущие временные файлы
    clear_user_temp_files(user_id)
    
    # Скачиваем документ
    file_bytes = await download_document(bot, document)
    if not file_bytes:
        await message.answer("❌ Не удалось загрузить файл. Попробуйте ещё раз.")
        return
    
    # Сохраняем
    temp_photo, error = save_temp_photo(
        user_id=user_id,
        file_bytes=file_bytes,
        original_filename=document.file_name,
        mime_type=mime_type,
    )
    
    if not temp_photo:
        if "Неподдерживаемый формат" in error:
            await message.answer(INVALID_FORMAT_MESSAGE, parse_mode="HTML")
        else:
            await message.answer(f"❌ {error}")
        return
    
    temp_photo.order = 1
    await state.update_data(photos=photos_to_state([temp_photo]))
    await state.set_state(GenerationStates.waiting_more_photos)
    
    logger.info(
        "document_photo_received",
        telegram_id=user_id,
        filename=temp_photo.filename,
        format=temp_photo.format_display,
    )
    
    await message.answer(
        f"✅ <b>Файл загружен!</b> (1/{MAX_PHOTOS})\n\n"
        f"📄 <code>{temp_photo.filename}</code>\n\n"
        "Вы можете добавить ещё фото или проверить загруженные.",
        reply_markup=get_photo_actions_keyboard(1),
        parse_mode="HTML",
    )


@router.message(GenerationStates.waiting_more_photos, F.document)
async def handle_additional_document(
    message: Message,
    bot: Bot,
    state: FSMContext,
) -> None:
    """
    Обработка дополнительного фото как документа.
    """
    document = message.document
    if not document:
        return
    
    user_id = message.from_user.id if message.from_user else 0
    data = await state.get_data()
    existing_photos = get_photos_from_state(data)
    
    # Проверяем лимит
    if len(existing_photos) >= MAX_PHOTOS:
        await message.answer(
            f"⚠️ <b>Достигнут лимит в {MAX_PHOTOS} фото!</b>\n\n"
            "Нажмите «Готово» для проверки файлов.",
            reply_markup=get_photo_actions_keyboard(len(existing_photos)),
            parse_mode="HTML",
        )
        return
    
    # Проверяем MIME-type
    mime_type = document.mime_type or ""
    if mime_type not in ("image/jpeg", "image/png"):
        filename = document.file_name or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext not in ("jpeg", "jpg", "png"):
            await message.answer(INVALID_FORMAT_MESSAGE, parse_mode="HTML")
            return
    
    # Скачиваем и сохраняем
    file_bytes = await download_document(bot, document)
    if not file_bytes:
        await message.answer("❌ Не удалось загрузить файл. Попробуйте ещё раз.")
        return
    
    temp_photo, error = save_temp_photo(
        user_id=user_id,
        file_bytes=file_bytes,
        original_filename=document.file_name,
        mime_type=mime_type,
    )
    
    if not temp_photo:
        if "Неподдерживаемый формат" in error:
            await message.answer(INVALID_FORMAT_MESSAGE, parse_mode="HTML")
        else:
            await message.answer(f"❌ {error}")
        return
    
    temp_photo.order = get_next_photo_order(existing_photos)
    photos = existing_photos + [temp_photo]
    await state.update_data(photos=photos_to_state(photos))
    
    logger.info(
        "additional_document_received",
        telegram_id=user_id,
        photo_count=len(photos),
        filename=temp_photo.filename,
    )
    
    if len(photos) >= MAX_PHOTOS:
        await message.answer(
            f"✅ <b>Загружено {len(photos)}/{MAX_PHOTOS} фото</b> (максимум)\n\n"
            "Нажмите «Готово» для проверки файлов.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"✅ <b>Файл добавлен!</b> ({len(photos)}/{MAX_PHOTOS})\n\n"
            "Добавьте ещё или проверьте загруженные.",
            reply_markup=get_photo_actions_keyboard(len(photos)),
            parse_mode="HTML",
        )


# ============================================================
# CALLBACK ОБРАБОТЧИКИ - ПОДТВЕРЖДЕНИЕ И УДАЛЕНИЕ
# ============================================================

@router.callback_query(GenerationStates.waiting_more_photos, F.data == "add_more_photos")
async def callback_add_more(callback: CallbackQuery) -> None:
    """Кнопка "Добавить ещё фото"."""
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "📷 <b>Отправьте ещё фото товара</b>\n\n"
            "Покажите товар с разных сторон для лучшего результата.\n\n"
            "Поддерживаемые форматы: <b>JPEG</b>, <b>PNG</b>",
            parse_mode="HTML",
        )


@router.callback_query(GenerationStates.waiting_more_photos, F.data == "confirm_photos")
async def callback_confirm_photos(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    """
    Кнопка "Готово — проверить файлы".
    
    Показывает превью загруженных фото с номерами.
    """
    data = await state.get_data()
    photos = get_photos_from_state(data)
    photos_sorted = sorted(photos, key=lambda p: p.order or 0)
    
    if not photos:
        await callback.answer("❌ Сначала загрузите хотя бы одно фото!", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(GenerationStates.confirming_photos)
    
    # Отправляем превью каждого фото с номером
    for i, photo in enumerate(photos_sorted, 1):
        try:
            photo_bytes = read_temp_photo(photo.path)
            if photo_bytes:
                from aiogram.types import BufferedInputFile
                order_num = photo.order or i
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=BufferedInputFile(photo_bytes, filename=f"photo_{i}.jpg"),
                    caption=f"📷 <b>Фото #{order_num}</b> (по порядку отправки)",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error("photo_preview_failed", photo_id=photo.id, error=str(e))
    
    # Отправляем сообщение с кнопками подтверждения
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=format_confirmation_message(len(photos)),
        reply_markup=get_photo_confirmation_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(GenerationStates.confirming_photos, F.data == "delete_photos_menu")
async def callback_delete_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Показать меню выбора фото для удаления.
    """
    data = await state.get_data()
    photos = get_photos_from_state(data)
    photos_sorted = sorted(photos, key=lambda p: p.order or 0)
    
    if not photos:
        await callback.answer("Нет фото для удаления", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(GenerationStates.deleting_photo)
    
    if callback.message:
        await callback.message.edit_text(
            f"🗑 <b>Выберите номер фото для удаления:</b>\n\n"
            f"Смотрите на превью выше и выберите номер фото, которое хотите удалить.\n\n"
            f"Загружено фото: {len(photos)}",
            reply_markup=get_photo_delete_keyboard([p.order for p in photos_sorted]),
            parse_mode="HTML",
        )


@router.callback_query(GenerationStates.deleting_photo, F.data.startswith("delete_photo:"))
async def callback_delete_photo(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Удаление конкретного фото по номеру.
    """
    photo_number = int(callback.data.split(":")[1])
    user_id = callback.from_user.id if callback.from_user else 0
    
    data = await state.get_data()
    photos = get_photos_from_state(data)
    
    photo_to_delete = next((p for p in photos if p.order == photo_number), None)
    if not photo_to_delete:
        await callback.answer("❌ Неверный номер фото", show_alert=True)
        return
    
    # Удаляем фото
    delete_temp_photo(user_id, photo_to_delete.id)
    
    # Обновляем список
    photos = [p for p in photos if p.order != photo_number]
    await state.update_data(photos=photos_to_state(photos))
    
    await callback.answer(f"✅ Фото #{photo_number} удалено")
    
    logger.info(
        "photo_deleted",
        telegram_id=user_id,
        deleted_filename=photo_to_delete.filename,
        remaining_count=len(photos),
    )
    
    if not photos:
        # Все фото удалены — возвращаем к загрузке
        await state.set_state(GenerationStates.waiting_photo)
        if callback.message:
            await callback.message.edit_text(
                "📷 <b>Все фото удалены</b>\n\n"
                "Отправьте новые фото товара для продолжения.",
                parse_mode="HTML",
            )
    else:
        # Возвращаемся к подтверждению
        await state.set_state(GenerationStates.confirming_photos)
        if callback.message:
            await callback.message.edit_text(
                format_confirmation_message(len(photos)),
                reply_markup=get_photo_confirmation_keyboard(),
                parse_mode="HTML",
            )


@router.callback_query(GenerationStates.deleting_photo, F.data == "back_to_confirmation")
async def callback_back_to_confirmation(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Возврат к экрану подтверждения без удаления.
    """
    data = await state.get_data()
    photos = get_photos_from_state(data)
    
    await callback.answer()
    await state.set_state(GenerationStates.confirming_photos)
    
    if callback.message:
        await callback.message.edit_text(
            format_confirmation_message(len(photos)),
            reply_markup=get_photo_confirmation_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(GenerationStates.confirming_photos, F.data == "photos_confirmed")
async def callback_photos_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Кнопка "Подтвердить" — переход к выбору категории.
    """
    data = await state.get_data()
    photos = get_photos_from_state(data)
    
    if not photos:
        await callback.answer("❌ Нет загруженных фото!", show_alert=True)
        return
    
    await callback.answer("✅ Отлично!")
    
    # Переходим к выбору категории
    await state.set_state(GenerationStates.waiting_category)
    
    if callback.message:
        await callback.message.edit_text(
            f"📸 <b>Загружено фото: {len(photos)}</b>\n\n"
            "Выберите категорию товара:",
            reply_markup=get_category_keyboard(),
            parse_mode="HTML",
        )
    
    logger.info(
        "photos_confirmed",
        telegram_id=callback.from_user.id if callback.from_user else 0,
        photo_count=len(photos),
    )


# ============================================================
# CALLBACK ОБРАБОТЧИКИ - СТАРЫЕ (для совместимости)
# ============================================================

@router.callback_query(GenerationStates.waiting_more_photos, F.data == "continue_generation")
async def callback_continue_legacy(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    """
    Старая кнопка "Продолжить" — редирект на новый флоу.
    """
    await callback_confirm_photos(callback, bot, state)


@router.callback_query(F.data == "cancel")
async def callback_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Отмена текущего действия."""
    current_state = await state.get_state()
    user_id = callback.from_user.id if callback.from_user else 0
    
    if current_state:
        # Очищаем временные файлы
        clear_user_temp_files(user_id)
        await state.clear()
        await callback.answer("Действие отменено")
        if callback.message:
            await callback.message.edit_text("❌ Генерация отменена.")
            await callback.message.answer(
                "Нажмите 🚀 <b>Создать ТЗ</b>, чтобы начать заново.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
    else:
        await callback.answer("Нечего отменять")


# ============================================================
# ОБРАБОТЧИКИ ОШИБОК ВВОДА
# ============================================================

@router.message(GenerationStates.waiting_photo, ~F.photo & ~F.document)
async def handle_not_photo_first(message: Message) -> None:
    """Если вместо первого фото пришло что-то другое."""
    await message.answer(
        PHOTO_UPLOAD_PROMPT,
        parse_mode="HTML",
    )


@router.message(GenerationStates.waiting_more_photos, ~F.photo & ~F.document)
async def handle_not_photo_more(
    message: Message,
    state: FSMContext,
) -> None:
    """Если вместо дополнительного фото пришло что-то другое."""
    data = await state.get_data()
    photos = get_photos_from_state(data)
    
    await message.answer(
        f"📷 Отправьте <b>фото</b> или нажмите кнопку ниже.\n\n"
        f"Загружено: {len(photos)}/{MAX_PHOTOS}",
        reply_markup=get_photo_actions_keyboard(len(photos)),
        parse_mode="HTML",
    )


@router.message(GenerationStates.confirming_photos)
async def handle_message_in_confirmation(
    message: Message,
    state: FSMContext,
) -> None:
    """Любое сообщение в режиме подтверждения."""
    data = await state.get_data()
    photos = get_photos_from_state(data)
    
    await message.answer(
        format_confirmation_message(len(photos)),
        reply_markup=get_photo_confirmation_keyboard(),
        parse_mode="HTML",
    )


@router.message(GenerationStates.deleting_photo)
async def handle_message_in_deletion(
    message: Message,
    state: FSMContext,
) -> None:
    """Любое сообщение в режиме удаления."""
    data = await state.get_data()
    photos = get_photos_from_state(data)
    photos_sorted = sorted(photos, key=lambda p: p.order or 0)
    
    await message.answer(
        f"🗑 <b>Выберите номер фото для удаления:</b>\n\n"
        "Смотрите на превью выше и выберите номер фото, которое хотите удалить.\n\n"
        f"Загружено фото: {len(photos)}",
        reply_markup=get_photo_delete_keyboard([p.order for p in photos_sorted]),
        parse_mode="HTML",
    )
