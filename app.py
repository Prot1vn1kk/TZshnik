"""
TZshnik v2.0 - Auto-updater Entry Point

Система автообновления через GitHub Commits.
Автоматически обновляется при каждом git push в ветку main.

Inspired by: https://github.com/alleexxeeyy/playerok-universal
"""

import asyncio
import logging
import os
import shutil
import site
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

GITHUB_REPO = "Prot1vn1kk/TZshnik"
GITHUB_BRANCH = "main"  # Ветка для отслеживания
COMMIT_FILE = Path(__file__).parent / ".commit"  # Файл с текущим коммитом

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
# GITHUB COMMITS API
# ============================================================

def get_latest_commit():
    """
    Получить последний коммит из ветки main.

    Returns:
        SHA коммита или None
    """
    try:
        import httpx
    except ImportError:
        try:
            import requests
        except ImportError:
            logger.warning("httpx и requests не установлены, пропускаем проверку обновлений")
            return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"

    try:
        try:
            import httpx
            with httpx.Client(timeout=30) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("sha")
        except ImportError:
            import requests
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("sha")
    except Exception as e:
        logger.warning(f"Ошибка запроса к GitHub API: {e}")
        return None


def download_branch_zip():
    """
    Скачать ZIP архив ветки main.

    Returns:
        Содержимое архива в байтах или None
    """
    zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

    try:
        logger.info(f"📥 Скачивание архива ветки {GITHUB_BRANCH}...")
        try:
            import httpx
            with httpx.Client(timeout=120, follow_redirects=True) as client:
                response = client.get(zip_url)
                response.raise_for_status()
                return response.content
        except ImportError:
            import requests
            response = requests.get(zip_url, timeout=120, allow_redirects=True)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Ошибка скачивания архива: {e}")
        return None


def install_release(content):
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

                # Логируем важные файлы
                if files_count <= 10 or 'support' in str(rel_path):
                    logger.info(f"  + {rel_path}")

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
# УПРАВЛЕНИЕ КОММИТАМИ
# ============================================================

def get_current_commit():
    """
    Получить текущий коммит из файла.

    Returns:
        SHA текущего коммита или None
    """
    if COMMIT_FILE.exists():
        try:
            content = COMMIT_FILE.read_text().strip()
            if content and len(content) >= 7:  # Минимальная длина короткого SHA
                return content
        except Exception:
            pass
    return None


def set_current_commit(commit_sha):
    """
    Сохранить коммит в файл.

    Args:
        commit_sha: SHA коммита для сохранения
    """
    try:
        COMMIT_FILE.write_text(commit_sha)
    except Exception as e:
        logger.warning(f"Не удалось сохранить коммит: {e}")


# ============================================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================

def install_dependencies():
    """
    Установить зависимости из requirements.txt если их нет.

    Returns:
        True если зависимости установлены или уже были
    """
    requirements_file = BOT_DIR / "requirements.txt"

    if not requirements_file.exists():
        logger.warning("requirements.txt не найден, пропускаем установку")
        return True

    deps_installed_flag = BOT_DIR / ".deps_installed"

    # === CRITICAL FIX: Add user site-packages to sys.path BEFORE import checks ===
    # This fixes the issue where packages are installed but not importable

    # Add .local/lib path for Pterodactyl hosting
    local_lib = Path.home() / ".local" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if local_lib.exists() and str(local_lib) not in sys.path:
        sys.path.insert(0, str(local_lib))
        logger.debug(f"Добавлен путь к модулям: {local_lib}")

    # Also enable user site
    try:
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.insert(0, user_site)
    except Exception:
        pass

    # === Now check imports with proper sys.path ===

    # ПРОВЕРЯЕМ ИМПОРТЫ ПЕРВЫМИ (всегда, даже если флаг существует)
    try:
        import httpx
        # Импорты успешны - создаём флаг если его нет
        if not deps_installed_flag.exists():
            try:
                deps_installed_flag.touch()
            except Exception:
                pass
        logger.info("✅ Критичные зависимости доступны (httpx OK)")
        return True
    except ImportError:
        # Модули не доступны
        pass

    # Если флаг существует, но импорты не удались - удаляем флаг
    if deps_installed_flag.exists():
        logger.warning("⚠️ Флаг существует, но модули не доступны. Пересоздаём...")
        try:
            deps_installed_flag.unlink()
        except Exception:
            pass

    # Устанавливаем зависимости
    logger.info("📦 Установка зависимостей...")
    try:
        logger.info(f"📥 Установка из {requirements_file.name}...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", str(requirements_file)
        ])

        logger.info("✅ Зависимости успешно установлены")

        # Create flag but DON'T restart - Pterodactyl handles deps
        try:
            deps_installed_flag.touch()
        except Exception:
            pass

        # Try one more import check after installation
        try:
            import importlib
            importlib.invalidate_caches()  # Clear import cache
            import httpx
            logger.info("✅ Зависимости теперь доступны")
            return True
        except ImportError:
            logger.warning("⚠️ Зависимости установлены, но импорт по-прежнему не работает")
            logger.warning("💡 Пробуем продолжить в любом случае...")
            return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Ошибка установки зависимостей (код {e.returncode})")
        logger.error("💡 Попробуйте установить вручную:")
        logger.error(f"   pip install -r {requirements_file}")
        return False


# ============================================================
# ПРОВЕРКА ФАЙЛОВОЙ СИСТЕМЫ
# ============================================================

def check_filesystem_writable(path=None):
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

def auto_update():
    """
    Главная функция автообновления через GitHub коммиты.

    Сравнивает текущий коммит с последним в ветке main.
    Если есть новый коммит - скачивает и устанавливает обновление.

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

    # Проверяем httpx или requests
    try:
        import httpx
    except ImportError:
        try:
            import requests
        except ImportError:
            logger.warning("⚠️ Автообновление недоступно: не установлен httpx или requests")
            logger.info("💡 Убедитесь что requirements.txt содержит httpx")
            return True

    try:
        logger.info(f"🔍 Проверка обновлений (ветка {GITHUB_BRANCH})...")

        # Получаем последний коммит
        latest_commit = get_latest_commit()
        if not latest_commit:
            logger.warning("Не удалось получить последний коммит")
            return True

        current_commit = get_current_commit()

        # Показываем короткие SHA для читаемости
        latest_short = latest_commit[:7]
        current_short = current_commit[:7] if current_commit else "не установлен"

        logger.info(f"Текущий коммит: {current_short}")
        logger.info(f"Последний коммит: {latest_short}")

        # Сравниваем коммиты
        if current_commit and current_commit == latest_commit:
            logger.info("✅ Установлена актуальная версия")
            return True

        # Доступно обновление
        logger.info(f"📦 Доступно обновление: {latest_short}")

        # Скачиваем архив ветки
        content = download_branch_zip()
        if not content:
            logger.error("Не удалось скачать архив обновления")
            return True  # Продолжаем работу бота

        # Устанавливаем обновление
        logger.info(f"📦 Установка обновления {latest_short}...")
        if install_release(content):
            set_current_commit(latest_commit)
            logger.info(f"✅ Обновление до {latest_short} успешно установлено!")
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

        # Пытаемся импортировать бота поддержки (опционально)
        support_bot_main = None
        try:
            import support_bot  # Сначала проверяем что модуль существует
            from support_bot.main import main as support_main
            support_bot_main = support_main
            logger.info("🤖 Бот поддержки найден, запуск...")
        except ImportError:
            logger.info("ℹ️ Бот поддержки не установлен, запускаем только основной бот")
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
