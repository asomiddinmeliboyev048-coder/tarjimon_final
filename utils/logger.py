import logging
import os
from datetime import datetime

# Create logs directory
os.makedirs("logs", exist_ok=True)

# Configure main logger
logger = logging.getLogger("tarjimon_bot")
logger.setLevel(logging.DEBUG)

# File handler for all logs
file_handler = logging.FileHandler("logs/activity.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# File handler for errors only
error_handler = logging.FileHandler("logs/errors.log", encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(file_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    "%(levelname)s - %(message)s"
)
console_handler.setFormatter(console_formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)

def log_user_action(user_id: int, action: str, details: str = ""):
    """Log user actions"""
    msg = f"User {user_id}: {action}"
    if details:
        msg += f" - {details}"
    logger.info(msg)

def log_translation(user_id: int, source_lang: str, target_lang: str, success: bool, duration: float = None, cached: bool = False):
    """Log translation events"""
    status = "SUCCESS" if success else "FAILED"
    cache_status = " (CACHED)" if cached else ""
    duration_str = f" in {duration:.2f}s" if duration else ""
    logger.info(f"Translation {status}: User {user_id} [{source_lang}→{target_lang}]{cache_status}{duration_str}")

def log_error(error_msg: str, user_id: int = None):
    """Log errors"""
    if user_id:
        logger.error(f"User {user_id}: {error_msg}")
    else:
        logger.error(error_msg)

def log_voice_generation(user_id: int, lang: str, success: bool, cached: bool = False, duration: float = None):
    """Log voice generation events"""
    status = "SUCCESS" if success else "FAILED"
    cache_status = " (CACHED)" if cached else ""
    duration_str = f" in {duration:.2f}s" if duration else ""
    logger.info(f"Voice {status}: User {user_id} [{lang}]{cache_status}{duration_str}")

