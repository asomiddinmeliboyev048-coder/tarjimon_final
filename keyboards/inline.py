from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_USERNAME

def get_subscription_keyboard():
    channel_username = CHANNEL_USERNAME.lstrip("@").strip()
    channel_url = f"https://t.me/{channel_username}"

    keyboard = [
        # Obuna bo'lish tugmasiga kanal stikeri qo'shildi
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=channel_url)],
        # Tekshirish tugmasiga tasdiq belgisi qo'shildi
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_language_keyboard():
    """
    Tillar menyusi: Bayroqlar va chiroyli tartib bilan.
    Callback ma'lumotlari mavjud logikaga mos (lang_uz, lang_en va h.k.)
    """
    keyboard = [
        # 1-qator: O'zbek tili (asosiy til sifatida alohida)
        [InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="lang_uz")],
        
        # 2-qator: Ingliz va Rus tillari yonma-yon
        [
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton(text="🇷🇺 Russian", callback_data="lang_ru")
        ],
        
        # 3-qator: Turk va Koreys tillari yonma-yon
        [
            InlineKeyboardButton(text="🇹🇷 Turkish", callback_data="lang_tr"),
            InlineKeyboardButton(text="🇰🇷 Korean", callback_data="lang_ko")
        ],
        
        # 4-qator: Arab tili alohida
        [InlineKeyboardButton(text="🇸🇦 Arabic", callback_data="lang_ar")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_voice_keyboard(translation_id: str):
    """
    Tarjimadan keyin chiqadigan ovoz berish va tilni o'zgartirish tugmalari.
    """
    keyboard = [
        # Ovoz berish tugmasiga dinamik va quloqchin emojisi
        [InlineKeyboardButton(text="🎧 Ovozni eshitish 🔊", callback_data=f"voice_{translation_id}")],
        # Tilni o'zgartirish tugmasiga dunyo xaritasi emojisi
        [InlineKeyboardButton(text="🔄 Tilni o'zgartirish 🌍", callback_data="change_language")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_keyboard():
    """
    Admin paneli uchun stikerlar bilan bezatilgan tugmalar.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast (Xabar yuborish)", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="📈 Bugun", callback_data="admin_today"),
            InlineKeyboardButton(text="🔄 Jami tarjimalar", callback_data="admin_total_translations")
        ],
        [
            InlineKeyboardButton(text="🌐 Tillar boshqaruvi", callback_data="admin_languages")
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)