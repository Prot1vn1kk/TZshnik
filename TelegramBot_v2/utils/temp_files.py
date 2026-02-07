"""
Управление временными файлами фотографий.

Модуль обеспечивает:
- Сохранение загруженных фото во временную папку
- Валидацию форматов файлов (только .jpeg, .png)
- Генерацию уникальных имён файлов
- Удаление отдельных файлов
- Очистку временных файлов пользователя
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import structlog


logger = structlog.get_logger()

# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Директория для временных файлов
TEMP_FILES_DIR = BASE_DIR / "data" / "temp_files"

# Допустимые форматы изображений
ALLOWED_EXTENSIONS = {".jpeg", ".jpg", ".png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}


@dataclass
class TempPhoto:
    """Информация о временном фото файле."""
    id: str  # UUID идентификатор
    filename: str  # Имя файла с расширением
    path: Path  # Полный путь к файлу
    size_bytes: int  # Размер файла в байтах
    extension: str  # Расширение файла (.jpeg, .png)
    created_at: datetime  # Время создания
    order: int = 0  # Порядковый номер загрузки (стабильный)
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя файла для пользователя."""
        return self.filename
    
    @property
    def format_display(self) -> str:
        """Формат файла для отображения."""
        return self.extension.upper().replace(".", "")
    
    def to_dict(self) -> dict:
        """Конвертация в словарь для хранения в FSM state."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "extension": self.extension,
            "created_at": self.created_at.isoformat(),
            "order": self.order,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TempPhoto":
        """Создание из словаря FSM state."""
        return cls(
            id=data["id"],
            filename=data["filename"],
            path=Path(data["path"]),
            size_bytes=data["size_bytes"],
            extension=data["extension"],
            created_at=datetime.fromisoformat(data["created_at"]),
            order=data.get("order", 0),
        )


def ensure_temp_dir(user_id: int) -> Path:
    """
    Создание директории для временных файлов пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Путь к директории пользователя
    """
    user_dir = TEMP_FILES_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def validate_file_format(
    file_bytes: bytes,
    original_filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """
    Валидация формата файла.
    
    Args:
        file_bytes: Бинарные данные файла
        original_filename: Оригинальное имя файла (если известно)
        mime_type: MIME-тип файла (если известен)
        
    Returns:
        Tuple[is_valid, extension, error_message]
    """
    extension = ".jpeg"  # По умолчанию (Telegram сжимает в JPEG)
    
    # Проверяем magic bytes (сигнатуру файла)
    if file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        extension = ".png"
    elif file_bytes[:2] == b'\xff\xd8':
        extension = ".jpeg"
    else:
        # Если magic bytes не распознаны, проверяем MIME-type
        if mime_type:
            if mime_type == "image/png":
                extension = ".png"
            elif mime_type in ("image/jpeg", "image/jpg"):
                extension = ".jpeg"
            elif mime_type not in ALLOWED_MIME_TYPES:
                return False, "", f"Неподдерживаемый формат: {mime_type}"
        # Проверяем расширение из имени файла
        elif original_filename:
            ext = Path(original_filename).suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                extension = ".jpeg" if ext in (".jpg", ".jpeg") else ext
            else:
                return False, "", f"Неподдерживаемый формат: {ext}"
        else:
            return False, "", "Не удалось определить формат файла"
    
    return True, extension, ""


def save_temp_photo(
    user_id: int,
    file_bytes: bytes,
    original_filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> Tuple[Optional[TempPhoto], str]:
    """
    Сохранение фото во временную папку.
    
    Args:
        user_id: Telegram ID пользователя
        file_bytes: Бинарные данные фото
        original_filename: Оригинальное имя файла
        mime_type: MIME-тип файла
        
    Returns:
        Tuple[TempPhoto или None, сообщение об ошибке]
    """
    # Валидация формата
    is_valid, extension, error = validate_file_format(
        file_bytes, original_filename, mime_type
    )
    if not is_valid:
        return None, error
    
    # Создаём директорию пользователя
    user_dir = ensure_temp_dir(user_id)
    
    # Генерируем уникальное имя файла
    photo_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%H%M%S")
    
    # Формируем читаемое имя файла
    if original_filename:
        # Используем оригинальное имя, очищенное от спецсимволов
        base_name = Path(original_filename).stem
        # Убираем небезопасные символы
        safe_name = "".join(c for c in base_name if c.isalnum() or c in "._- ")[:30]
        filename = f"{safe_name}_{photo_id}{extension}"
    else:
        filename = f"Photo_{timestamp}_{photo_id}{extension}"
    
    file_path = user_dir / filename
    
    try:
        # Сохраняем файл
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        photo = TempPhoto(
            id=photo_id,
            filename=filename,
            path=file_path,
            size_bytes=len(file_bytes),
            extension=extension,
            created_at=datetime.now(),
        )

        logger.info(
            "temp_photo_saved",
            user_id=user_id,
            photo_id=photo_id,
            filename=filename,
            size_bytes=len(file_bytes),
        )

        return photo, ""

    except OSError as e:
        # Ошибка файловой системы (нет места, нет прав и т.д.)
        logger.error(
            "temp_photo_save_failed",
            user_id=user_id,
            error_type="OSError",
            error=str(e),
            filename=filename,
        )
        return None, f"Ошибка сохранения файла: {str(e)}"
    except (ValueError, TypeError) as e:
        # Ошибка валидации данных
        logger.error(
            "temp_photo_save_failed",
            user_id=user_id,
            error_type="ValidationError",
            error=str(e),
        )
        return None, f"Ошибка валидации: {str(e)}"


def delete_temp_photo(user_id: int, photo_id: str) -> bool:
    """
    Удаление конкретного временного фото.
    
    Args:
        user_id: Telegram ID пользователя
        photo_id: ID фото (UUID)
        
    Returns:
        True если файл удалён успешно
    """
    user_dir = TEMP_FILES_DIR / str(user_id)
    
    if not user_dir.exists():
        return False
    
    # Ищем файл по ID в имени
    for file_path in user_dir.iterdir():
        if photo_id in file_path.name:
            try:
                file_path.unlink()
                logger.info(
                    "temp_photo_deleted",
                    user_id=user_id,
                    photo_id=photo_id,
                )
                return True
            except Exception as e:
                logger.error(
                    "temp_photo_delete_failed",
                    user_id=user_id,
                    photo_id=photo_id,
                    error=str(e),
                )
                return False
    
    return False


def get_user_temp_photos(user_id: int) -> List[Path]:
    """
    Получение списка временных фото пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Список путей к файлам
    """
    user_dir = TEMP_FILES_DIR / str(user_id)
    
    if not user_dir.exists():
        return []
    
    return sorted(user_dir.iterdir(), key=lambda p: p.stat().st_mtime)


def read_temp_photo(file_path: Path) -> Optional[bytes]:
    """
    Чтение содержимого временного фото.

    Args:
        file_path: Путь к файлу

    Returns:
        Бинарные данные или None
    """
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except OSError as e:
        logger.error(
            "temp_photo_read_failed",
            path=str(file_path),
            error_type="OSError",
            error=str(e),
        )
        return None
    except ValueError as e:
        logger.error(
            "temp_photo_read_failed",
            path=str(file_path),
            error_type="ValueError",
            error=str(e),
        )
        return None


def clear_user_temp_files(user_id: int) -> int:
    """
    Очистка всех временных файлов пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Количество удалённых файлов
    """
    user_dir = TEMP_FILES_DIR / str(user_id)
    
    if not user_dir.exists():
        return 0
    
    count = 0
    try:
        for file_path in user_dir.iterdir():
            try:
                file_path.unlink()
                count += 1
            except Exception:
                pass
        
        # Пытаемся удалить пустую директорию
        try:
            user_dir.rmdir()
        except Exception:
            pass
        
        logger.info(
            "user_temp_files_cleared",
            user_id=user_id,
            files_deleted=count,
        )
        
    except Exception as e:
        logger.error(
            "temp_files_clear_failed",
            user_id=user_id,
            error=str(e),
        )
    
    return count


def cleanup_old_temp_files(max_age_hours: int = 24) -> int:
    """
    Очистка старых временных файлов всех пользователей.

    Вызывается при запуске бота или по расписанию.

    Args:
        max_age_hours: Максимальный возраст файлов в часах

    Returns:
        Количество удалённых файлов
    """
    if not TEMP_FILES_DIR.exists():
        TEMP_FILES_DIR.mkdir(parents=True, exist_ok=True)
        return 0

    count = 0
    cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

    try:
        for user_dir in TEMP_FILES_DIR.iterdir():
            if not user_dir.is_dir():
                continue

            for file_path in user_dir.iterdir():
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        count += 1
                except OSError:
                    # Игнорируем ошибки при удалении отдельных файлов
                    pass

            # Удаляем пустые директории
            try:
                if not any(user_dir.iterdir()):
                    user_dir.rmdir()
            except OSError:
                # Игнорируем ошибки при удалении пустых директорий
                pass

        if count > 0:
            logger.info(
                "old_temp_files_cleaned",
                files_deleted=count,
                max_age_hours=max_age_hours,
            )

    except OSError as e:
        logger.error(
            "temp_files_cleanup_failed",
            error_type="OSError",
            error=str(e),
        )
    except ValueError as e:
        logger.error(
            "temp_files_cleanup_failed",
            error_type="ValueError",
            error=str(e),
        )

    return count


def format_file_list(photos: List[TempPhoto]) -> str:
    """
    Форматирование списка файлов для отображения пользователю.
    
    Args:
        photos: Список TempPhoto объектов
        
    Returns:
        Форматированная строка со списком файлов
    """
    if not photos:
        return "Нет загруженных файлов"
    
    lines = []
    for i, photo in enumerate(photos, 1):
        size_kb = photo.size_bytes / 1024
        lines.append(
            f"{i}. <code>{photo.filename}</code> ({photo.format_display}, {size_kb:.1f} KB)"
        )
    
    return "\n".join(lines)
