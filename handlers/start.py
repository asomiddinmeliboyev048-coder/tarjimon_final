from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_ID
from utils.database import Database
from keyboards.inline import get_subscription_keyboard, get_language_keyboard
from services.subscription import is_user_subscribed
from utils.logger import log_user_action

router = Router()
db = Database()

@router.message(Command("start"))
async def start_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    db.add_user(user_id, username, first_name)
    log_user_action(user_id, "start_command", f"{username} | {first_name}")

    if user_id == ADMIN_ID:
        await message.answer(
            "🌍 Tilni tanlang:",
            reply_markup=get_language_keyboard()
        )
        return

    is_subscribed = await is_user_subscribed(bot, user_id)
    if is_subscribed:
        await message.answer(
            "🌍 Tilni tanlang:",
            reply_markup=get_language_keyboard()
        )
    else:
        await message.answer(
            "Kanalga obuna bo'ling:",
            reply_markup=get_subscription_keyboard()
        )

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id

    log_user_action(user_id, "check_subscription_clicked")
    is_subscribed = await is_user_subscribed(bot, user_id)

    if is_subscribed:
        try:
            await callback.message.edit_text(
                "✅ Obuna tasdiqlandi! Tilni tanlang:" \
                "qaysi tilga tarjima bo'lishini tanlang:",
                reply_markup=get_language_keyboard()
            )
        except TelegramBadRequest:
            pass
    else:
        try:
            await callback.message.edit_text(
                "❌ Siz hali kanalga obuna bo'lmagansiz.\nKanalga obuna bo'ling:",
                reply_markup=get_subscription_keyboard()
            )
        except TelegramBadRequest:
            await callback.answer(
                "❌ Siz hali kanalga obuna bo'lmagansiz.",
                show_alert=True
            )

@router.callback_query(F.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    language = callback.data.split("_", 1)[1]

    log_user_action(user_id, "language_selected", f"lang: {language}")
    db.update_language(user_id, language)

    # Verify language was saved
    saved_lang = db.get_user_language(user_id)
    log_user_action(user_id, "language_saved_verify", f"requested: {language}, saved: {saved_lang}")

    from config import LANG_INSTRUCTIONS
    instruction_text = LANG_INSTRUCTIONS.get(language, "Tarjima qilish uchun matn yozing.")

    try:
        await callback.message.edit_text(instruction_text)
    except TelegramBadRequest:
        pass
