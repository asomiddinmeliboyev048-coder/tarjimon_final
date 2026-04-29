import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# Channel configuration from environment variables
# CHANNEL_USER: username without @ (e.g., 'meliboyevdev')
# CHANNEL_LINK: full channel URL (e.g., 'https://t.me/meliboyevdev')
CHANNEL_USER = os.getenv("CHANNEL_USER", "meliboyevdev")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", f"https://t.me/{CHANNEL_USER}")

# Legacy support for old variable names
CHANNEL_USERNAME = CHANNEL_USER

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")

# Default source language for translation
DEFAULT_SOURCE_LANG = "uz"

# Languages mapping - target languages and Uzbek option for smart translations
LANGUAGES = {
    "uz": {"name": "O'zbek tili", "emoji": "🇺🇿", "voice": "uz-UZ-MadinaNeural"},
    "en": {"name": "Ingliz tili", "emoji": "��🇸", "voice": "en-US-GuyNeural"},
    "ru": {"name": "Rus tili", "emoji": "��🇺", "voice": "ru-RU-SvetlanaNeural"},
    "ko": {"name": "Koreys tili", "emoji": "🇰🇷", "voice": "ko-KR-SunHiNeural"},
    "tr": {"name": "Turk tili", "emoji": "🇹🇷", "voice": "tr-TR-AhmetNeural"},
    "ar": {"name": "Arab tili", "emoji": "🇦🇪", "voice": "ar-SA-HamedNeural"},
}

VOICE_MAP = {
    "uz": "uz-UZ-MadinaNeural",
    "en": "en-US-GuyNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ko": "ko-KR-SunHiNeural",
    "tr": "tr-TR-AhmetNeural",
    "ar": "ar-SA-HamedNeural",
}

# Languages supported by gTTS (for fallback)
GTTS_SUPPORTED_LANGS = {'en', 'ru', 'tr', 'ko', 'ar', 'uz'}  # uz may be attempted, but gTTS may still reject it

# Maximum text length for TTS (edge-tts limit)
MAX_TTS_TEXT_LENGTH = 1000

# Default fallback voice when specific language not found
DEFAULT_FALLBACK_VOICE = "en-US-GuyNeural"

# Language instructions shown after language selection
LANG_INSTRUCTIONS = {
    "en": "Siz matn yoki so'z yozing, men uni Ingliz tiliga tarjima qilib beraman.",
    "ru": "Siz matn yoki so'z yozing, men uni Rus tiliga tarjima qilib beraman.",
    "tr": "Siz matn yoki so'z yozing, men uni Turk tiliga tarjima qilib beraman.",
    "ko": "Siz matn yoki so'z yozing, men uni Koreys tiliga tarjima qilib beraman.",
    "ar": "Siz matn yoki so'z yozing, men uni Arab tiliga tarjima qilib beraman.",
    "uz": "Siz O'zbek tilini tanladingiz. Menga matn yuboring, men uni tarjima qilib beraman.",
}

# Translation settings
TRANSLATION_MAX_RETRIES = 3
TRANSLATION_TIMEOUT = 30  # seconds
