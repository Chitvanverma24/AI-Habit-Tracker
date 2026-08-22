"""

AI Habit Tracker SaaS - License Management Service
Handles license key generation, activation, verification, and admin operations.

"""

import secrets
import string
import csv
import io
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import streamlit as st
from database import get_db
from auth import auth


def _generate_key_segment(length: int = 4) -> str:
    """Generate a cryptographically random alphanumeric segment."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_license_key() -> str:
    """Generate a single license key in format HT-XXXX-XXXX-XXXX-XXXX."""
    segments = [_generate_key_segment() for _ in range(4)]
    return f"HT-{'-'.join(segments)}"


def generate_license_keys(count: int) -> List[str]:
    """Generate multiple unique license keys."""
    keys = set()
    while len(keys) < count:
        keys.add(generate_license_key())
    return list(keys)


def normalize_email(email: Optional[str]) -> str:
    """Normalize email address: strip leading/trailing whitespace and lowercase."""
    if not email or not isinstance(email, str):
        return ""
    return email.strip().lower()


def normalize_license_key(key: Optional[str]) -> str:
    """Normalize license key: strip leading/trailing whitespace and uppercase."""
    if not key or not isinstance(key, str):
        return ""
    return key.strip().upper()


def is_valid_email(email: str) -> bool:
    """Basic email regex validation."""
    clean = normalize_email(email)
    if not clean:
        return False
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(email_regex, clean))


def activate_purchase_key(license_key: str, email: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate and activate a purchase license key with an email address.
    Supports RPC execution or direct Supabase table query fallback.
    """
    clean_key = normalize_license_key(license_key)
    clean_email = normalize_email(email)

    if not clean_key:
        return False, "Invalid license key."

    if not clean_email or not is_valid_email(clean_email):
        return False, "Invalid email address."

    db = get_db()
    current_uid = user_id or auth.get_user_id()

    # 1. Try Supabase RPC first
    try:
        result = db.rpc("activate_purchase", {"p_license_key": clean_key, "p_email": clean_email}).execute()
        if result.data:
            response = result.data
            if isinstance(response, list):
                response = response[0] if response else {}
            if isinstance(response, dict):
                success = response.get("success", False)
                message = response.get("message") or response.get("error", "Activation error.")
                if success:
                    st.cache_data.clear()
                return success, message
    except Exception:
        # Fall back to direct Python database operations below
        pass

    # 2. Python Fallback Query against `licenses` table
    try:
        # Fetch license record
        resp = db.table("licenses").select("*").ilike("license_key", clean_key).execute()
        records = resp.data or []

        if not records:
            return False, "Invalid license key."

        lic = records[0]
        status = lic.get("status", "unused")

        if status == "revoked":
            return False, "This license has been revoked."

        if status == "active":
            assigned_email = normalize_email(lic.get("assigned_email"))
            if assigned_email == clean_email:
                # Same email reactivating/linking account
                if current_uid and not lic.get("assigned_user_id"):
                    try:
                        db.table("licenses").update({
                            "assigned_user_id": current_uid,
                            "activated_by": current_uid
                        }).eq("id", lic["id"]).execute()
                    except Exception:
                        pass
                st.cache_data.clear()
                return True, "Purchase activated successfully."
            else:
                return False, "This license has already been activated."

        # License status is 'unused'
        update_payload = {
            "status": "active",
            "assigned_email": clean_email,
            "activated_at": datetime.now().isoformat()
        }
        if current_uid:
            update_payload["assigned_user_id"] = current_uid
            update_payload["activated_by"] = current_uid

        db.table("licenses").update(update_payload).eq("id", lic["id"]).execute()
        st.cache_data.clear()
        return True, "Purchase activated successfully."

    except Exception as e:
        err_msg = str(e)
        if "PGRST205" in err_msg or "schema cache" in err_msg:
            return False, "Database table 'licenses' is missing. Please run the provided SQL migration in Supabase."
        return False, f"Activation error: {err_msg}"


def activate_license(license_key: str) -> Tuple[bool, str]:
    """Backward compatible wrapper for logged-in user activation."""
    user_email = auth.get_user_email() or ""
    user_id = auth.get_user_id()
    return activate_purchase_key(license_key, user_email, user_id)


