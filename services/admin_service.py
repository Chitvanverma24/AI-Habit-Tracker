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

        db = get_db()

        # 1. Try Supabase RPC admin_delete_user first (SECURITY DEFINER)
        try:
            rpc_res = db.rpc("admin_delete_user", {"p_target_user_id": target_user_id}).execute()
            if rpc_res.data:
                res = rpc_res.data
                if isinstance(res, list):
                    res = res[0] if res else {}
                if isinstance(res, dict) and res.get("success"):
                    clear_data_cache()
                    st.cache_data.clear()
                    return True, "User account and all associated records permanently deleted."
        except Exception:
            pass

        # 2. Fallback: Cascading deletion via direct table operations
        try:
            # Unlink license records
            try:
                db.table("licenses").update({"assigned_user_id": None, "activated_by": None}).eq("assigned_user_id", target_user_id).execute()
                db.table("licenses").update({"activated_by": None}).eq("activated_by", target_user_id).execute()
            except Exception:
                pass

            # Delete related child records
            for tbl in ["habit_logs", "habits", "journal_entries", "achievements", "notifications", "feedback", "subscriptions"]:
                try:
                    db.table(tbl).delete().eq("user_id", target_user_id).execute()
                except Exception:
                    pass

            # Delete profile record
            db.table("profiles").delete().eq("id", target_user_id).execute()

            # Verify deletion status in database
            check_res = db.table("profiles").select("id").eq("id", target_user_id).execute()
            if check_res.data and len(check_res.data) > 0:
                return False, "Unable to delete user profile. Please run the database migration script in Supabase to ensure admin DELETE permissions."

            clear_data_cache()
            st.cache_data.clear()
            return True, "User account and all associated records deleted successfully."
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
