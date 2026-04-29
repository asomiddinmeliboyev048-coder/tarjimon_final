import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from utils.database import Database
from handlers import start, translate, admin
from utils.logger import logger, log_error

# Ensure required directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("cache/voice", exist_ok=True)


async def main():
    """Main bot entry point - optimized for high concurrency"""

    try:
        Database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not configured! Please set BOT_TOKEN in .env file")
        return

    bot = None
    try:
        # Optimize bot instance for high throughput
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Configure Dispatcher for parallel message processing
        # MemoryStorage is fastest for high-concurrency scenarios
        dp = Dispatcher(storage=MemoryStorage())
        
        # Register all handlers
        dp.include_router(start.router)
        dp.include_router(translate.router)
        dp.include_router(admin.router)

        logger.info("Bot initialized with optimized handlers for high concurrency")

        # Start polling with optimized settings for 30-40 concurrent users
        await dp.start_polling(
            bot,
            skip_updates=True,  # Skip pending updates on startup
            handle_signals=True,
            close_bot_session=True,
            timeout=30,  # Long polling timeout
            relaxation=0.1,  # Small delay between requests
            fast=True,  # Fast mode for handling updates
            allowed_updates=["message", "callback_query"]  # Only process necessary update types
        )
    except TelegramRetryAfter as e:
        logger.error(f"Flood control: retry after {e.retry_after} seconds")
        await asyncio.sleep(e.retry_after)
    except TelegramNetworkError as e:
        logger.error(f"Network error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during polling service: {e}")
        log_error(f"Polling service error: {e}")
    finally:
        if bot is not None:
            try:
                await bot.session.close()
                logger.info("Bot session closed")
            except Exception as e:
                logger.error(f"Error closing bot session: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
