"""Entry point for `python -m TelegramBot_v2.support_bot`."""

import asyncio
import sys
from pathlib import Path

# Ensure TelegramBot_v2 is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from support_bot.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот поддержки остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
