import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiohttp import web

from config import BOT_TOKEN
from utils.database import Database
from handlers import start, translate, admin
from utils.logger import logger, log_error

# Ensure required directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("cache/voice", exist_ok=True)

# Get port from environment variable (Render sets this) or default to 8080
PORT = int(os.getenv('PORT', 8080))


async def health_check(request):
    """Health check endpoint for UptimeRobot and Render"""
    return web.Response(text="Bot is running!")


async def run_web_server():
    """Run aiohttp web server for keeping the service alive"""
    app = web.Application()
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Web server started on port {PORT}")
    
    # Keep the server running
    while True:
        await asyncio.sleep(3600)  # Sleep for 1 hour, effectively forever


async def run_bot():
    """Run the Telegram bot with polling"""
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
            handle_signals=False,  # Disable signal handling since we run in parallel with web server
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


async def main():
    """Main entry point - run bot and web server in parallel"""
    logger.info("Starting bot and web server in parallel...")
    
    # Create tasks for both services
    bot_task = asyncio.create_task(run_bot())
    web_task = asyncio.create_task(run_web_server())
    
    # Run both tasks concurrently
    await asyncio.gather(bot_task, web_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
