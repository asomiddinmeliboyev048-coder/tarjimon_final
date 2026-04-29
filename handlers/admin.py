from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_ID, LANGUAGES
from utils.database import Database
from keyboards.inline import get_admin_keyboard, get_language_keyboard
from utils.logger import log_user_action, log_error, logger

router = Router()
db = Database()

@router.message(Command("admin"))
async def admin_command(message: Message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        log_error(f"Unauthorized admin access attempt by user {user_id}")
        await message.answer("❌ Siz admin emassiz!")
        return
    
    log_user_action(user_id, "admin_access", "opened admin panel")
    await message.answer(
        "📊 Admin panel:",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    
    if user_id != ADMIN_ID:
        log_error(f"Unauthorized admin callback attempt by user {user_id}")
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    data = callback.data
    log_user_action(user_id, "admin_action", f"action: {data}")
    
    if data == "admin_stats":
        try:
            stats = db.get_stats()
            text = (
                "📊 <b>Statistika</b>\n\n"
                f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
                f"✅ Faol foydalanuvchilar: <b>{stats['active_users']}</b>\n"
                f"🔁 Jami tarjimalar: <b>{stats['total_translations']}</b>\n"
                f"📈 Bugun: <b>{stats['today_translations']}</b>"
            )
            logger.info(f"Admin {user_id} viewed stats: {stats}")
        except Exception as e:
            log_error(f"Error getting stats: {e}", user_id)
            text = "❌ Statistikani olishda xatolik yuz berdi"
        
        try:
            await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
    
    elif data == "admin_users":
        try:
            total = db.get_total_users()
            text = f"👥 <b>Foydalanuvchilar</b>\n\nJami: <b>{total}</b>"
            logger.info(f"Admin {user_id} viewed user count: {total}")
        except Exception as e:
            log_error(f"Error getting user count: {e}", user_id)
            text = "❌ Foydalanuvchilar sonini olishda xatolik"
        
        try:
            await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
    
    elif data == "admin_languages":
        try:
            lang_stats = db.get_language_stats()
            text = "🌍 <b>Til statistikasi</b>\n\n"
            for lang_code, count in lang_stats.items():
                emoji = LANGUAGES.get(lang_code, {}).get("emoji", "")
                name = LANGUAGES.get(lang_code, {}).get("name", "")
                text += f"{emoji} {name}: <b>{count}</b>\n"
            
            if not lang_stats:
                text += "Ma'lumot yo'q"
            
            logger.info(f"Admin {user_id} viewed language stats: {lang_stats}")
        except Exception as e:
            log_error(f"Error getting language stats: {e}", user_id)
            text = "❌ Til statistikalarini olishda xatolik"
        
        try:
            await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
    
    elif data == "admin_today":
        try:
            today_count = db.get_today_translations()
            text = f"📈 <b>Bugungi tarjimalar</b>\n\nJami: <b>{today_count}</b>"
            logger.info(f"Admin {user_id} viewed today's translations: {today_count}")
        except Exception as e:
            log_error(f"Error getting today's translations: {e}", user_id)
            text = "❌ Bugungi tarjimalarni olishda xatolik"
        
        try:
            await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
    
    elif data == "admin_total_translations":
        try:
            total = db.get_total_translations()
            text = f"🔁 <b>Jami tarjimalar</b>\n\nJami: <b>{total}</b>"
            logger.info(f"Admin {user_id} viewed total translations: {total}")
        except Exception as e:
            log_error(f"Error getting total translations: {e}", user_id)
            text = "❌ Jami tarjimalarni olishda xatolik"
        
        try:
            await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
    
    elif data == "admin_broadcast":
        try:
            await callback.message.edit_text(
                "🔔 Broadcast funksiyasi hozircha faollashtirilmagan.",
                reply_markup=get_admin_keyboard()
            )
        except TelegramBadRequest:
            pass
    
    elif data == "admin_back":
        try:
            await callback.message.edit_text(
                "📊 Admin panel:",
                reply_markup=get_admin_keyboard()
            )
        except TelegramBadRequest:
            pass

