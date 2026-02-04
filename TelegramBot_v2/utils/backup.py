"""
Backup и восстановление базы данных.

Модуль обеспечивает:
- Автоматическое резервное копирование SQLite
- Ротацию старых бэкапов
- Восстановление из бэкапа
- Расписание автоматических бэкапов
"""

import asyncio
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import structlog

from bot.config import settings


logger = structlog.get_logger()


# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Директория для бэкапов
BACKUP_DIR = settings.data_dir / "backups"

# Настройки ротации
MAX_DAILY_BACKUPS = 7       # Хранить 7 дневных бэкапов
MAX_WEEKLY_BACKUPS = 4      # Хранить 4 недельных бэкапа
MAX_MONTHLY_BACKUPS = 3     # Хранить 3 месячных бэкапа

# Расширения файлов
BACKUP_EXTENSION = ".sqlite.gz"


# ============================================================
# ФУНКЦИИ BACKUP
# ============================================================

def get_db_path() -> Optional[Path]:
    """
    Получить путь к файлу базы данных.
    
    Returns:
        Path к файлу БД или None
    """
    db_url = settings.database_url
    
    if "sqlite" not in db_url:
        logger.warning("Backup is only supported for SQLite databases")
        return None
    
    # Извлекаем путь из URL
    # sqlite+aiosqlite:///data/database.sqlite
    if ":///" in db_url:
        path_str = db_url.split("///")[1]
        return Path(path_str)
    elif "://" in db_url:
        path_str = db_url.split("://")[1]
        return Path(path_str)
    
    return None


def ensure_backup_dir():
    """Создать директорию для бэкапов если её нет."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def generate_backup_name(backup_type: str = "manual") -> str:
    """
    Сгенерировать имя файла бэкапа.
    
    Args:
        backup_type: Тип бэкапа (daily, weekly, monthly, manual)
        
    Returns:
        Имя файла бэкапа
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_{backup_type}_{timestamp}{BACKUP_EXTENSION}"


