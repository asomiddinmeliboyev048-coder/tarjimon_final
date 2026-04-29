from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from config import CHANNEL_ID, CHANNEL_USERNAME, ADMIN_ID
from utils.logger import log_error

async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True

    if CHANNEL_ID:
        chat_id = CHANNEL_ID
    else:
        chat_id = f"@{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME else ""

    if not chat_id:
        log_error("CHANNEL_ID and CHANNEL_USERNAME are not configured")
        return True

    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramBadRequest as e:
        log_error(f"Subscription check error: {e}", user_id)
        return False
    except Exception as e:
        log_error(f"Unexpected subscription error: {e}", user_id)
        return False

