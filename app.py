import asyncio
import os
import sys
import subprocess
from pathlib import Path
import logging
import shutil
from datetime import datetime
from typing import Optional

# Настройка базового логирования для отладки запуска
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DeployShim")

# Определяем пути
project_root = Path(__file__).resolve().parent
bot_dir = project_root / "TelegramBot_v2"
backup_dir = project_root / ".backup"

# Репозиторий GitHub
GITHUB_REPO_URL = "https://github.com/Prot1vn1kk/TZshnik.git"
BRANCH_NAME = "main"


# ============================================================
# GIT UPDATE FUNCTIONS
# ============================================================

def run_git_command(command: list, timeout: int = 60) -> tuple[bool, str, str]:
    """
    Выполняет git команду и возвращает результат.

    Args:
        command: Git команда как список
        timeout: Таймаут выполнения

    Returns:
        Tuple[success, stdout, stderr]
    """
    try:
        result = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timeout"
    except Exception as e:
        return False, "", str(e)


def check_git_repository() -> bool:
    """Проверяет, является ли директория git репозиторием."""
    git_dir = project_root / ".git"
    return git_dir.exists() and git_dir.is_dir()


def init_git_repo() -> bool:
    """Инициализирует git репозиторий и клонирует с GitHub."""
    logger.info("📦 Инициализация git репозитория...")

    try:
        # Проверяем, есть ли уже .git директория
        if check_git_repository():
            logger.info("✅ Git репозиторий уже инициализирован")
            # Убеждаемся, что правильный remote
            success, _, _ = run_git_command(["git", "remote", "-v"])
            if success and GITHUB_REPO_URL not in _:
                logger.info("⚙️ Настройка remote...")
                run_git_command(["git", "remote", "set-url", "origin", GITHUB_REPO_URL])
            return True

        # Клонируем репозиторий во временную директорию
        temp_dir = project_root.parent / "TZshnik_temp"

        logger.info(f"📥 Клонирование репозитория из {GITHUB_REPO_URL}...")
        success, stdout, stderr = run_git_command([
            "git", "clone", "--depth", "1", "--branch", BRANCH_NAME,
            GITHUB_REPO_URL, str(temp_dir)
        ], timeout=120)

        if not success:
            logger.error(f"❌ Ошибка клонирования: {stderr}")
            return False

        # Копируем .git директорию
        temp_git = temp_dir / ".git"
        if temp_git.exists():
            target_git = project_root / ".git"
            if target_git.exists():
                shutil.rmtree(target_git)
            shutil.copytree(temp_git, target_git)
            logger.info("✅ Git репозиторий инициализирован")
        else:
            logger.warning("⚠️ .git директория не найдена в клонированном репозитории")

        # Удаляем временную директорию
        shutil.rmtree(temp_dir, ignore_errors=True)

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации git: {e}")
        return False


