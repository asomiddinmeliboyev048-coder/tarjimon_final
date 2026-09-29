import hashlib
import os
import asyncio
import time

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest

from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
TranslationNotFound,
RequestError,
LanguageNotSupportedException
)

from config import (
ADMIN_ID,
LANGUAGES,
DEFAULT_SOURCE_LANG,
TRANSLATION_TIMEOUT
)

from utils.database import Database
from keyboards.inline import (
get_language_keyboard,
get_subscription_keyboard,
get_voice_keyboard
)

from services.translator import detect_language
from utils.voice import generate_voice
from services.subscription import is_user_subscribed
from utils.logger import (
log_user_action,
log_error,
log_translation
)

router = Router()
db = Database()

# ============================================================

# TRANSLATION CACHE

# ============================================================

translation_cache = {}

# Alohida tarjima cache.

# Bir xil matnni qayta-qayta Google'ga yubormaslik uchun.

text_translation_cache = {}

# ============================================================

# GOOGLE RATE LIMIT PROTECTION

# ============================================================

# Google 5 request/second limitidan uzoqroq turish uchun

# requestlar orasida kamida 0.8 sekund interval.

GOOGLE_REQUEST_INTERVAL = 0.8

# Bir vaqtda faqat bitta Google request ishlaydi.

google_request_lock = asyncio.Lock()

# Oxirgi Google request vaqti.

last_google_request_time = 0.0

async def wait_for_google_rate_limit():
"""
Google Translate requestlari orasida xavfsiz interval saqlaydi.

```
Bu bot bir nechta foydalanuvchidan bir vaqtning o'zida
request olsa ham Google'ga requestlarni tartibli yuboradi.
"""

global last_google_request_time

async with google_request_lock:
    now = time.monotonic()
    elapsed = now - last_google_request_time

    if elapsed < GOOGLE_REQUEST_INTERVAL:
        await asyncio.sleep(
            GOOGLE_REQUEST_INTERVAL - elapsed
        )

    last_google_request_time = time.monotonic()
```

async def run_google_translation(translator, text):
"""
GoogleTranslator.translate() ni rate-limit va retry
himoyasi bilan ishga tushiradi.

```
Retry:
    1-urinish -> darhol
    2-urinish -> 2 soniya
    3-urinish -> 5 soniya
    4-urinish -> 10 soniya
