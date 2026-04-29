import hashlib
import os
import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from deep_translator import GoogleTranslator

from config import ADMIN_ID, LANGUAGES, DEFAULT_SOURCE_LANG, TRANSLATION_TIMEOUT
from utils.database import Database
from keyboards.inline import get_language_keyboard, get_subscription_keyboard, get_voice_keyboard
from services.translator import detect_language
from utils.voice import generate_voice
from services.subscription import is_user_subscribed
from utils.logger import log_user_action, log_error, log_translation

router = Router()
db = Database()
translation_cache = {}

@router.callback_query(F.data == "change_language")
async def change_language_callback(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    try:
        await callback.message.edit_text(
            "🌍 Tilni tanlang:",
            reply_markup=get_language_keyboard()
        )
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("voice_"))
async def play_voice_callback(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    translation_id = callback.data.split("_", 1)[1]
    cached = translation_cache.get(translation_id)

    if not cached:
        log_error(f"Translation not found in cache: {translation_id}", user_id)
        await callback.answer(
            "❌ Tarjima matni topilmadi. Iltimos, matnni qayta yuboring.",
            show_alert=True
        )
        return

    translated_text = cached.get("text")
    translated_lang = cached.get("lang")  # Language of the translated text
    if not translated_text or not translated_lang:
        log_error("Invalid cached translation data", user_id)
        await callback.answer(
            "❌ Ovoz yaratishda xatolik yuz berdi.",
            show_alert=True
        )
        return

    loading_msg = await callback.message.answer("⏳ Ovoz tayyorlanmoqda...")
    try:
        log_user_action(user_id, "voice_requested", f"lang: {translated_lang}")

        voice_file_path = await generate_voice(translated_text, translated_lang)

        # Enhanced validation with detailed error checking
        if not voice_file_path:
            log_error(f"generate_voice returned None for {translated_lang}", user_id)
            # Show specific message for Uzbek (gTTS doesn't support it well)
            if translated_lang == 'uz':
                await loading_msg.edit_text(
                    "⚠️ Hozircha ushbu til uchun ovozli xizmatda uzilish bor.\n"
                    "Matnli tarjimadan foydalanib turing."
                )
            else:
                await loading_msg.edit_text(
                    "❌ Ovoz yaratishda texnik xatolik yuz berdi.\n"
                    "Iltimos, qayta urinib ko'ring."
                )
            return

        if not os.path.exists(voice_file_path):
            log_error(f"Voice file does not exist: {voice_file_path}", user_id)
            await loading_msg.edit_text("❌ Ovoz yaratishda texnik xatolik yuz berdi.")
            return

        if os.path.getsize(voice_file_path) == 0:
            log_error(f"Voice file is empty: {voice_file_path}", user_id)
            await loading_msg.edit_text("❌ Ovoz fayli bo'sh.\nIltimos, qayta urinib ko'ring.")
            return

        # File exists and has content, proceed with sending
        try:
            audio = FSInputFile(voice_file_path)
            await callback.message.answer_voice(voice=audio)
            await loading_msg.delete()
            translation_cache.pop(translation_id, None)
            log_user_action(user_id, "voice_sent", f"lang: {translated_lang}")

            # Clean up the file after successful sending
            try:
                os.remove(voice_file_path)
            except Exception as cleanup_error:
                log_error(f"Failed to cleanup voice file: {cleanup_error}", user_id)

        except Exception as send_error:
            log_error(f"Failed to send voice message: {send_error}", user_id)
            await loading_msg.edit_text("❌ Ovoz yuborishda xatolik yuz berdi.\nIltimos, qayta urinib ko'ring.")

    except Exception as e:
            log_error(f"Voice generation error: {e}", user_id)
            try:
                # Check if voice generation returned None (service unavailable for this language)
                if translated_lang == 'uz':
                    await loading_msg.edit_text(
                        "⚠️ Hozircha ushbu til uchun ovozli xizmatda uzilish bor.\n"
                        "Matnli tarjimadan foydalanib turing."
                    )
                else:
                    await loading_msg.edit_text(
                        "❌ Ovoz yaratishda texnik xatolik yuz berdi.\n"
                        "Iltimos, qayta urinib ko'ring."
                    )
            except Exception as edit_error:
                log_error(f"Failed to edit loading message: {edit_error}", user_id)
@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_translation(message: Message, bot: Bot):
    """
    Universal Translator Logic:
    - Uzbek mode (uz): User sends any foreign language text -> auto-detect -> translate to Uzbek
    - Other modes: User sends Uzbek text -> translate to selected target language
    - Smart fallback: If result equals input, suggest different language
    - No blocking: Always attempt translation, never reject text
    """
    user_id = message.from_user.id
    text_input = message.text.strip()

    if user_id != ADMIN_ID:
        is_subscribed = await is_user_subscribed(bot, user_id)
        if not is_subscribed:
            await message.answer(
                "Kanalga obuna bo'ling:",
                reply_markup=get_subscription_keyboard()
            )
            return

    user_language = db.get_user_language(user_id)
    log_user_action(user_id, "language_check", f"got: {user_language}, type: {type(user_language)}")

    if not user_language:
        log_user_action(user_id, "language_missing", f"language is None or empty")
        await message.answer(
            "🌍 Tilni tanlang:",
            reply_markup=get_language_keyboard()
        )
        return

    if user_language not in LANGUAGES:
        log_user_action(user_id, "language_invalid", f"language: {user_language}, valid: {list(LANGUAGES.keys())}")
        await message.answer(
            "🌍 Tilni tanlang:",
            reply_markup=get_language_keyboard()
        )
        return

    # Send instant reply to user - bot feels faster
    start_time = asyncio.get_event_loop().time()
    loading_msg = await message.answer("⏳ Tarjima qilinmoqda...")
    
    try:
        log_user_action(user_id, "translation_requested", f"target_lang: {user_language}")

        # Detect the source language of input text
        detected_source = await detect_language(text_input, user_id)
        log_user_action(user_id, "language_detected", f"detected: {detected_source}, target: {user_language}")

        # UNIVERSAL TRANSLATION LOGIC:
        # Case 1: User selected Uzbek mode (uz) -> Translate foreign text TO Uzbek
        # Case 2: User selected other language -> Translate Uzbek text TO that language
        
        translated_text = None
        actual_target_lang = user_language
        
        # Try translation - never block, always attempt
        try:
            # Smart translation: determine source and target
            if user_language == DEFAULT_SOURCE_LANG:  # Uzbek mode
                # User wants foreign text translated TO Uzbek
                if detected_source == DEFAULT_SOURCE_LANG:
                    # Input appears to be Uzbek, but let's try to translate anyway
                    # This handles false positives in detection
                    pass
                # Always translate to Uzbek in Uzbek mode
                translator = GoogleTranslator(source='auto', target=DEFAULT_SOURCE_LANG)
                actual_target_lang = DEFAULT_SOURCE_LANG
            else:
                # User selected a foreign language (en, ru, ko, tr, ar)
                # Assume input is Uzbek and translate TO selected language
                translator = GoogleTranslator(source=DEFAULT_SOURCE_LANG, target=user_language)
                actual_target_lang = user_language
            
            # Execute translation with timeout using asyncio.to_thread for non-blocking
            import sys
            if sys.version_info >= (3, 9):
                result = await asyncio.wait_for(
                    asyncio.to_thread(translator.translate, text_input),
                    timeout=TRANSLATION_TIMEOUT
                )
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, translator.translate, text_input),
                    timeout=TRANSLATION_TIMEOUT
                )
            
            if result and isinstance(result, str):
                translated_text = result.strip()
            
        except asyncio.TimeoutError:
            log_error(f"Translation timeout", user_id)
            try:
                await loading_msg.edit_text(
                    "⏳ Tarjima juda uzoq davom etdi.\n"
                    "Iltimos, keyinroq qayta urinib ko'ring."
                )
            except TelegramBadRequest:
                pass
            return

        except TranslationNotFound:
            log_error("Translation not found", user_id)
            try:
                await loading_msg.edit_text(
                    "❌ Bu matn uchun tarjima topilmadi.\n"
                    "Iltimos, boshqa matn bilan urinib ko'ring."
                )
            except TelegramBadRequest:
                pass
            return

        except (RequestError, LanguageNotSupportedException) as e:
            log_error(f"Translation API error: {e}", user_id)
            try:
                await loading_msg.edit_text(
                    "🔌 Tarjima xizmatida texnik nosozlik.\n"
                    "Iltimos, bir necha daqiqadan so'ng qayta urinib ko'ring."
                )
            except TelegramBadRequest:
                pass
            return

        except Exception as e:
            log_error(f"Translation unexpected error: {e}", user_id)
            try:
                await loading_msg.edit_text(
                    "❌ Tarjimada xatolik yuz berdi.\n"
                    "Iltimos, qayta urinib ko'ring yoki boshqa matn yuboring."
                )
            except TelegramBadRequest:
                pass
            return

        # SMART FALLBACK: Check if translation failed or equals input
        if not translated_text:
            try:
                await loading_msg.edit_text(
                    "❌ Tarjima qilishda texnik muammo yuz berdi.\n"
                    "Iltimos, boshqa matn bilan urinib ko'ring yoki keyinroq qayta urining.\n\n"
                    "Agar muammo takrorlansa, /start buyrug'ini yuborib, tilni qayta tanlang."
                )
            except TelegramBadRequest:
                pass
            return
        
        # Check if result is same as input (100% match)
        if translated_text.lower() == text_input.lower():
            log_user_action(user_id, "translation_echo_detected", f"same text returned")
            try:
                await loading_msg.edit_text(
                    f"🤔 Matn allaqachon {LANGUAGES.get(user_language, {}).get('name', 'tanlangan til')}da yoki "
                    f"tarjima qilib bo'lmaydi.\n\n"
                    f"Iltimos, boshqa tilda matn yuboring.\n\n"
                    f"Misol: Agar siz Ingliz tilini tanlagan bo'lsangiz, O'zbekcha matn yuboring."
                )
            except TelegramBadRequest:
                pass
            return
        
        # SUCCESS: Translation completed - edit the loading message
        emoji = LANGUAGES.get(actual_target_lang, {}).get("emoji", "🌍")
        translation_id = hashlib.md5(f"{translated_text}_{actual_target_lang}".encode()).hexdigest()
        translation_cache[translation_id] = {
            "text": translated_text,
            "lang": actual_target_lang,
        }
        
        # Calculate response time
        end_time = asyncio.get_event_loop().time()
        response_time = end_time - start_time
        log_user_action(user_id, "translation_response_time", f"{response_time:.3f}s")

        try:
            await loading_msg.edit_text(
                f"{emoji} Tarjima:\n{translated_text}",
                reply_markup=get_voice_keyboard(translation_id)
            )
        except TelegramBadRequest:
            # If edit fails, send as new message
            await message.answer(
                f"{emoji} Tarjima:\n{translated_text}",
                reply_markup=get_voice_keyboard(translation_id)
            )

        db.add_translation(user_id, text_input, translated_text, detected_source, actual_target_lang)
        log_translation(user_id, detected_source, actual_target_lang, True)

    except Exception as e:
        log_error(f"Translation error in handler: {e}", user_id)
        try:
            await loading_msg.edit_text(
                "❌ Xatolik yuz berdi.\n"
                "Iltimos, qayta urinib ko'ring yoki boshqa matn yuboring."
            )
        except TelegramBadRequest:
            await message.answer(
                "❌ Xatolik yuz berdi.\n"
                "Iltimos, qayta urinib ko'ring yoki boshqa matn yuboring."
            )


