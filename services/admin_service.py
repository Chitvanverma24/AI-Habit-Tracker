"""

AI Habit Tracker SaaS - Admin Service
Encapsulates admin business logic for user management, role assignments,
and system controls.

"""

from typing import Dict, Any
import streamlit as st
from database import get_db
from auth import auth
from services.cache_manager import clear_data_cache


class AdminService:
    """Admin operations service executing secure platform management."""

    @staticmethod
    def update_user_role(target_user_id: str, is_admin: bool) -> tuple[bool, str]:
        """Grant or revoke admin privileges for a user."""
        if not auth.is_admin():
            return False, "Permission Denied: Only Admins can modify user roles."

        current_uid = auth.get_user_id()
        if target_user_id == current_uid and not is_admin:
            return False, "Cannot remove your own admin privileges."

        try:
            get_db().table("profiles").update({"is_admin": is_admin}).eq("id", target_user_id).execute()
            clear_data_cache()
            return True, f"User role updated to {'Admin' if is_admin else 'User'}."
        except Exception as e:
            return False, f"Failed to update role: {str(e)}"

    @staticmethod
    def delete_user(target_user_id: str) -> tuple[bool, str]:
        """Delete user account and all associated data."""
        if not auth.is_admin():
            return False, "Permission Denied: Only Admins can delete users."

        current_uid = auth.get_user_id()
        if target_user_id == current_uid:
            return False, "Cannot delete your own account from the Admin Console."

        try:
            get_db().table("profiles").delete().eq("id", target_user_id).execute()
            clear_data_cache()
            # NOTE: This only deletes the profile and cascaded data.
            # The auth.users record persists (requires Supabase Admin API / service_role key).
            # The user's login will fail on next attempt since profile creation trigger
            # will re-create a blank profile, effectively resetting them.
            return True, "User profile and data deleted. Auth account requires manual removal via Supabase Dashboard."
        except Exception as e:
            return False, f"Failed to delete user: {str(e)}"

    @staticmethod
    def save_admin_settings(settings: Dict[str, Any]) -> tuple[bool, str]:
        """Save admin settings with full validation and cache invalidation."""
        if not auth.is_admin():
            return False, "Permission Denied: Admin authorization required."

        try:
            from services.settings_service import update_settings
            success, msg = update_settings(settings)
            return success, msg
        except Exception as e:
            return False, f"Error saving settings: {str(e)}"


update_user_role = AdminService.update_user_role
delete_user = AdminService.delete_user
save_admin_settings = AdminService.save_admin_settings
