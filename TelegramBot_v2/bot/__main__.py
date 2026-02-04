"""
Точка входа для запуска бота как модуля.
python -m bot
"""

from bot.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
