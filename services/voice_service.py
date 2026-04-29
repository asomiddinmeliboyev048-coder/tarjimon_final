"""
Voice Service - Core voice generation business logic with caching.
"""

from utils.voice import generate_voice, get_cache_stats, cleanup_old_cache
from utils.logger import log_voice_generation, log_error, logger


class VoiceService:
    """
    Service class for handling voice generation operations.
    Provides caching, cleanup, and logging.
    """
    
    @staticmethod
    async def generate(text: str, target_lang: str, user_id: int = None) -> str:
        """
        Generate voice with full error handling and logging.
        
        Args:
            text: Text to convert to speech
            target_lang: Target language code
            user_id: Optional user ID for logging
            
        Returns:
            File path to generated voice or None if failed
        """
        if not text or not text.strip():
            log_error("Empty text provided for voice generation", user_id)
            return None
            
        try:
            result = await generate_voice(text, target_lang)
            return result
        except Exception as e:
            log_error(f"Voice service error: {e}", user_id)
            return None
    
    @staticmethod
    def get_cache_info():
        """Get voice cache statistics"""
        return get_cache_stats()
    
    @staticmethod
    def cleanup_cache(max_age_days: int = 7):
        """Clean up old voice cache files"""
        deleted = cleanup_old_cache(max_age_days)
        logger.info(f"Voice cache cleanup: {deleted} files deleted")
        return deleted