def create_backup() -> Optional[Path]:
    """Создаёт бэкап текущих файлов перед обновлением."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"backup_{timestamp}"

    try:
        # Исключаем из бэкапа: виртуальное окружение, кэш, временные файлы
        exclude_dirs = {
            "venv", "__pycache__", ".pytest_cache",
            "data/temp_files", ".backup"
        }

        backup_path.mkdir(parents=True, exist_ok=True)

        logger.info("💾 Создание бэкапа...")

        for item in bot_dir.iterdir():
            if item.name in exclude_dirs:
                continue
            if item.is_dir():
                dest = backup_path / item.name
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".pytest_cache"
                ))
            elif item.is_file():
                shutil.copy2(item, backup_path / item.name)

        logger.info(f"✅ Бэкап создан: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа: {e}")
        return None


def restore_backup(backup_path: Path) -> bool:
    """Восстанавливает файлы из бэкапа."""
    try:
        logger.info("🔄 Восстановление из бэкапа...")

        # Восстанавливаем файлы
        for item in backup_path.iterdir():
            dest = bot_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()

            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        logger.info("✅ Восстановление завершено")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка восстановления: {e}")
        return False


def check_updates() -> tuple[bool, str]:
    """
    Проверяет наличие обновлений на GitHub.

    Returns:
        Tuple[has_updates, commit_hash]
    """
    logger.info("🔍 Проверка обновлений...")

    # Fetch с удалённого репозитория
    success, _, stderr = run_git_command([
        "git", "fetch", "origin", BRANCH_NAME
    ])

    if not success:
        logger.warning(f"⚠️ Не удалось проверить обновления: {stderr}")
        return False, ""

    # Сравниваем коммиты
    success, stdout, _ = run_git_command([
        "git", "rev-parse", f"origin/{BRANCH_NAME}"
    ])

    if not success:
        return False, ""

    remote_commit = stdout.strip()

    success, stdout, _ = run_git_command(["git", "rev-parse", "HEAD"])

    if not success:
        return False, ""

    local_commit = stdout.strip()

    has_updates = remote_commit != local_commit

    if has_updates:
        logger.info(f"📦 Доступно обновление: {remote_commit[:8]}")
    else:
        logger.info("✅ Бот актуален")

    return has_updates, remote_commit


def pull_updates() -> bool:
    """Подтягивает обновления с GitHub."""
    logger.info("⬇️ Загрузка обновлений...")

    # Сбрасываем локальные изменения в конфигах (если есть)
    run_git_command(["git", "reset", "--hard", "HEAD"])

    # Переключаемся на ветку
    success, _, stderr = run_git_command([
        "git", "checkout", BRANCH_NAME
    ])

    if not success:
        logger.error(f"❌ Ошибка переключения ветки: {stderr}")
        return False

    # Делаем pull
    success, stdout, stderr = run_git_command([
        "git", "pull", "origin", BRANCH_NAME
    ], timeout=120)

    if not success:
        logger.error(f"❌ Ошибка загрузки: {stderr}")
        return False

    logger.info("✅ Обновления загружены")

    # Показываем что изменилось
    success, stdout, _ = run_git_command([
        "git", "log", "--oneline", "HEAD@{1}..HEAD"
    ])

    if success and stdout.strip():
        logger.info("📝 Последние изменения:")
        for line in stdout.strip().split('\n')[:5]:  # Показываем до 5 коммитов
            logger.info(f"   • {line}")

    return True


def install_requirements() -> bool:
    """Обновляет зависимости Python."""
    requirements_file = bot_dir / "requirements.txt"

    if not requirements_file.exists():
        logger.info("📦 requirements.txt не найден, пропускаем...")
        return True

    logger.info("📦 Обновление зависимостей...")

    try:
        # Проверяем наличие pip
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.warning("⚠️ pip недоступен, пропускаем установку зависимостей")
            return True

        # Устанавливаем зависимости
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
            timeout=300  # 5 минут
        )

        if result.returncode != 0:
            logger.warning(f"⚠️ Некоторые зависимости не установлены: {result.stderr[-200:]}")
        else:
            logger.info("✅ Зависимости обновлены")

        return True

    except Exception as e:
        logger.warning(f"⚠️ Ошибка установки зависимостей: {e}")
        return True  # Не критичная ошибка, продолжаем


def auto_update() -> bool:
    """
    Основная функция автообновления.

    Returns:
        True если обновление прошло успешно или не требуется
    """
    try:
        # 1. Проверяем/инициализируем git
        if not check_git_repository():
            if not init_git_repo():
                logger.warning("⚠️ Не удалось инициализировать git, работаем без автообновления")
                return True

        # 2. Проверяем обновления
        has_updates, commit_hash = check_updates()

        if not has_updates:
            return True

        # 3. Создаём бэкап
        backup_path = create_backup()
        if not backup_path:
            logger.warning("⚠️ Не удалось создать бэкап, обновление отменено")
            return True

        # 4. Загружаем обновления
        if not pull_updates():
            logger.error("❌ Ошибка загрузки обновлений")
            restore_backup(backup_path)
            return False

        # 5. Обновляем зависимости
        install_requirements()

        # 6. Очищаем старые бэкапы (оставляем только последние 3)
        try:
            backups = sorted(backup_dir.glob("backup_*"), reverse=True)[3:]
            for old_backup in backups:
                shutil.rmtree(old_backup, ignore_errors=True)
        except Exception:
            pass

        logger.info("✅ Обновление завершено успешно!")
        return True

    except Exception as e:
        logger.error(f"❌ Критическая ошибка автообновления: {e}")
        return True  # Продолжаем работу бота даже если обновление failed


def prepare_environment():
    """Подготовка окружения перед запуском."""
    # Создаем папку data внутри TelegramBot_v2, если её нет
    data_dir = bot_dir / "data"
    exports_dir = bot_dir / "exports"

    for folder in [data_dir, exports_dir]:
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Создана директория: {folder}")
            except Exception as e:
                logger.error(f"❌ Не удалось создать директорию {folder}: {e}")

        # Проверяем права на запись
        if os.access(folder, os.W_OK):
            logger.info(f"✅ Доступ на запись в {folder} подтвержден")
        else:
            logger.warning(f"⚠️ Нет прав на запись в {folder}! Попытка исправить...")
            try:
                os.chmod(folder, 0o777)
                logger.info(f"✅ Права изменены на 777 для {folder}")
            except Exception as e:
                logger.error(f"❌ Не удалось изменить права для {folder}: {e}")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Запуск шим-скрипта деплоя с автообновлением...")
    logger.info("=" * 60)

    # 1. Проверяем и применяем обновления
    try:
        auto_update()
    except Exception as e:
        logger.warning(f"⚠️ Автообновление пропущено из-за ошибки: {e}")

    # 2. Готовим папки
    prepare_environment()

    # 3. Импортируем и запускаем бота
    try:
        # Импортируем именно из пакета TelegramBot_v2
        from bot.main import main

        logger.info("🤖 Запуск основного модуля бота...")
        asyncio.run(main())
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта. Убедитесь, что папка TelegramBot_v2 существует. Ошибка: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("⛔ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)
