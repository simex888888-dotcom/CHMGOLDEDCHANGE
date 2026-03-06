"""
CHM GOLD EXCHANGE Telegram Bot entry point.
Pure bot mode — no Mini App required.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `bot.*` and sibling packages resolve
# regardless of how the script is invoked (python bot/main.py  OR  python -m bot.main)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from bot.handlers.admin import router as admin_router
from bot.handlers.client import router as client_router
from bot.scheduler import setup_scheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# MemoryStorage for FSM (use Redis for multi-instance production)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


async def main() -> None:
    # Admin router first (more specific filters)
    dp.include_router(admin_router)
    # Client router (general users)
    dp.include_router(client_router)

    # Setup APScheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started — posts at 10:00 and 20:00 MSK")

    # Auto-create tables for SQLite dev environment
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./chmgold.db")
    if "sqlite" in db_url:
        from database.engine import create_tables
        await create_tables()
        logger.info("SQLite tables created/verified")

    logger.info("Starting CHM GOLD EXCHANGE Bot (polling mode)")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
