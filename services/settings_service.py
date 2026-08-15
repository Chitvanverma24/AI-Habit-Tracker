"""

AI Habit Tracker SaaS - System Settings Service
Manages live global platform settings with Supabase persistence
and local fallback redundancy.

"""

import json
import os
from typing import Dict, Any, Optional
import streamlit as st
from database import get_db
from auth import auth

# Fallback settings JSON file path
FALLBACK_FILE = os.path.join(os.path.dirname(__file__), "system_settings.json")

# Core Default Global System Settings
DEFAULT_SETTINGS: Dict[str, Any] = {
    "maintenance_mode": False,
    "registration_enabled": True,
    "ai_enabled": True,
    "selected_ai_model": "gemini-2.5-flash",
    "allow_journal": True,
    "allow_habits": True,
    "allow_achievements": True,
    "allow_admin_panel": True,
    "system_name": "AI Habit Tracker",
    "system_logo": "🎯",
    "support_email": "support@habittracker.ai",
    "default_timezone": "UTC"
}


def _load_local_fallback() -> Dict[str, Any]:
    """Load settings from local JSON file fallback."""
    if os.path.exists(FALLBACK_FILE):
        try:
            with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_SETTINGS.copy()
                merged.update(data)
                return merged
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def _save_local_fallback(settings: Dict[str, Any]) -> None:
    """Save settings to local JSON file fallback."""
    try:
        os.makedirs(os.path.dirname(FALLBACK_FILE), exist_ok=True)
        with open(FALLBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


@st.cache_data(ttl=30, show_spinner=False)
def _cached_fetch_settings() -> Dict[str, Any]:
    """Cached fetch with 2-second TTL for live cross-session synchronization."""
    settings = DEFAULT_SETTINGS.copy()

    # Try Supabase first
    try:
        db = get_db()
        response = db.table("system_settings").select("key, value").execute()
        if response and response.data:
            for row in response.data:
                k = row.get("key")
                v = row.get("value")
                if k:
                    if isinstance(v, str):
                        try:
                            v = json.loads(v)
                        except Exception:
                            pass
                    settings[k] = v
            _save_local_fallback(settings)
            return settings
    except Exception:
        pass

    return _load_local_fallback()


class SettingsService:
    """Production Settings Service managing live configuration."""

    @staticmethod
    def fetch_settings_from_db() -> Dict[str, Any]:
        """Fetch settings from database or local fallback."""
        return _cached_fetch_settings()

    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """Return all current global settings live."""
        return _cached_fetch_settings()

    @classmethod
    def get_setting(cls, key: str, default: Any = None) -> Any:
        """Get a single setting by key with fallback default."""
        settings = cls.get_all_settings()
        if key in settings:
            return settings[key]
        return DEFAULT_SETTINGS.get(key, default)

    @classmethod
    def update_setting(cls, key: str, value: Any) -> tuple[bool, str]:
        """Update a single global setting with permission check & Supabase persistence."""
        if not auth.is_admin():
            return False, "Permission Denied: Only Admin users can modify system settings."

        try:
            current = _load_local_fallback()
            current[key] = value
            _save_local_fallback(current)

            db_error = None
            try:
                db = get_db()
                db.table("system_settings").upsert({
                    "key": key,
                    "value": value
                }).execute()
            except Exception as e:
                db_error = str(e)

            try:
                st.session_state["global_system_settings"] = current
            except Exception:
                pass

            st.cache_data.clear()
            if db_error:
                return True, f"Setting '{key}' saved locally but database sync failed: {db_error}"
            return True, f"Setting '{key}' updated successfully."
        except Exception as e:
            return False, f"Failed to update setting '{key}': {str(e)}"

    @classmethod
    def update_settings(cls, new_settings: Dict[str, Any]) -> tuple[bool, str]:
        """Batch update multiple global settings."""
        if not auth.is_admin():
            return False, "Permission Denied: Only Admin users can modify system settings."

        try:
            current = _load_local_fallback()
            records_to_upsert = []
            for k, v in new_settings.items():
                current[k] = v
                records_to_upsert.append({"key": k, "value": v})

            _save_local_fallback(current)

            db_error = None
            try:
                db = get_db()
                db.table("system_settings").upsert(records_to_upsert).execute()
            except Exception as e:
                db_error = str(e)

            try:
                st.session_state["global_system_settings"] = current
            except Exception:
                pass

            st.cache_data.clear()
            if db_error:
                return True, f"Settings saved locally but database sync failed: {db_error}"
            return True, "All system settings updated successfully."
        except Exception as e:
            return False, f"Failed to update settings: {str(e)}"

    @classmethod
    def reload_settings(cls) -> Dict[str, Any]:
        """Force reload settings from database and clear memory cache."""
        st.cache_data.clear()
        return _cached_fetch_settings()


get_setting = SettingsService.get_setting
get_all_settings = SettingsService.get_all_settings
update_setting = SettingsService.update_setting
update_settings = SettingsService.update_settings
reload_settings = SettingsService.reload_settings