def check_email_has_active_license(email: str, license_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Check if an email address is associated with an active license."""
    clean_email = normalize_email(email)
    clean_key = normalize_license_key(license_key)

    if not clean_email or not is_valid_email(clean_email):
        return None

    db = get_db()

    # 1. Try verify_active_license RPC first if available
    try:
        rpc_res = db.rpc("verify_active_license", {"p_email": clean_email, "p_license_key": clean_key or ""}).execute()
        if rpc_res.data and isinstance(rpc_res.data, dict):
            if rpc_res.data.get("valid"):
                return rpc_res.data
    except Exception:
        pass

    # 2. If clean_key is not passed, check Streamlit session state for activated key matching this email
    if not clean_key and hasattr(st, "session_state"):
        sess_email = normalize_email(st.session_state.get("activated_email"))
        sess_key = normalize_license_key(st.session_state.get("activated_license"))
        if sess_email == clean_email and sess_key:
            clean_key = sess_key

    # 3. If a license key is available, verify via activate_purchase RPC (SECURITY DEFINER)
    if clean_key:
        ok, msg = activate_purchase_key(clean_key, clean_email)
        if ok:
            return {
                "license_key": clean_key,
                "assigned_email": clean_email,
                "status": "active",
                "message": msg
            }

    # 4. Direct table select fallback (works when authenticated or if RLS permits)
    try:
        response = (
            db.table("licenses")
            .select("*")
            .ilike("assigned_email", clean_email)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
    except Exception:
        pass

    return None


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_user_license(user_id: str, clean_email: str) -> Optional[Dict[str, Any]]:
    """Internal cached helper for checking user license by user_id and email."""
    if not user_id:
        return None

    db = get_db()

    # Check by assigned_user_id or activated_by first
    try:
        response = (
            db.table("licenses")
            .select("*")
            .or_(f"assigned_user_id.eq.{user_id},activated_by.eq.{user_id}")
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
    except Exception:
        pass

    # Check by assigned_email if user_email is present
    if clean_email:
        try:
            response_email = (
                db.table("licenses")
                .select("*")
                .ilike("assigned_email", clean_email)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if response_email.data:
                lic = response_email.data[0]
                # Auto-associate user_id with license record if missing via activate_purchase RPC
                if user_id and not lic.get("assigned_user_id"):
                    lic_key = lic.get("license_key")
                    if lic_key:
                        activate_purchase_key(lic_key, clean_email, user_id)
                return lic
        except Exception:
            pass

    return None


def check_user_license(user_id: str, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Check if a user has an active license. Returns license dict or None."""
    if not user_id:
        return None
    clean_email = normalize_email(email or auth.get_user_email())
    return _fetch_user_license(user_id, clean_email)



def bulk_create_licenses(count: int) -> Tuple[bool, str, List[str]]:
    """Admin: Generate and insert license keys into the database."""
    if not auth.is_admin():
        return False, "Permission denied.", []

    if count < 1 or count > 1000:
        return False, "Count must be between 1 and 1000.", []

    keys = generate_license_keys(count)
    records = [{"license_key": k, "status": "unused"} for k in keys]
    db = get_db()

    # 1. Try RPC first
    try:
        res = db.rpc("generate_bulk_licenses", {"p_keys": keys}).execute()
        if res.data:
            response = res.data
            if isinstance(response, list):
                response = response[0] if response else {}
            if isinstance(response, dict) and response.get("success"):
                st.cache_data.clear()
                return True, f"Successfully generated {count} license keys.", keys
    except Exception:
        pass

    # 2. Direct table insert fallback
    try:
        db.table("licenses").insert(records).execute()
        st.cache_data.clear()
        return True, f"Successfully generated {count} license keys.", keys
    except Exception as e:
        err_msg = str(e)
        if "PGRST205" in err_msg or "schema cache" in err_msg:
            return False, "Database table 'licenses' missing. Please run database/migration_license_system.sql in Supabase SQL Editor.", []
        return False, f"Failed to create licenses: {err_msg}", []


def export_keys_csv(keys: List[str]) -> str:
    """Convert a list of keys to CSV string for download."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["License Key"])
    for key in keys:
        writer.writerow([key])
    return output.getvalue()


@st.cache_data(ttl=30, show_spinner=False)
def get_license_counts() -> Dict[str, int]:
    """Admin: Get counts of licenses by status based on the real database."""
    db = get_db()
    counts = {"unused": 0, "active": 0, "revoked": 0, "total": 0}
    try:
        for status in ["unused", "active", "revoked"]:
            resp = db.table("licenses").select("id", count="exact").eq("status", status).execute()
            counts[status] = resp.count or 0
        counts["total"] = counts["unused"] + counts["active"] + counts["revoked"]
    except Exception:
        pass
    return counts


@st.cache_data(ttl=30, show_spinner=False)
def get_licenses_paginated(page: int = 1, per_page: int = 20, status_filter: str = "All",
                           search: str = "") -> Tuple[List[Dict], int]:
    """Admin: Fetch paginated licenses with optional filters."""
    db = get_db()
    try:
        query = db.table("licenses").select("*, profiles!assigned_user_id(display_name)", count="exact")

        if status_filter != "All":
            query = query.eq("status", status_filter.lower())
        if search:
            query = query.or_(f"license_key.ilike.%{search}%,assigned_email.ilike.%{search}%")

        offset = (page - 1) * per_page
        query = query.order("created_at", desc=True).range(offset, offset + per_page - 1)

        result = query.execute()
        total = result.count or 0
        return result.data or [], total
    except Exception:
        # Fallback if profile join fails
        try:
            query = db.table("licenses").select("*", count="exact")
            if status_filter != "All":
                query = query.eq("status", status_filter.lower())
            if search:
                query = query.or_(f"license_key.ilike.%{search}%,assigned_email.ilike.%{search}%")
            offset = (page - 1) * per_page
            query = query.order("created_at", desc=True).range(offset, offset + per_page - 1)
            result = query.execute()
            return result.data or [], result.count or 0
        except Exception:
            return [], 0


def revoke_license(license_id: str) -> Tuple[bool, str]:
    """Admin: Revoke a license by ID."""
    if not auth.is_admin():
        return False, "Permission denied."
    try:
        db = get_db()
        db.table("licenses").update({
            "status": "revoked",
            "revoked_at": datetime.now().isoformat()
        }).eq("id", license_id).execute()
        st.cache_data.clear()
        return True, "License revoked successfully."
    except Exception as e:
        return False, f"Failed to revoke license: {str(e)}"


def reinstate_license(license_id: str) -> Tuple[bool, str]:
    """Admin: Reinstate a revoked license back to unused (clears activation)."""
    if not auth.is_admin():
        return False, "Permission denied."
    try:
        db = get_db()
        db.table("licenses").update({
            "status": "unused",
            "assigned_user_id": None,
            "activated_by": None,
            "assigned_email": None,
            "activated_at": None,
            "revoked_at": None
        }).eq("id", license_id).execute()
        st.cache_data.clear()
        return True, "License reinstated successfully."
    except Exception as e:
        return False, f"Failed to reinstate license: {str(e)}"
