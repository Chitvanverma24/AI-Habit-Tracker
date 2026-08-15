"""

AI Habit Tracker SaaS - Cache & System Tools Manager
Provides database diagnostic tools, cache manipulation, and data synchronization.

"""

from datetime import datetime
import streamlit as st
from database import get_db
from services.settings_service import reload_settings


class CacheManager:
    """Manages application caching, database health checks, and sync operations."""

    @staticmethod
    def clear_data_cache() -> tuple[bool, str]:
        """Clear all Streamlit data cache."""
        try:
            st.cache_data.clear()
            return True, "Data cache cleared successfully!"
        except Exception as e:
            return False, f"Error clearing data cache: {str(e)}"

    @staticmethod
    def clear_resource_cache() -> tuple[bool, str]:
        """Clear all Streamlit resource connections cache."""
        try:
            st.cache_resource.clear()
            return True, "Resource connections reset successfully!"
        except Exception as e:
            return False, f"Error resetting resource connections: {str(e)}"

    @staticmethod
    def ping_database() -> tuple[bool, str]:
        """Execute diagnostic database health ping and latency measurement."""
        try:
            t0 = datetime.now()
            get_db().table("profiles").select("id").limit(1).execute()
            latency = (datetime.now() - t0).total_seconds() * 1000
            return True, f"Database Healthy ({latency:.0f} ms)"
        except Exception as e:
            return False, f"Database Ping Failed: {str(e)}"

    @staticmethod
    def reload_system_settings() -> tuple[bool, str]:
        """Reload global settings live from Supabase or fallback file."""
        try:
            reload_settings()
            return True, "System settings reloaded from database!"
        except Exception as e:
            return False, f"Failed to reload settings: {str(e)}"

    @staticmethod
    def sync_data() -> tuple[bool, str]:
        """Sync platform metrics, clear cache, and reload system state."""
        try:
            st.cache_data.clear()
            reload_settings()
            return True, "All system metrics and settings synchronized!"
        except Exception as e:
            return False, f"Data sync failed: {str(e)}"


clear_data_cache = CacheManager.clear_data_cache
clear_resource_cache = CacheManager.clear_resource_cache
ping_database = CacheManager.ping_database
reload_system_settings = CacheManager.reload_system_settings
sync_data = CacheManager.sync_data
