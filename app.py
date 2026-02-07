import asyncio
import os
import sys
import zipfile
import io
import hashlib
import json
from pathlib import Path
import logging
import shutil
from datetime import datetime
from typing import Optional, Dict, Any
import urllib.request
import urllib.error

# Настройка базового логирования для отладки запуска
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DeployShim")

# Определяем пути
project_root = Path(__file__).resolve().parent
bot_dir = project_root / "TelegramBot_v2"

# GitHub конфигурация
GITHUB_REPO = "Prot1vn1kk/TZshnik"
GITHUB_API_BASE = "https://api.github.com"
CURRENT_VERSION_FILE = project_root / ".version"

# Файл для пропуска обновлений
SKIP_UPDATE_FLAG = bot_dir / ".skip_update"


# ============================================================
# ВЕРСИЯ ПРОЕКТА
# ============================================================

VERSION = "2.0.1"  # Текущая версия бота


def get_current_version() -> str:
    """Получает текущую версию бота."""
    # Если есть файл версии, читаем из него
    if CURRENT_VERSION_FILE.exists():
        try:
            with open(CURRENT_VERSION_FILE, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return VERSION


def set_current_version(version: str) -> bool:
    """Сохраняет текущую версию."""
    try:
        with open(CURRENT_VERSION_FILE, 'w') as f:
            f.write(version)
        return True
    except Exception as e:
        logger.warning(f"Не удалось сохранить версию: {e}")
        return False


# ============================================================
# GITHUB API ФУНКЦИИ
# ============================================================

def fetch_github_api(endpoint: str) -> Optional[Dict[str, Any]]:
    """
    Выполняет запрос к GitHub API.

    Args:
        endpoint: API endpoint (например, /repos/user/repo/releases/latest)

    Returns:
        JSON ответ или None
    """
    url = f"{GITHUB_API_BASE}{endpoint}"

    try:
        request = urllib.request.Request(url)
        request.add_header('User-Agent', 'TZshnik-Bot')
        request.add_header('Accept', 'application/vnd.github.v3+json')

        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)

    except urllib.error.HTTPError as e:
        logger.warning(f"GitHub API HTTP Error: {e.code}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"GitHub API Connection Error: {e}")
        return None
    except Exception as e:
        logger.warning(f"GitHub API Error: {e}")
        return None


def get_latest_commit() -> Optional[Dict[str, Any]]:
    """
    Получает информацию о последнем коммите в ветке main.

    Returns:
        Информация о коммите или None
    """
    return fetch_github_api(f"/repos/{GITHUB_REPO}/commits/main")


def get_file_from_github(file_path: str, ref: str = "main") -> Optional[str]:
    """
    Получает содержимое файла из GitHub.

    Args:
        file_path: Путь к файлу в репозитории
        ref: Ветка или коммит

    Returns:
        Содержимое файла или None
    """
    return fetch_github_api(f"/repos/{GITHUB_REPO}/contents/TelegramBot_v2/{file_path}?ref={ref}")


# ============================================================
# ПРОВЕРКА ФАЙЛОВОЙ СИСТЕМЫ
# ============================================================

def check_filesystem_writable(path: Optional[Path] = None) -> bool:
    """
    Проверяет, можно ли писать в файловую систему.

    Args:
        path: Путь для проверки (по умолчанию project_root)

    Returns:
        True если можно писать
    """
    test_path = path or project_root

    try:
        # Пытаемся создать тестовый файл
        test_file = test_path / f".write_test_{os.getpid()}"
        test_file.write_text("test")
        test_file.unlink()
        return True
    except (OSError, IOError, PermissionError) as e:
        logger.warning(f"Файловая система только для чтения: {e}")
        return False


def get_writable_dir() -> Optional[Path]:
    """
    Находит директорию, доступную для записи.

    Returns:
        Путь к writable директории или None
    """
    # Проверяем домашнюю директорию
    home = Path.home()
    if check_filesystem_writable(home):
        return home

    # Проверяем /tmp
    tmp = Path("/tmp")
    if tmp.exists() and check_filesystem_writable(tmp):
        return tmp

    # Проверяем текущую директорию
    cwd = Path.cwd()
    if check_filesystem_writable(cwd):
        return cwd

    return None


# ============================================================
# ФУНКЦИИ ОБНОВЛЕНИЯ
# ============================================================

def check_updates() -> tuple[bool, Optional[str], Optional[str]]:
    """
    Проверяет наличие обновлений через GitHub API.

    Returns:
        Tuple[has_updates, latest_commit_sha, commit_message]
    """
    logger.info("🔍 Проверка обновлений через GitHub API...")

    commit_info = get_latest_commit()
    if not commit_info or 'sha' not in commit_info:
        logger.warning("⚠️ Не удалось получить информацию о коммите")
        return False, None, None

    latest_sha = commit_info['sha'][:8]  # Короткий хеш
    message = commit_info.get('commit', {}).get('message', 'Нет описания')
    date_str = commit_info.get('commit', {}).get('committer', {}).get('date', '')

    # Читаем сохранённую версию
    saved_version = get_current_version()

    has_updates = saved_version != latest_sha

    if has_updates:
        logger.info(f"📦 Доступно обновление: {latest_sha}")
        if date_str:
            logger.info(f"   Дата: {date_str}")
        if message:
            logger.info(f"   Изменения: {message[:100]}...")
    else:
        logger.info("✅ Бот актуален")

    return has_updates, latest_sha, message


def download_and_update_py_files() -> bool:
    """
    Загружает и обновляет только Python файлы (без данных и конфигов).

    Returns:
        True если обновление успешно
    """
    logger.info("⬇️ Загрузка обновлений Python файлов...")

    # Список файлов для обновления (Python модули)
    files_to_update = [
        "bot/__init__.py",
        "bot/main.py",
        "bot/config/__init__.py",
        "bot/config/settings.py",
        "bot/handlers/__init__.py",
        "bot/handlers/start.py",
        "bot/handlers/admin_panel.py",
        "bot/keyboards/__init__.py",
        "bot/keyboards/admin_keyboards.py",
        "bot/middleware.py",
        "bot/states.py",
        "config/__init__.py",
        "config/packages.py",
        "config/constants.py",
        "database/__init__.py",
        "database/database.py",
        "database/models.py",
        "database/crud.py",
        "database/admin_crud.py",
        "templates/__init__.py",
        "templates/message_templates.py",
        "utils/__init__.py",
        "utils/temp_files.py",
        "utils/pdf_export.py",
        "utils/validators.py",
        "app.py",
    ]

    success_count = 0

    for file_path in files_to_update:
        try:
            # Получаем файл из GitHub
            file_info = get_file_from_github(file_path)
            if not file_info or 'content' not in file_info:
                logger.warning(f"⚠️ Файл {file_path} не найден на GitHub")
                continue

            # Декодируем содержимое (base64)
            import base64
            content = base64.b64decode(file_info['content']).decode('utf-8')

            # Записываем файл
            target_path = bot_dir / file_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding='utf-8')

            success_count += 1
            logger.info(f"   ✅ {file_path}")

        except Exception as e:
            logger.warning(f"   ❌ {file_path}: {e}")

    logger.info(f"✅ Обновлено {success_count}/{len(files_to_update)} файлов")
    return success_count > 0