"""

retry_delays = [0, 2, 5, 10]

last_error = None

for attempt, delay in enumerate(retry_delays, start=1):

    if delay > 0:
        await asyncio.sleep(delay)

    try:
        await wait_for_google_rate_limit()

        result = await asyncio.wait_for(
            asyncio.to_thread(
                translator.translate,
                text
            ),
            timeout=TRANSLATION_TIMEOUT
        )

        return result

    except asyncio.TimeoutError:
        raise

    except (
        RequestError,
        ConnectionError,
        OSError
    ) as e:

        last_error = e

        log_error(
            f"Google translation request failed "
            f"(attempt {attempt}/{len(retry_delays)}): {e}"
        )

        if attempt == len(retry_delays):
            raise

if last_error:
    raise last_error

return None
```

# ============================================================

# VOICE CALLBACK

# ============================================================

@router.callback_query(F.data == "change_language")
async def change_language_callback(
callback: CallbackQuery,
bot: Bot
):
await callback.answer()

```
try:
    await callback.message.edit_text(
        "🌍 Tilni tanlang:",
        reply_markup=get_language_keyboard()
    )

except TelegramBadRequest:
    pass
```

# ============================================================

# VOICE PLAY CALLBACK

# ============================================================

@router.callback_query(F.data.startswith("voice_"))
async def play_voice_callback(callback: CallbackQuery):

```
await callback.answer()

user_id = callback.from_user.id

translation_id = callback.data.split("_", 1)[1]

cached = translation_cache.get(translation_id)

if not cached:
    log_error(
        f"Translation not found in cache: {translation_id}",
        user_id
    )

    await callback.answer(
        "❌ Tarjima matni topilmadi. "
        "Iltimos, matnni qayta yuboring.",
        show_alert=True
    )

    return

translated_text = cached.get("text")
translated_lang = cached.get("lang")

if not translated_text or not translated_lang:
    log_error(
        "Invalid cached translation data",
        user_id
    )

    await callback.answer(
        "❌ Ovoz yaratishda xatolik yuz berdi.",
        show_alert=True
    )

    return

loading_msg = await callback.message.answer(
    "⏳ Ovoz tayyorlanmoqda..."
)

try:

    log_user_action(
        user_id,
        "voice_requested",
        f"lang: {translated_lang}"
    )

    voice_file_path = await generate_voice(
        translated_text,
        translated_lang
    )

    # ====================================================
    # VOICE GENERATION VALIDATION
    # ====================================================

    if not voice_file_path:

        log_error(
            f"generate_voice returned None "
            f"for {translated_lang}",
            user_id
        )

        if translated_lang == "uz":

            await loading_msg.edit_text(
                "⚠️ Hozircha ushbu til uchun "
                "ovozli xizmatda uzilish bor.\n"
                "Matnli tarjimadan foydalanib turing."
            )

        else:

            await loading_msg.edit_text(
                "❌ Ovoz yaratishda texnik xatolik yuz berdi.\n"
                "Iltimos, qayta urinib ko'ring."
            )

        return

    if not os.path.exists(voice_file_path):

        log_error(
            f"Voice file does not exist: "
            f"{voice_file_path}",
            user_id
        )

        await loading_msg.edit_text(
            "❌ Ovoz yaratishda texnik xatolik yuz berdi."
        )

        return

    if os.path.getsize(voice_file_path) == 0:

        log_error(
            f"Voice file is empty: "
            f"{voice_file_path}",
            user_id
        )

        await loading_msg.edit_text(
            "❌ Ovoz fayli bo'sh.\n"
            "Iltimos, qayta urinib ko'ring."
        )

        return

    # ====================================================
    # SEND VOICE
    # ====================================================

    try:

        audio = FSInputFile(voice_file_path)

        await callback.message.answer_voice(
            voice=audio
        )

        await loading_msg.delete()

        translation_cache.pop(
            translation_id,
            None
        )

        log_user_action(
            user_id,
            "voice_sent",
            f"lang: {translated_lang}"
        )

    except Exception as send_error:

        log_error(
            f"Failed to send voice message: "
            f"{send_error}",
            user_id
        )

        await loading_msg.edit_text(
            "❌ Ovoz yuborishda xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring."
        )

        return

    # ====================================================
    # CLEANUP VOICE FILE
    # ====================================================

    try:
        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)

    except Exception as cleanup_error:

        log_error(
            f"Failed to cleanup voice file: "
            f"{cleanup_error}",
            user_id
        )

except Exception as e:

    log_error(
        f"Voice generation error: {e}",
        user_id
    )

    try:

        if translated_lang == "uz":

            await loading_msg.edit_text(
                "⚠️ Hozircha ushbu til uchun "
                "ovozli xizmatda uzilish bor.\n"
                "Matnli tarjimadan foydalanib turing."
            )

        else:

            await loading_msg.edit_text(
                "❌ Ovoz yaratishda texnik xatolik yuz berdi.\n"
                "Iltimos, qayta urinib ko'ring."
            )

    except Exception as edit_error:

        log_error(
            f"Failed to edit loading message: "
            f"{edit_error}",
            user_id
        )
```

# ============================================================

# TEXT TRANSLATION

# ============================================================

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_translation(
message: Message,
bot: Bot
):
"""
Universal Translator Logic:

