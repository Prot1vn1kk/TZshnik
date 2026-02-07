"""
TZshnik v2.0 - Auto-updater Entry Point

Профессиональная система автообновления через GitHub Releases.
Использует semantic versioning и ZIP архивы для простоты и надёжности.

Inspired by: https://github.com/alleexxeeyy/playerok-universal
"""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

GITHUB_REPO = "Prot1vn1kk/TZshnik"
VERSION_FILE = Path(__file__).parent / ".version"
VERSION = "2.0.1"  # Starting version

SKIP_UPDATE_FLAG = Path(__file__).parent / "TelegramBot_v2" / ".skip_update"

# Директории
PROJECT_ROOT = Path(__file__).resolve().parent
BOT_DIR = PROJECT_ROOT / "TelegramBot_v2"


# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TZshnik.Updater")


# ============================================================
# GITHUB RELEASES API
# ============================================================

def get_releases() -> list:
    """
    Получить все релизы с GitHub.

    Returns:
        Список релизов в формате JSON
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning(f"Ошибка запроса к GitHub API: {e}")
        return []


def get_latest_release(releases: list) -> Optional[dict]:
    """
    Найти последний релиз по semantic versioning.

    Args:
        releases: Список релизов из GitHub API

    Returns:
        Последний релиз или None
    """
    latest = None
    latest_ver = None

    for rel in releases:
        tag_name = rel.get("tag_name", "")
        if not tag_name:
            continue

        # Пропускаем prerelease если есть более стабильные
        if rel.get("prerelease", False):
            continue

        try:
            ver = Version(tag_name)
            if latest_ver is None or ver > latest_ver:
                latest_ver = ver
                latest = rel
        except Exception:
            # Пропускаем теги, которые не являются semver
            continue

    return latest


def download_release_zip(release_info: dict) -> Optional[bytes]:
    """
    Скачать ZIP архив релиза.

    Args:
        release_info: Информация о релизе из GitHub API

    Returns:
        Содержимое архива в байтах или None
    """
    zip_url = release_info.get('zipball_url')
    if not zip_url:
        logger.error("В релизе нет URL для скачивания архива")
        return None

    try:
        logger.info(f"Скачивание архива с {zip_url[:50]}...")
        response = requests.get(zip_url, timeout=120)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        logger.error(f"Ошибка скачивания архива: {e}")
        return None


def install_release(content: bytes) -> bool:
    """
    Распаковать и установить все файлы из архива обновления.

    Args:
        content: Содержимое ZIP архива в байтах

    Returns:
        True если успешно, False иначе
    """
    temp_dir = PROJECT_ROOT / ".temp_update"

    try:
        # Очищаем старую временную папку
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        temp_dir.mkdir(parents=True, exist_ok=True)

        # Распаковываем архив
        logger.info("Распаковка архива...")
        with zipfile.ZipFile(BytesIO(content), 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Находим корневую папку архива
        archive_root = None
        for item in temp_dir.iterdir():
            if item.is_dir():
                archive_root = item
                break

        if not archive_root:
            logger.error("В архиве нет корневой папки!")
            return False

        logger.info(f"Корневая папка архива: {archive_root.name}")

        # Копируем все файлы из архива
        files_count = 0
        for src_file in archive_root.rglob("*"):
            if src_file.is_file():
                # Вычисляем относительный путь от archive_root
                rel_path = src_file.relative_to(archive_root)

                # Если путь содержит "TelegramBot_v2", берём после него
                # Это нужно потому что в архиве файлы лежат в {repo}-{hash}/TelegramBot_v2/
                path_parts = rel_path.parts
                try:
                    tg_idx = path_parts.index("TelegramBot_v2")
                    rel_path = Path(*path_parts[tg_idx + 1:])
                except ValueError:
                    # Если нет TelegramBot_v2 в пути, пропускаем файл
                    # (это могут быть файлы уровня выше, которые не нужно обновлять)
                    continue

                dst_file = BOT_DIR / rel_path

                # Создаём директорию если нужно
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # Копируем файл
                shutil.copy2(src_file, dst_file)
                files_count += 1

        logger.info(f"Обновлено {files_count} файлов")
        return True

    except Exception as e:
        logger.error(f"Ошибка установки обновления: {e}", exc_info=True)
        return False

    finally:
        # Удаляем временную папку
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================
# УПРАВЛЕНИЕ ВЕРСИЯМИ
# ============================================================

def get_current_version() -> str:
    """
    Получить текущую версию из файла.

    Returns:
        Текущая версия
    """
    if VERSION_FILE.exists():
        try:
            return VERSION_FILE.read_text().strip()
        except Exception:
            pass
    return VERSION


def set_current_version(version: str) -> None:
    """
    Сохранить версию в файл.

    Args:
        version: Версия для сохранения
    """
    try:
        VERSION_FILE.write_text(version)
    except Exception as e:
        logger.warning(f"Не удалось сохранить версию: {e}")


# ============================================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================

def install_dependencies() -> bool:
    """
    Установить зависимости из requirements.txt если их нет.

    Returns:
        True если зависимости установлены или уже были
    """
    requirements_file = BOT_DIR / "requirements.txt"

    if not requirements_file.exists():
        logger.warning("requirements.txt не найден, пропускаем установку")
        return True

    # Проверяем, установлены ли критичные зависимости
    try:
        import requests
        import packaging
        logger.info("✅ Критичные зависимости уже установлены")
        return True
    except ImportError:
        logger.info("📦 Установка зависимостей...")

    # Пытаемся установить зависимости
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--upgrade", "pip"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", str(requirements_file)
        ])

        logger.info("✅ Зависимости успешно установлены")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Ошибка установки зависимостей: {e}")
        logger.error("Попробуйте установить вручную: pip install -r TelegramBot_v2/requirements.txt")
        return False


# ============================================================
# ПРОВЕРКА ФАЙЛОВОЙ СИСТЕМЫ
# ============================================================

def check_filesystem_writable(path: Optional[Path] = None) -> bool:
    """
    Проверить, можно ли писать в файловую систему.

    Args:
        path: Путь для проверки (по умолчанию BOT_DIR)

    Returns:
        True если можно писать
    """
    test_path = path or BOT_DIR

    try:
        test_file = test_path / f".write_test_{os.getpid()}"
        test_file.write_text("test")
        test_file.unlink()
        return True
    except (OSError, IOError, PermissionError):
        logger.warning("Файловая система только для чтения")
        return False


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ АВТООБНОВЛЕНИЯ
# ============================================================

def auto_update() -> bool:
    """
    Главная функция автообновления.

    Returns:
        True если можно продолжать запуск бота
    """
    # Проверяем флаг пропуска обновления
    if SKIP_UPDATE_FLAG.exists():
        logger.info("⏭️ Обновление отключено (файл .skip_update)")
        return True

    # Проверяем возможность записи
    if not check_filesystem_writable():
        logger.warning("⚠️ Read-only файловая система, пропускаем обновление")
        return True

    # Импортируем requests и packaging (могут быть не установлены)
    try:
        import requests
        from packaging.version import Version as PkgVersion
    except ImportError as e:
        logger.warning(f"⚠️ Автообновление недоступно: {e}")
        logger.warning("Установите зависимости: pip install requests packaging")
        return True

    try:
        logger.info("🔍 Проверка обновлений через GitHub Releases...")

        # Получаем релизы
        releases = get_releases()
        if not releases:
            logger.info("Нет доступных релизов")
            return True

        # Находим последний релиз
        latest = get_latest_release(releases)
        if not latest:
            logger.info("Не найдено валидных релизов")
            return True

        latest_tag = latest.get("tag_name", "")
        current = get_current_version()

        logger.info(f"Текущая версия: {current}")
        logger.info(f"Последняя версия: {latest_tag}")

        # Сравниваем версии через semver
        try:
            current_ver = PkgVersion(current)
            latest_ver = PkgVersion(latest_tag)
        except Exception as e:
            logger.warning(f"Некорректные версии: {e}")
            return True

        if current_ver >= latest_ver:
            logger.info("✅ Установлена актуальная версия")
            return True

        # Доступно обновление
        logger.info(f"📦 Доступно обновление: {latest_tag}")

        # Скачиваем архив
        content = download_release_zip(latest)
        if not content:
            logger.error("Не удалось скачать архив обновления")
            return True  # Продолжаем работу бота

        # Устанавливаем обновление
        logger.info(f"📦 Установка обновления {latest_tag}...")
        if install_release(content):
            set_current_version(latest_tag)
            logger.info(f"✅ Обновление до {latest_tag} успешно установлено!")
            return True
        else:
            logger.error("❌ Не удалось установить обновление")
            return True

    except Exception as e:
        logger.error(f"Ошибка автообновления: {e}", exc_info=True)
        return True  # Продолжаем работу бота при ошибках


# ============================================================
# ПОДГОТОВКА ОКРУЖЕНИЯ
# ============================================================

def prepare_environment():
    """Подготовка окружения перед запуском бота."""
    folders = [
        BOT_DIR / "data",
        BOT_DIR / "exports",
        BOT_DIR / "data" / "temp_files",
    ]

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# ИСПРАВЛЕНИЕ ПУТЕЙ ИМПОРТА
# ============================================================

def fix_import_paths():
    """Добавляет все необходимые пути в sys.path."""
    paths_to_add = [
        str(PROJECT_ROOT),
        str(BOT_DIR),
        str(BOT_DIR / "bot"),
        str(BOT_DIR / "config"),
        str(BOT_DIR / "database"),
        str(BOT_DIR / "utils"),
        str(BOT_DIR / "templates"),
    ]

    for path in paths_to_add:
        if path not in sys.path and Path(path).exists():
            sys.path.insert(0, path)


# ============================================================
# ПЕРЕЗАПУСК БОТА
# ============================================================

def restart_bot():
    """Перезапустить бота после обновления."""
    logger.info("🔄 Перезапуск бота...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Запуск TZshnik бота...")
    logger.info("=" * 60)

    # Исправляем пути импорта
    fix_import_paths()

    # Устанавливаем зависимости если их нет
    if not install_dependencies():
        logger.error("❌ Не удалось установить зависимости")
        logger.error("Установите вручную: pip install -r TelegramBot_v2/requirements.txt")
        sys.exit(1)

    # Проверяем и применяем обновления
    try:
        auto_update()
    except Exception as e:
        logger.warning(f"⚠️ Автообновление пропущено: {e}")

    # Готовим папки
    prepare_environment()

    # Импортируем и запускаем ботов
    try:
        from bot.main import main as main_bot

        # Пытаемся импортировать бота поддержки
        support_bot_main = None
        try:
            from support_bot.main import main as support_main
            support_bot_main = support_main
            logger.info("🤖 Запуск основного бота + бота поддержки...")
        except ImportError as e:
            logger.warning(f"⚠️ Бот поддержки не найден, запуск только основного: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации бота поддержки: {e}")

        async def run_all_bots():
            """Запустить все боты конкурентно."""
            tasks = [main_bot()]
            if support_bot_main:
                tasks.append(support_bot_main())
            await asyncio.gather(*tasks)

        asyncio.run(run_all_bots())

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        logger.error(f"   sys.path: {sys.path}")
        logger.error(f"   BOT_DIR существует: {BOT_DIR.exists()}")
        if BOT_DIR.exists():
            logger.error(f"   bot/main.py существует: {(BOT_DIR / 'bot' / 'main.py').exists()}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⛔ Боты остановлены пользователем")

    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