def update_via_github_zipball() -> bool:
    """
    Альтернативный метод: скачивание ZIP архива с GitHub.
    Работает на некоторых облачных хостингах.

    Returns:
        True если обновление успешно
    """
    logger.info("📦 Попытка обновления через ZIP архив...")

    zipball_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"

    try:
        # Скачиваем ZIP
        request = urllib.request.Request(zipball_url)
        request.add_header('User-Agent', 'TZshnik-Bot')

        with urllib.request.urlopen(request, timeout=60) as response:
            zip_data = response.read()

        # Распаковываем в памяти
        with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
            # Получаем список файлов
            file_list = zip_ref.namelist()

            # Фильтруем только нужные файлы (Python модули)
            py_files = [f for f in file_list if f.endswith('.py') and
                       'TelegramBot_v2' in f and
                       '__pycache__' not in f and
                       '.pyc' not in f]

            logger.info(f"📦 Найдено {len(py_files)} Python файлов")

            for zip_path in py_files:
                try:
                    # Извлекаем файл
                    file_data = zip_ref.read(zip_path)

                    # Вычисляем целевой путь
                    # ZIP путь: TZshnik-main/TelegramBot_v2/file.py
                    relative_path = zip_path.split('TelegramBot_v2/', 1)[1]
                    target_path = bot_dir / relative_path

                    # Создаём директорию
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Записываем файл
                    target_path.write_bytes(file_data)

                except Exception as e:
                    logger.warning(f"   ⚠️ {zip_path}: {e}")

        logger.info("✅ Обновление через ZIP завершено")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка ZIP обновления: {e}")
        return False


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ АВТООБНОВЛЕНИЯ
# ============================================================

