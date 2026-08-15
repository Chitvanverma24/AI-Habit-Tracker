"""

AI Habit Tracker SaaS - Admin Service
Encapsulates admin business logic for user management, role assignments,
and system controls.

"""

import sys
import traceback
from typing import Dict, Any
import streamlit as st
from database import get_db, get_admin_db
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
            result = get_db().table("profiles").update({"is_admin": is_admin}).eq("id", target_user_id).execute()
            if not result.data:
                return False, "User profile not found or update had no effect."
            clear_data_cache()
            return True, f"User role updated to {'Admin' if is_admin else 'User'}."
        except Exception as e:
            print(f"[AdminService] update_user_role error: {e}", file=sys.stderr)
            return False, f"Failed to update role: {str(e)}"

    @staticmethod
    def delete_user(target_user_id: str) -> tuple[bool, str]:
        """Delete user account and all associated data.

        Execution Flow:
        1. Verify caller has admin privileges and is not deleting self.
        2. Validate target user ID format.
        3. Unlink license records (SET NULL on assigned_user_id, activated_by).
        4. Explicitly delete child application records from public tables.
        5. Delete profile record from profiles table.
        6. Delete auth user from Supabase Auth via auth.admin.delete_user().
        7. Fallback to SECURITY DEFINER RPC if Auth API is unavailable.
        8. Verify deletion and return clear success or precise technical error.
        """
        if not auth.is_admin():
            return False, "Permission Denied: Only Admins can delete users."

        if not target_user_id or not isinstance(target_user_id, str) or len(target_user_id.strip()) < 10:
            return False, "Invalid user ID provided."

        target_user_id = target_user_id.strip()
        current_uid = auth.get_user_id()
        if target_user_id == current_uid:
            return False, "Cannot delete your own account from the Admin Console."

        errors_log = []
        db = get_db()
        admin_db = get_admin_db()

        # Safe diagnostic logging (NEVER logs secret values)
        has_admin_client = admin_db is not None
        print(f"[AdminService] Deleting user {target_user_id} (Admin Client Available: {has_admin_client})", file=sys.stderr)

        # Use admin client for data operations if available (bypasses RLS)
        data_db = admin_db if admin_db else db

        # ── Step 1: Unlink license records (SET NULL, not delete) ──
        try:
            data_db.table("licenses").update(
                {"assigned_user_id": None, "activated_by": None}
            ).eq("assigned_user_id", target_user_id).execute()
        except Exception as e:
            errors_log.append(f"License unlink (assigned_user_id): {e}")

        try:
            data_db.table("licenses").update(
                {"activated_by": None}
            ).eq("activated_by", target_user_id).execute()
        except Exception as e:
            errors_log.append(f"License unlink (activated_by): {e}")

        # ── Step 2: Explicitly delete child records from public tables ──
        child_tables = ["habit_logs", "habits", "journal_entries", "achievements",
                        "notifications", "feedback", "subscriptions"]
        for tbl in child_tables:
            try:
                data_db.table(tbl).delete().eq("user_id", target_user_id).execute()
            except Exception as e:
                errors_log.append(f"Delete from {tbl}: {e}")

        # ── Step 3: Delete profile record ──
        try:
            data_db.table("profiles").delete().eq("id", target_user_id).execute()
        except Exception as e:
            errors_log.append(f"Delete profile: {e}")

        # ── Step 4: Delete from Supabase Auth via Admin API (service_role key) ──
        auth_deleted = False
        auth_err = None
        if admin_db:
            try:
                admin_db.auth.admin.delete_user(target_user_id)
                auth_deleted = True
                print(f"[AdminService] Successfully deleted user {target_user_id} from Supabase Auth.", file=sys.stderr)
            except Exception as e:
                auth_err = str(e)
                errors_log.append(f"Auth Admin API delete: {auth_err}")
                print(f"[AdminService] Auth Admin delete_user failed for {target_user_id}: {e}", file=sys.stderr)

        # ── Step 5: Fallback to SECURITY DEFINER RPC if Auth API was not executed ──
        if not auth_deleted:
            try:
                rpc_res = db.rpc("admin_delete_user", {"p_target_user_id": target_user_id}).execute()
                if rpc_res.data:
                    res = rpc_res.data
                    if isinstance(res, list):
                        res = res[0] if res else {}
                    if isinstance(res, dict) and res.get("success"):
                        auth_deleted = True
                    elif isinstance(res, dict) and res.get("error"):
                        errors_log.append(f"RPC admin_delete_user: {res['error']}")
            except Exception as e:
                errors_log.append(f"RPC admin_delete_user: {e}")

        # ── Step 6: Verify deletion ──
        profile_still_exists = False
        try:
            check_res = data_db.table("profiles").select("id").eq("id", target_user_id).execute()
            if check_res.data and len(check_res.data) > 0:
                profile_still_exists = True
        except Exception:
            pass

        if profile_still_exists:
            err_msg = "; ".join(errors_log) if errors_log else "Profile record could not be removed."
            print(f"[AdminService] Deletion failed for {target_user_id}: {err_msg}", file=sys.stderr)
            return False, f"Failed to delete user profile: {err_msg}"

        clear_data_cache()
        st.cache_data.clear()

        if auth_deleted:
            return True, "User account and all associated records permanently deleted."
        elif not admin_db:
            return False, "User data removed from database, but Auth deletion failed because SUPABASE_SERVICE_ROLE_KEY is not configured or could not initialize."
        else:
            return False, f"User data removed from database, but Supabase Auth deletion failed: {auth_err or 'Unknown error'}"

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
