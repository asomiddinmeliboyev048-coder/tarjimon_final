"""
User Service - Core user management business logic.
"""

from utils.database import Database
from utils.logger import log_user_action, log_error, logger


class UserService:
    """
    Service class for handling user operations.
    Wraps database operations with logging.
    """
    
    def __init__(self):
        self.db = Database()
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """
        Register a new user or update existing user.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: Telegram first name
            
        Returns:
            True if successful
        """
        try:
            self.db.add_user(user_id, username, first_name)
            log_user_action(user_id, "user_registered", f"@{username}")
            return True
        except Exception as e:
            log_error(f"Error registering user: {e}", user_id)
            return False
    
    def set_user_language(self, user_id: int, language: str) -> bool:
        """
        Set user's preferred language.
        
        Args:
            user_id: Telegram user ID
            language: Language code
            
        Returns:
            True if successful
        """
        try:
            self.db.update_language(user_id, language)
            log_user_action(user_id, "language_set", f"lang: {language}")
            return True
        except Exception as e:
            log_error(f"Error setting user language: {e}", user_id)
            return False
    
    def get_user_language(self, user_id: int) -> str:
        """
        Get user's preferred language.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Language code or None
        """
        try:
            return self.db.get_user_language(user_id)
        except Exception as e:
            log_error(f"Error getting user language: {e}", user_id)
            return None
    
    def get_stats(self) -> dict:
        """
        Get overall bot statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            return self.db.get_stats()
        except Exception as e:
            log_error(f"Error getting stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'total_translations': 0,
                'language_stats': {},
                'today_translations': 0
            }
    
    def log_translation(self, user_id: int, source_text: str, translated_text: str, target_language: str) -> bool:
        """
        Log a translation event.
        
        Args:
            user_id: Telegram user ID
            source_text: Original text
            translated_text: Translated text
            target_language: Target language code
            
        Returns:
            True if successful
        """
        try:
            self.db.add_translation_log(user_id, source_text, translated_text, target_language)
            return True
        except Exception as e:
            log_error(f"Error logging translation: {e}", user_id)
            return False