def auto_update() -> bool:
    """
    Основная функция автообновления для облачного хостинга.

    Returns:
        True если обновление прошло успешно или не требуется
    """
    # Проверяем флаг пропуска обновления
    if SKIP_UPDATE_FLAG.exists():
        logger.info("⏭️ Обновление отключено (файл .skip_update)")
        return True

    try:
        # Проверяем возможность записи
        if not check_filesystem_writable(bot_dir):
            logger.warning("⚠️ Файловая система только для чтения")

            # Проверяем наличие обновлений
            has_updates, latest_sha, message = check_updates()

            if has_updates:
                logger.warning("=" * 60)
                logger.warning("📦 ДОСТУПНО ОБНОВЛЕНИЕ!")
                logger.warning(f"   Версия: {latest_sha}")
                logger.warning("🔧 Обновление невозможно автоматически (read-only FS)")
                logger.warning("📝 Пожалуйста, обратитесь в службу поддержки")
                logger.warning("=" * 60)

            return True

        # Обычный режим обновления
        has_updates, latest_sha, message = check_updates()

        if not has_updates:
            return True

        # Метод 1: Обновление отдельных файлов через API
        logger.info("🔄 Метод 1: Обновление через GitHub API...")

        if download_and_update_py_files():
            # Сохраняем новую версию
            set_current_version(latest_sha)
            logger.info("✅ Обновление завершено успешно!")
            return True

        # Метод 2: ZIP архив (fallback)
        logger.info("🔄 Метод 2: Обновление через ZIP архив...")

        if update_via_github_zipball():
            set_current_version(latest_sha)
            logger.info("✅ Обновление завершено!")
            return True

        logger.warning("⚠️ Все методы обновления не сработали")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка автообновления: {e}")
        return True  # Продолжаем работу бота


# ============================================================
# ПОДГОТОВКА ОКРУЖЕНИЯ
# ============================================================

def prepare_environment():
    """Подготовка окружения перед запуском."""
    # Создаем папку data внутри TelegramBot_v2, если её нет
    data_dir = bot_dir / "data"
    exports_dir = bot_dir / "exports"
    temp_files_dir = bot_dir / "data" / "temp_files"

    for folder in [data_dir, exports_dir, temp_files_dir]:
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Создана директория: {folder}")
            except Exception as e:
                logger.error(f"❌ Не удалось создать директорию {folder}: {e}")
                continue  # Продолжаем с другими папками

        # Проверяем права на запись
        if folder.exists():
            if os.access(folder, os.W_OK):
                logger.info(f"✅ Доступ на запись в {folder} подтвержден")
            else:
                logger.warning(f"⚠️ Нет прав на запись в {folder}")


# ============================================================
# ИСПРАВЛЕНИЕ ПУТЕЙ ИМПОРТА
# ============================================================

def fix_import_paths():
    """Исправляет пути импорта для разных окружений."""
    # Добавляем все необходимые пути в sys.path
    paths_to_add = [
        str(project_root),
        str(bot_dir),
        str(bot_dir / "bot"),
        str(bot_dir / "config"),
        str(bot_dir / "database"),
        str(bot_dir / "utils"),
        str(bot_dir / "templates"),
    ]

    for path in paths_to_add:
        if path not in sys.path and Path(path).exists():
            sys.path.insert(0, path)
            logger.debug(f"Добавлен путь: {path}")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Запуск TZshnik бота...")
    logger.info("=" * 60)

    # Исправляем пути импорта
    fix_import_paths()

    # Проверяем и применяем обновления
    try:
        auto_update()
    except Exception as e:
        logger.warning(f"⚠️ Автообновление пропущено: {e}")

    # Готовим папки
    prepare_environment()

    # Импортируем и запускаем бота
    try:
        # Пробуем разные варианты импорта
        try:
            from bot.main import main
        except ImportError:
            # Fallback для облачного хостинга
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "main",
                bot_dir / "bot" / "main.py"
            )
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)
            main = main_module.main

        logger.info("🤖 Запуск бота...")
        asyncio.run(main())

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        logger.error(f"   sys.path: {sys.path}")
        logger.error(f"   bot_dir существует: {bot_dir.exists()}")
        if bot_dir.exists():
            logger.error(f"   bot/main.py существует: {(bot_dir / 'bot' / 'main.py').exists()}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⛔ Бот остановлен пользователем")

    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
