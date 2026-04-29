"""
Translation Service - Core translation business logic with caching and retry.
"""

from services.translator import translate_text, get_cache_stats, clear_translation_cache
from utils.logger import log_translation, log_error, logger


class TranslationService:
    """
    Service class for handling translation operations.
    Provides caching, retry logic, and logging.
    """
    
    @staticmethod
    async def translate(text: str, target_lang: str, user_id: int = None) -> tuple[str, str] | None:
        """
        Translate text with full error handling and logging.
        
        Args:
            text: Text to translate
            target_lang: Target language code
            user_id: Optional user ID for logging
            
        Returns:
            Tuple (translated_text, actual_target_lang) or None if failed
        """
        if not text or not text.strip():
            log_error("Empty text provided for translation", user_id)
            return None
            
        try:
            result = await translate_text(text, target_lang, user_id)
            return result
        except Exception as e:
            log_error(f"Translation service error: {e}", user_id)
            return None
    
    @staticmethod
    def get_cache_info():
        """Get translation cache statistics"""
        return get_cache_stats()
    
    @staticmethod
    def clear_cache():
        """Clear translation cache"""
        clear_translation_cache()
        logger.info("Translation cache cleared")
