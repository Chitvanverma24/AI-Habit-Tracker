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

        Strategy:
        1. Try the SECURITY DEFINER RPC `admin_delete_user` which handles
           cascade deletion of all application data and attempts auth.users removal.
        2. Use the Supabase Auth Admin API via service_role client to delete
           the user from auth.users (this cascades to profiles and all child
           tables via ON DELETE CASCADE foreign keys).
        3. Fallback: manually delete application data using the admin client
           to bypass RLS, then delete the profile.
        """
        if not auth.is_admin():
            return False, "Permission Denied: Only Admins can delete users."

        current_uid = auth.get_user_id()
        if target_user_id == current_uid:
            return False, "Cannot delete your own account from the Admin Console."

        errors_log = []
        db = get_db()
        admin_db = get_admin_db()

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

        # ── Step 2: Try Supabase Auth Admin API (service_role key) ──
        # Deleting from auth.users triggers ON DELETE CASCADE on profiles,
        # which cascades to all child tables (habits, habit_logs, etc.)
        auth_deleted = False
        if admin_db:
            try:
                admin_db.auth.admin.delete_user(target_user_id)
                auth_deleted = True
            except Exception as e:
                err_msg = str(e)
                errors_log.append(f"Auth Admin API delete: {err_msg}")
                print(f"[AdminService] Auth Admin delete_user error: {e}", file=sys.stderr)

        # ── Step 3: If auth deletion succeeded, verify and return ──
        if auth_deleted:
            # Verify the profile is gone (should be cascaded)
            try:
                check = data_db.table("profiles").select("id").eq("id", target_user_id).execute()
                if check.data and len(check.data) > 0:
                    # Auth user deleted but profile persists — force delete app data
                    errors_log.append("Auth user deleted but profile persisted — cleaning up manually.")
                else:
                    clear_data_cache()
                    st.cache_data.clear()
                    return True, "User account and all associated records permanently deleted."
            except Exception:
                # If we can't verify, assume success since auth user is deleted
                clear_data_cache()
                st.cache_data.clear()
                return True, "User account deleted from authentication system."

        # ── Step 4: Try SECURITY DEFINER RPC as alternative ──
        if not auth_deleted:
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
                    elif isinstance(res, dict) and res.get("error"):
                        errors_log.append(f"RPC admin_delete_user: {res['error']}")
            except Exception as e:
                errors_log.append(f"RPC admin_delete_user: {e}")

        # ── Step 5: Manual cascade deletion fallback ──
        child_tables = ["habit_logs", "habits", "journal_entries", "achievements",
                        "notifications", "feedback", "subscriptions"]
        for tbl in child_tables:
            try:
                data_db.table(tbl).delete().eq("user_id", target_user_id).execute()
            except Exception as e:
                errors_log.append(f"Delete from {tbl}: {e}")

        # Delete profile record
        try:
            data_db.table("profiles").delete().eq("id", target_user_id).execute()
        except Exception as e:
            errors_log.append(f"Delete profile: {e}")

        # ── Step 6: Verify deletion ──
        try:
            check_res = data_db.table("profiles").select("id").eq("id", target_user_id).execute()
            if check_res.data and len(check_res.data) > 0:
                # Log accumulated errors for debugging
                if errors_log:
                    print(f"[AdminService] delete_user errors for {target_user_id}:", file=sys.stderr)
                    for err in errors_log:
                        print(f"  - {err}", file=sys.stderr)
                if not admin_db:
                    return False, ("Unable to delete user. The SUPABASE_SERVICE_ROLE_KEY is not configured. "
                                   "Add it to .streamlit/secrets.toml (find it in Supabase Dashboard → Settings → API → service_role key).")
                return False, "Unable to delete user profile. Check server logs for details."
        except Exception:
            pass

        # Log any non-fatal errors
        if errors_log:
            print(f"[AdminService] delete_user completed with warnings for {target_user_id}:", file=sys.stderr)
            for err in errors_log:
                print(f"  - {err}", file=sys.stderr)

        clear_data_cache()
        st.cache_data.clear()

        if auth_deleted:
            return True, "User account and all associated records permanently deleted."
        else:
            return True, ("User application data deleted successfully. "
                          "Note: The authentication record may still exist. "
                          "Configure SUPABASE_SERVICE_ROLE_KEY for complete auth deletion.")

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
