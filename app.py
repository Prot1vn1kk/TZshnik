import asyncio
import os
import sys
from pathlib import Path
import logging

# Настройка базового логирования для отладки запуска
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DeployShim")

# Определяем пути
project_root = Path(__file__).resolve().parent
bot_dir = project_root / "TelegramBot_v2"

# Добавляем пути в sys.path для корректных импортов
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(bot_dir))

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

if __name__ == "__main__":
    logger.info("🚀 Запуск шим-скрипта деплоя...")
    
    # 1. Готовим папки
    prepare_environment()
    
    # 2. Импортируем и запускаем бота
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
