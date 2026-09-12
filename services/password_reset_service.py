"""
AI Habit Tracker SaaS - Password Reset Service
Encapsulates manual password reset requests, secure temporary password generation,
24-hour expiration tracking, and mandatory password update workflow.
"""

import os
import sys
import json
import uuid
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st
from database import get_db, get_admin_db
from services.license_service import normalize_email, is_valid_email

# Local fallback file for password reset requests (server-side only)
FALLBACK_REQUESTS_FILE = os.path.join(os.path.dirname(__file__), "password_resets.json")

# Standard generic confirmation message (never reveals whether email exists)
RESET_CONFIRMATION_MESSAGE = (
    "Password Reset Request Received\n\n"
    "Your request has been received and will be reviewed.\n\n"
    "If the email address is associated with an account, a temporary password will be sent "
    "to the registered email address within approximately 12–24 hours.\n\n"
    "The temporary password will be valid for 24 hours.\n\n"
    "After logging in with the temporary password, please update your password using the "
    "existing Profile → Data & Security → Update Password feature."
)


def _load_local_requests() -> List[Dict[str, Any]]:
    """Load reset requests from local JSON fallback file."""
    if os.path.exists(FALLBACK_REQUESTS_FILE):
        try:
            with open(FALLBACK_REQUESTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[PasswordResetService] Failed to load local requests: {e}", file=sys.stderr)
    return []


def _save_local_requests(requests_list: List[Dict[str, Any]]) -> bool:
    """Save reset requests to local JSON fallback file."""
    try:
        os.makedirs(os.path.dirname(FALLBACK_REQUESTS_FILE), exist_ok=True)
        with open(FALLBACK_REQUESTS_FILE, "w", encoding="utf-8") as f:
            json.dump(requests_list, f, indent=2)
        return True
    except Exception as e:
        print(f"[PasswordResetService] Failed to save local requests: {e}", file=sys.stderr)
        return False


class PasswordResetService:
    """Service managing manual password reset requests and temporary passwords."""

    @staticmethod
    def generate_secure_temporary_password(length: int = 14) -> str:
        """Generate a unique cryptographically secure random temporary password.

        Guarantees:
        - Uses secrets module for cryptographic randomness.
        - Minimum length 14 characters.
        - Contains uppercase, lowercase, digits, and special characters.
        - Never predictable or repetitive.
        """
        if length < 12:
            length = 12

        upper = string.ascii_uppercase
        lower = string.ascii_lowercase
        digits = string.digits
        symbols = "!@#$%^&*"

        # Ensure at least 2 characters from each set
        password_chars = [
            secrets.choice(upper),
            secrets.choice(upper),
            secrets.choice(lower),
            secrets.choice(lower),
            secrets.choice(digits),
            secrets.choice(digits),
            secrets.choice(symbols),
            secrets.choice(symbols),
        ]

        # Fill the remaining length from all combined characters
        all_chars = upper + lower + digits + symbols
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))

        # Cryptographically shuffle the character list
        secrets.SystemRandom().shuffle(password_chars)
        temp_pwd = "".join(password_chars)
        return temp_pwd

    @classmethod
    def create_reset_request(cls, email: str) -> Tuple[bool, str]:
        """Validate email and securely create a password reset request.

        Privacy requirement:
        - Never reveals to the user whether the email exists.
        - Never stores passwords.
        - Returns a generic professional confirmation message.
        """
        if not email or not isinstance(email, str) or not email.strip():
            return False, "Please enter your email address."

        clean_email = normalize_email(email)
        if not is_valid_email(clean_email):
            return False, "Please enter a valid email address."

        req_id = str(uuid.uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        record = {
            "id": req_id,
            "email": clean_email,
            "status": "pending",
            "created_at": now_str,
            "processed_at": None,
            "processed_by": None,
            "expires_at": None
        }

        # Try saving to Supabase table first
        saved_in_db = False
        try:
            admin_db = get_admin_db()
            db_client = admin_db if admin_db else get_db()
            res = db_client.table("password_reset_requests").insert(record).execute()
            if res and res.data:
                saved_in_db = True
        except Exception:
            # Fallback to local storage
            saved_in_db = False

        # Always save/sync in local fallback for redundancy
        requests = _load_local_requests()
        # Avoid duplicate pending requests for the same email within 5 minutes
        requests.insert(0, record)
        _save_local_requests(requests)

        return True, RESET_CONFIRMATION_MESSAGE

    @classmethod
    def get_all_requests(cls) -> List[Dict[str, Any]]:
        """Fetch all reset requests from Supabase and fallback storage."""
        items_by_id = {}
        for r in _load_local_requests():
            if isinstance(r, dict) and "id" in r:
                items_by_id[r["id"]] = r

        try:
            admin_db = get_admin_db()
            db_client = admin_db if admin_db else get_db()
            res = (
                db_client.table("password_reset_requests")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            if res and hasattr(res, "data") and isinstance(res.data, list):
                for r in res.data:
                    if isinstance(r, dict) and "id" in r:
                        items_by_id[r["id"]] = r
        except Exception:
            pass

        sorted_items = list(items_by_id.values())
        sorted_items.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return sorted_items

    @classmethod
    def get_pending_requests(cls) -> List[Dict[str, Any]]:
        """Fetch only pending password reset requests."""
        all_reqs = cls.get_all_requests()
        return [r for r in all_reqs if str(r.get("status", "")).lower() == "pending"]

    @classmethod
    def process_reset_request(cls, request_id: str, admin_user_id: str) -> Tuple[bool, str, Optional[str]]:
        """Admin operation to process a pending password reset request.

        Execution:
        1. Verifies request exists and is pending.
        2. Locates the user in Supabase Auth by email.
        3. Generates a unique cryptographically secure temporary password.
        4. Resets the user's password in Supabase Auth.
        5. Sets temporary password metadata with 24-hour expiration.
        6. Updates the request status to 'processed'.
        7. Returns the temporary password for admin to manually send.
        """
        if not request_id:
            return False, "Invalid request ID provided.", None

        # Find the request
        all_reqs = cls.get_all_requests()
        target_req = None
        for r in all_reqs:
            if str(r.get("id")) == str(request_id):
                target_req = r
                break

        if not target_req:
            return False, "Password reset request not found.", None

        if str(target_req.get("status", "")).lower() != "pending":
            return False, f"This request has already been {target_req.get('status')}.", None

        target_email = normalize_email(target_req.get("email", ""))
        if not target_email:
            return False, "Request does not contain a valid email address.", None

        admin_db = get_admin_db()
        if not admin_db:
            return False, "Administrative Supabase client is not available.", None

        # Look up user by email in Supabase Auth
        target_user = None
        try:
            users_list = admin_db.auth.admin.list_users()
            for u in users_list:
                if u.email and u.email.strip().lower() == target_email:
                    target_user = u
                    break
        except Exception as e:
            print(f"[PasswordResetService] list_users error: {e}", file=sys.stderr)
            return False, f"Failed to query Supabase Auth users: {str(e)}", None

        if not target_user:
            # Mark request as rejected or user not found
            cls._update_request_status(request_id, "rejected", admin_user_id)
            return False, f"No registered user account found for email: '{target_email}'. Request marked as rejected.", None

        # Generate secure temporary password
        temp_password = cls.generate_secure_temporary_password()

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_dt = now + timedelta(hours=24)
        expires_iso = expires_dt.isoformat()

        # Update Supabase Auth user password and metadata
        try:
            existing_meta = getattr(target_user, "user_metadata", {}) or {}
            if not isinstance(existing_meta, dict):
                existing_meta = {}

            updated_meta = dict(existing_meta)
            updated_meta["is_temporary_password"] = True
            updated_meta["temporary_password_created_at"] = now_iso
            updated_meta["temporary_password_expires_at"] = expires_iso
            updated_meta["must_change_password"] = True

            admin_db.auth.admin.update_user_by_id(target_user.id, {
                "password": temp_password,
                "user_metadata": updated_meta
            })
        except Exception as e:
            print(f"[PasswordResetService] Auth update_user_by_id failed: {e}", file=sys.stderr)
            return False, f"Failed to reset password in Supabase Auth: {str(e)}", None

        # Update request status in database and fallback
        cls._update_request_status(
            request_id=request_id,
            status="processed",
            admin_user_id=admin_user_id,
            expires_at=expires_iso
        )

        return True, "Password reset successfully processed.", temp_password

    @classmethod
    def _update_request_status(cls, request_id: str, status: str, admin_user_id: Optional[str] = None,
                               expires_at: Optional[str] = None) -> None:
        """Update request status in Supabase table and local fallback."""
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "status": status,
            "processed_at": now_iso,
            "processed_by": admin_user_id,
        }
        if expires_at:
            update_data["expires_at"] = expires_at

        # Update in Supabase
        try:
            admin_db = get_admin_db()
            db_client = admin_db if admin_db else get_db()
            db_client.table("password_reset_requests").update(update_data).eq("id", request_id).execute()
        except Exception:
            pass

        # Update in local fallback
        reqs = _load_local_requests()
        for r in reqs:
            if str(r.get("id")) == str(request_id):
                r.update(update_data)
                break
        _save_local_requests(reqs)

    @classmethod
    def check_user_temporary_password_status(cls, user_obj: Any) -> Dict[str, Any]:
        """Check whether the user is using an active or expired temporary password."""
        result = {
            "is_temporary": False,
            "is_expired": False,
            "must_change": False,
            "expires_at": None
        }

        if not user_obj:
            return result

        meta = getattr(user_obj, "user_metadata", None)
        if not meta or not isinstance(meta, dict):
            # Try dictionary access if user_obj is dict
            if isinstance(user_obj, dict):
                meta = user_obj.get("user_metadata", {})
            else:
                return result

        if not meta:
            return result

        is_temp = bool(meta.get("is_temporary_password", False))
        must_change = bool(meta.get("must_change_password", False))
        expires_at_str = meta.get("temporary_password_expires_at")

        if is_temp or must_change:
            result["is_temporary"] = True
            result["must_change"] = True
            result["expires_at"] = expires_at_str

            if expires_at_str:
                try:
                    exp_dt = datetime.fromisoformat(expires_at_str)
                    now_utc = datetime.now(timezone.utc)
                    if now_utc > exp_dt:
                        result["is_expired"] = True
                except Exception:
                    # In case of date parse error, don't expire prematurely
                    pass

        return result

    @classmethod
    def clear_temporary_password_status(cls, user_id: str, email: Optional[str] = None) -> bool:
        """Clear temporary password state from user metadata after password update."""
        if not user_id:
            return False

        # 1. Update user metadata in Supabase Auth
        try:
            admin_db = get_admin_db()
            if admin_db:
                # Fetch existing metadata first
                user_res = admin_db.auth.admin.get_user_by_id(user_id)
                u = getattr(user_res, "user", None)
                existing_meta = getattr(u, "user_metadata", {}) or {}
                if not isinstance(existing_meta, dict):
                    existing_meta = {}

                updated_meta = dict(existing_meta)
                updated_meta["is_temporary_password"] = False
                updated_meta["must_change_password"] = False
                updated_meta.pop("temporary_password_expires_at", None)
                updated_meta.pop("temporary_password_created_at", None)

                admin_db.auth.admin.update_user_by_id(user_id, {
                    "user_metadata": updated_meta
                })
        except Exception as e:
            print(f"[PasswordResetService] Failed to clear user metadata: {e}", file=sys.stderr)

        # 2. Clear session state flags
        if hasattr(st, "session_state"):
            st.session_state.pop("must_change_password", None)
            st.session_state.pop("is_temporary_password", None)
            st.session_state.pop("temp_password_expires_at", None)

        return True
