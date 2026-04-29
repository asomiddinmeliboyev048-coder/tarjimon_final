import json
import os
from datetime import datetime, date
from utils.logger import logger

class Database:
    def __init__(self, db_file="data.json"):
        self.db_file = db_file
        self.data = self._load_data()
        self._ensure_structure()

    def _load_data(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load database: {e}")
                return {}
        return {}

    def _save_data(self):
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save database: {e}")

    def _ensure_structure(self):
        if "users" not in self.data:
            self.data["users"] = {}
        if "translations" not in self.data:
            self.data["translations"] = {}
        if "stats" not in self.data:
            self.data["stats"] = {
                "total_users": 0,
                "active_users": 0,
                "total_translations": 0,
                "today_translations": 0
            }
        self._save_data()

    def add_user(self, user_id, username, first_name, language=None):
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "language": language
            }
            self.data["stats"]["total_users"] += 1
            self._save_data()
            logger.info(f"New user added: {user_id}, language: {language}")
        else:
            self.data["users"][user_id]["last_active"] = datetime.now().isoformat()
            self.data["users"][user_id]["username"] = username
            self.data["users"][user_id]["first_name"] = first_name
            self._save_data()

    def get_stats(self):
        # Update active users (users active in last 30 days)
        active_count = 0
        for user in self.data["users"].values():
            last_active = datetime.fromisoformat(user["last_active"])
            if (datetime.now() - last_active).days <= 30:
                active_count += 1
        self.data["stats"]["active_users"] = active_count

        # Update today translations
        today = date.today().isoformat()
        today_count = sum(1 for t in self.data["translations"].values() if t.get("date") == today)
        self.data["stats"]["today_translations"] = today_count

        self._save_data()
        return self.data["stats"]

    def get_total_users(self):
        return self.data["stats"]["total_users"]

    def get_language_stats(self):
        stats = {}
        for user in self.data["users"].values():
            lang = user.get("language")
            if lang:
                stats[lang] = stats.get(lang, 0) + 1
        return stats

    def get_today_translations(self):
        return self.data["stats"]["today_translations"]

    def get_total_translations(self):
        return self.data["stats"]["total_translations"]

    def add_translation(self, user_id, text, translated_text, source_lang, target_lang):
        translation_id = str(len(self.data["translations"]) + 1)
        self.data["translations"][translation_id] = {
            "user_id": str(user_id),
            "text": text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        self.data["stats"]["total_translations"] += 1
        self._save_data()

    def update_language(self, user_id, language):
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "username": None,
                "first_name": None,
                "joined_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "language": language
            }
        else:
            self.data["users"][user_id]["language"] = language
            self.data["users"][user_id]["last_active"] = datetime.now().isoformat()
        self._save_data()
        logger.info(f"User {user_id} language updated to: {language}")

    def get_user_language(self, user_id):
        user_id = str(user_id)
        # Reload data from disk to ensure we have latest changes from other instances
        self.data = self._load_data()
        self._ensure_structure()
        user = self.data["users"].get(user_id, {})
        return user.get("language")

    def get_user(self, user_id):
        return self.data["users"].get(str(user_id))