```
Uzbek mode:
    User sends foreign text -> Uzbek

Other modes:
    User sends Uzbek text -> selected language

Features:
    - Google rate-limit protection
    - Retry
    - Timeout
    - Translation cache
    - Language detection
    - Error handling
    - Voice support
"""

user_id = message.from_user.id

text_input = message.text.strip()

# ========================================================
# EMPTY TEXT
# ========================================================

if not text_input:

    await message.answer(
        "❌ Iltimos, matn yuboring."
    )

    return

# ========================================================
# SUBSCRIPTION CHECK
# ========================================================

if user_id != ADMIN_ID:

    is_subscribed = await is_user_subscribed(
        bot,
        user_id
    )

    if not is_subscribed:

        await message.answer(
            "Kanalga obuna bo'ling:",
            reply_markup=get_subscription_keyboard()
        )

        return

# ========================================================
# USER LANGUAGE
# ========================================================

user_language = db.get_user_language(user_id)

log_user_action(
    user_id,
    "language_check",
    f"got: {user_language}, "
    f"type: {type(user_language)}"
)

if not user_language:

    log_user_action(
        user_id,
        "language_missing",
        "language is None or empty"
    )

    await message.answer(
        "🌍 Tilni tanlang:",
        reply_markup=get_language_keyboard()
    )

    return

if user_language not in LANGUAGES:

    log_user_action(
        user_id,
        "language_invalid",
        f"language: {user_language}, "
        f"valid: {list(LANGUAGES.keys())}"
    )

    await message.answer(
        "🌍 Tilni tanlang:",
        reply_markup=get_language_keyboard()
    )

    return

# ========================================================
# LOADING
# ========================================================

start_time = asyncio.get_event_loop().time()

loading_msg = await message.answer(
    "⏳ Tarjima qilinmoqda..."
)

try:

    log_user_action(
        user_id,
        "translation_requested",
        f"target_lang: {user_language}"
    )

    # ====================================================
    # CHECK TRANSLATION CACHE
    # ====================================================

    cache_key = (
        f"{text_input.strip().lower()}|"
        f"{user_language}"
    )

    cached_translation = text_translation_cache.get(
        cache_key
    )

    if cached_translation:

        translated_text = cached_translation.get(
            "text"
        )

        detected_source = cached_translation.get(
            "source",
            "auto"
        )

        actual_target_lang = cached_translation.get(
            "target",
            user_language
        )

        log_user_action(
            user_id,
            "translation_cache_hit",
            f"target: {actual_target_lang}"
        )

    else:

        # =================================================
        # LANGUAGE DETECTION
        # =================================================

        try:

            await wait_for_google_rate_limit()

            detected_source = await asyncio.wait_for(
                detect_language(
                    text_input,
                    user_id
                ),
                timeout=TRANSLATION_TIMEOUT
            )

        except asyncio.TimeoutError:

            log_error(
                "Language detection timeout",
                user_id
            )

            await loading_msg.edit_text(
                "⏳ Tilni aniqlash juda uzoq davom etdi.\n"
                "Iltimos, keyinroq qayta urinib ko'ring."
            )

            return

        except Exception as detection_error:

            log_error(
                f"Language detection error: "
                f"{detection_error}",
                user_id
            )

            # Detection ishlamasa ham tarjimani to'xtatmaymiz.
            detected_source = "auto"

        log_user_action(
            user_id,
            "language_detected",
            f"detected: {detected_source}, "
            f"target: {user_language}"
        )

        # =================================================
        # SELECT TRANSLATION TARGET
        # =================================================

        actual_target_lang = user_language

        if user_language == DEFAULT_SOURCE_LANG:

            # Foreign -> Uzbek

            translator = GoogleTranslator(
                source="auto",
                target=DEFAULT_SOURCE_LANG
            )

            actual_target_lang = DEFAULT_SOURCE_LANG

        else:

            # Uzbek -> selected language

            translator = GoogleTranslator(
                source=DEFAULT_SOURCE_LANG,
                target=user_language
            )

            actual_target_lang = user_language

        # =================================================
        # TRANSLATE WITH RATE LIMIT + RETRY
        # =================================================

        try:

            result = await run_google_translation(
                translator,
                text_input
            )

        except asyncio.TimeoutError:

            log_error(
                "Translation timeout",
                user_id
            )

            await loading_msg.edit_text(
                "⏳ Tarjima juda uzoq davom etdi.\n"
                "Iltimos, keyinroq qayta urinib ko'ring."
            )

            return

        except TranslationNotFound:

            log_error(
                "Translation not found",
                user_id
            )

            await loading_msg.edit_text(
                "❌ Bu matn uchun tarjima topilmadi.\n"
                "Iltimos, boshqa matn bilan urinib ko'ring."
            )

            return

        except LanguageNotSupportedException as e:

            log_error(
                f"Language not supported: {e}",
                user_id
            )

            await loading_msg.edit_text(
                "❌ Tanlangan til hozircha "
                "qo'llab-quvvatlanmaydi."
            )

            return

        except RequestError as e:

            log_error(
                f"Google translation API error "
                f"after retries: {e}",
                user_id
            )

            await loading_msg.edit_text(
                "🔌 Tarjima xizmati vaqtincha "
                "band yoki cheklangan.\n\n"
                "⏳ Bir necha soniyadan keyin "
                "qayta urinib ko'ring."
            )

            return

        except Exception as e:

            log_error(
                f"Translation unexpected error: {e}",
                user_id
            )

            await loading_msg.edit_text(
                "❌ Tarjimada xatolik yuz berdi.\n"
                "Iltimos, qayta urinib ko'ring yoki "
                "boshqa matn yuboring."
            )

            return

        # =================================================
        # VALIDATE RESULT
        # =================================================

        if result and isinstance(result, str):

            translated_text = result.strip()

        else:

            translated_text = None

        if not translated_text:

            log_error(
                "Google returned empty translation",
                user_id
            )

            await loading_msg.edit_text(
                "❌ Tarjima qilishda texnik muammo "
                "yuz berdi.\n"
                "Iltimos, boshqa matn bilan urinib ko'ring."
            )

            return

        # =================================================
        # SAVE TO CACHE
        # =================================================

        text_translation_cache[cache_key] = {
            "text": translated_text,
            "source": detected_source,
            "target": actual_target_lang
        }

        # Cache juda katta bo'lib ketmasligi uchun
        # oxirgi 1000 ta tarjimani saqlaymiz.
        if len(text_translation_cache) > 1000:

            oldest_key = next(
                iter(text_translation_cache)
            )

            text_translation_cache.pop(
                oldest_key,
                None
            )

    # ====================================================
    # SMART FALLBACK
    # ====================================================

    if not translated_text:

        await loading_msg.edit_text(
            "❌ Tarjima qilishda texnik muammo yuz berdi.\n"
            "Iltimos, boshqa matn bilan urinib ko'ring "
            "yoki keyinroq qayta urining.\n\n"
            "Agar muammo takrorlansa, /start buyrug'ini "
            "yuborib, tilni qayta tanlang."
        )

        return

    # ====================================================
    # CHECK SAME RESULT
    # ====================================================

    if translated_text.lower() == text_input.lower():

        log_user_action(
            user_id,
            "translation_echo_detected",
            "same text returned"
        )

        try:

            await loading_msg.edit_text(
                f"🤔 Matn allaqachon "
                f"{LANGUAGES.get(user_language, {}).get('name', 'tanlangan til')}"
                f"da yoki tarjima qilib bo'lmaydi.\n\n"
                f"Iltimos, boshqa tilda matn yuboring.\n\n"
                f"Misol: Agar siz Ingliz tilini tanlagan "
                f"bo'lsangiz, O'zbekcha matn yuboring."
            )

        except TelegramBadRequest:
            pass

        return

    # ====================================================
    # SUCCESS
    # ====================================================

    emoji = LANGUAGES.get(
        actual_target_lang,
        {}
    ).get(
        "emoji",
        "🌍"
    )

    translation_id = hashlib.md5(
        f"{translated_text}_{actual_target_lang}".encode()
    ).hexdigest()

    translation_cache[translation_id] = {
        "text": translated_text,
        "lang": actual_target_lang
    }

    # ====================================================
    # RESPONSE TIME
    # ====================================================

    end_time = asyncio.get_event_loop().time()

    response_time = end_time - start_time

    log_user_action(
        user_id,
        "translation_response_time",
        f"{response_time:.3f}s"
    )

    # ====================================================
    # SEND RESULT
    # ====================================================

    try:

        await loading_msg.edit_text(
            f"{emoji} Tarjima:\n{translated_text}",
            reply_markup=get_voice_keyboard(
                translation_id
            )
        )

    except TelegramBadRequest:

        await message.answer(
            f"{emoji} Tarjima:\n{translated_text}",
            reply_markup=get_voice_keyboard(
                translation_id
            )
        )

    # ====================================================
    # DATABASE
    # ====================================================

    try:

        db.add_translation(
            user_id,
            text_input,
            translated_text,
            detected_source,
            actual_target_lang
        )

    except Exception as db_error:

        log_error(
            f"Failed to save translation "
            f"to database: {db_error}",
            user_id
        )

    # ====================================================
    # LOG SUCCESS
    # ====================================================

    log_translation(
        user_id,
        detected_source,
        actual_target_lang,
        True
    )

# ========================================================
# OUTER HANDLER ERROR
# ========================================================

except Exception as e:

    log_error(
        f"Translation error in handler: {e}",
        user_id
    )

    try:

        await loading_msg.edit_text(
            "❌ Xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring yoki "
            "boshqa matn yuboring."
        )

    except TelegramBadRequest:

        await message.answer(
            "❌ Xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring yoki "
            "boshqa matn yuboring."
        )