async def create_backup(
    backup_type: str = "manual",
    compress: bool = True,
) -> Optional[Path]:
    """
    Создать резервную копию базы данных.
    
    Args:
        backup_type: Тип бэкапа для именования
        compress: Сжимать ли файл gzip
        
    Returns:
        Path к созданному бэкапу или None при ошибке
    """
    db_path = get_db_path()
    if not db_path or not db_path.exists():
        logger.error("Database file not found", path=str(db_path))
        return None
    
    ensure_backup_dir()
    
    backup_name = generate_backup_name(backup_type)
    backup_path = BACKUP_DIR / backup_name
    
    try:
        if compress:
            # Сжимаем с gzip
            with open(db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Просто копируем
            backup_path = backup_path.with_suffix('.sqlite')
            shutil.copy2(db_path, backup_path)
        
        backup_size = backup_path.stat().st_size
        original_size = db_path.stat().st_size
        
        logger.info(
            "backup_created",
            path=str(backup_path),
            original_size=original_size,
            backup_size=backup_size,
            compression_ratio=round(backup_size / original_size, 2) if compress else 1.0,
        )
        
        return backup_path
        
    except Exception as e:
        logger.error("backup_failed", error=str(e), exc_info=True)
        return None


async def restore_backup(backup_path: Path) -> bool:
    """
    Восстановить базу данных из бэкапа.
    
    ВНИМАНИЕ: Эта операция перезапишет текущую базу данных!
    
    Args:
        backup_path: Путь к файлу бэкапа
        
    Returns:
        True если успешно
    """
    db_path = get_db_path()
    if not db_path:
        return False
    
    if not backup_path.exists():
        logger.error("Backup file not found", path=str(backup_path))
        return False
    
    try:
        # Создаём бэкап текущей БД на всякий случай
        current_backup = await create_backup("pre_restore")
        if not current_backup:
            logger.warning("Failed to create pre-restore backup")
        
        # Восстанавливаем
        if str(backup_path).endswith('.gz'):
            # Распаковываем gzip
            with gzip.open(backup_path, 'rb') as f_in:
                with open(db_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Просто копируем
            shutil.copy2(backup_path, db_path)
        
        logger.info("backup_restored", backup_path=str(backup_path))
        return True
        
    except Exception as e:
        logger.error("restore_failed", error=str(e), exc_info=True)
        return False


def list_backups() -> List[dict]:
    """
    Получить список всех бэкапов.
    
    Returns:
        Список словарей с информацией о бэкапах
    """
    ensure_backup_dir()
    
    backups = []
    for path in BACKUP_DIR.glob("backup_*"):
        if path.is_file():
            stat = path.stat()
            backups.append({
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_mtime),
            })
    
    # Сортируем по дате создания (новые первые)
    backups.sort(key=lambda x: x["created"], reverse=True)
    return backups


async def rotate_backups():
    """
    Ротация старых бэкапов.
    
    Удаляет бэкапы сверх лимитов по типам.
    """
    backups = list_backups()
    
    # Группируем по типам
    daily = [b for b in backups if "daily" in b["name"]]
    weekly = [b for b in backups if "weekly" in b["name"]]
    monthly = [b for b in backups if "monthly" in b["name"]]
    
    deleted_count = 0
    
    # Удаляем лишние дневные
    for backup in daily[MAX_DAILY_BACKUPS:]:
        try:
            Path(backup["path"]).unlink()
            deleted_count += 1
        except Exception as e:
            logger.error("failed_to_delete_backup", path=backup["path"], error=str(e))
    
    # Удаляем лишние недельные
    for backup in weekly[MAX_WEEKLY_BACKUPS:]:
        try:
            Path(backup["path"]).unlink()
            deleted_count += 1
        except Exception as e:
            logger.error("failed_to_delete_backup", path=backup["path"], error=str(e))
    
    # Удаляем лишние месячные
    for backup in monthly[MAX_MONTHLY_BACKUPS:]:
        try:
            Path(backup["path"]).unlink()
            deleted_count += 1
        except Exception as e:
            logger.error("failed_to_delete_backup", path=backup["path"], error=str(e))
    
    if deleted_count > 0:
        logger.info("backups_rotated", deleted=deleted_count)


# ============================================================
# РАСПИСАНИЕ АВТОМАТИЧЕСКИХ БЭКАПОВ
# ============================================================

class BackupScheduler:
    """Планировщик автоматических бэкапов."""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить планировщик."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("backup_scheduler_started")
    
    async def stop(self):
        """Остановить планировщик."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("backup_scheduler_stopped")
    
    async def _run_scheduler(self):
        """Основной цикл планировщика."""
        while self._running:
            try:
                now = datetime.now()
                
                # Дневной бэкап в 3:00
                if now.hour == 3 and now.minute == 0:
                    await self._daily_backup()
                
                # Недельный бэкап в воскресенье в 4:00
                if now.weekday() == 6 and now.hour == 4 and now.minute == 0:
                    await self._weekly_backup()
                
                # Месячный бэкап 1-го числа в 5:00
                if now.day == 1 and now.hour == 5 and now.minute == 0:
                    await self._monthly_backup()
                
                # Ждём 1 минуту
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("backup_scheduler_error", error=str(e))
                await asyncio.sleep(60)
    
    async def _daily_backup(self):
        """Создать дневной бэкап."""
        backup = await create_backup("daily")
        if backup:
            await rotate_backups()
    
    async def _weekly_backup(self):
        """Создать недельный бэкап."""
        await create_backup("weekly")
        await rotate_backups()
    
    async def _monthly_backup(self):
        """Создать месячный бэкап."""
        await create_backup("monthly")
        await rotate_backups()


# Глобальный планировщик
backup_scheduler = BackupScheduler()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def get_backup_stats() -> dict:
    """
    Получить статистику бэкапов.
    
    Returns:
        Словарь со статистикой
    """
    backups = list_backups()
    
    total_size = sum(b["size_bytes"] for b in backups)
    
    return {
        "total_backups": len(backups),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "latest_backup": backups[0] if backups else None,
        "oldest_backup": backups[-1] if backups else None,
        "by_type": {
            "daily": len([b for b in backups if "daily" in b["name"]]),
            "weekly": len([b for b in backups if "weekly" in b["name"]]),
            "monthly": len([b for b in backups if "monthly" in b["name"]]),
            "manual": len([b for b in backups if "manual" in b["name"]]),
        },
    }


async def cleanup_old_backups(days: int = 30):
    """
    Удалить бэкапы старше N дней.
    
    Args:
        days: Количество дней
    """
    cutoff = datetime.now() - timedelta(days=days)
    backups = list_backups()
    deleted = 0
    
    for backup in backups:
        if backup["created"] < cutoff:
            try:
                Path(backup["path"]).unlink()
                deleted += 1
            except Exception as e:
                logger.error("failed_to_delete_old_backup", error=str(e))
    
    if deleted > 0:
        logger.info("old_backups_cleaned", deleted=deleted, older_than_days=days)
