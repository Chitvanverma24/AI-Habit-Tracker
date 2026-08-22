import os
import sys
from typing import Optional, List, Dict, Any

import streamlit as st
from supabase import Client, create_client


def _get_secret_value(*keys: str) -> Optional[str]:
    """Safely retrieves a configuration key from st.secrets or os.environ."""
    # 1. Try root st.secrets
    try:
        if hasattr(st, "secrets"):
            for k in keys:
                if k in st.secrets:
                    val = str(st.secrets[k]).strip()
                    if val:
                        return val
    except Exception:
        pass

    # 2. Try nested st.secrets (e.g., st.secrets["supabase"]["service_role_key"])
    try:
        if hasattr(st, "secrets") and "supabase" in st.secrets:
            sb = st.secrets["supabase"]
            for k in keys:
                short_k = k.lower().replace("supabase_", "")
                if hasattr(sb, "get") and sb.get(short_k):
                    return str(sb.get(short_k)).strip()
                if hasattr(sb, "get") and sb.get(k):
                    return str(sb.get(k)).strip()
    except Exception:
        pass

    # 3. Try os.environ
    for k in keys:
        val = os.environ.get(k)
        if val and val.strip():
            return val.strip()

    return None


def _normalize_jwt_key(key: Optional[str]) -> Optional[str]:
    """Normalizes JWT format (auto-repairs missing dots between segments)."""
    if not key:
        return None
    key = key.strip(" \"'\t\r\n")
    if key in ("YOUR_SERVICE_ROLE_KEY", "GENERATE_A_LONG_RANDOM_SECRET_KEY", ""):
        return None
    # If the key is a JWT with missing dot between header and payload
    if key.count(".") == 1 and key.startswith("eyJ") and "eyJpc3Mi" in key:
        idx = key.find("eyJpc3Mi")
        if idx > 0 and key[idx - 1] != ".":
            key = key[:idx] + "." + key[idx:]
    return key


# Per-Session Supabase Client (Anon/Publishable Key for general operations)

def get_db() -> Client:
    """Returns a Supabase client instance.
    When running in Streamlit, the client is strictly scoped to the active
    user's session in st.session_state to ensure complete session isolation
    between concurrent browsers and users."""
    # 1. Check if an active per-session client exists in st.session_state
    try:
        if hasattr(st, "session_state"):
            if "_supabase_client" in st.session_state and st.session_state["_supabase_client"] is not None:
                return st.session_state["_supabase_client"]
    except Exception:
        pass

    # 2. Initialize a fresh client
    url = _get_secret_value("SUPABASE_URL", "supabase_url", "URL")
    key = _get_secret_value("SUPABASE_KEY", "supabase_key", "KEY", "SUPABASE_ANON_KEY")
    if not url or not key:
        # Fallback to direct indexing if available
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]

    client = create_client(url, key)

    # 3. If authenticated in current session, attach session token to postgrest
    try:
        if hasattr(st, "session_state"):
            token = st.session_state.get("auth_token")
            if token:
                try:
                    client.postgrest.auth(token)
                except Exception:
                    pass
            st.session_state["_supabase_client"] = client
    except Exception:
        pass

    return client


@st.cache_resource(show_spinner=False)
def get_admin_db() -> Optional[Client]:
    """Returns a privileged Supabase client using the service_role key.
    Used exclusively for server-side admin operations (e.g., deleting auth users).
    Returns None if the service_role key is not configured.
    NEVER expose this client or its key to the frontend."""
    try:
        url = _get_secret_value("SUPABASE_URL", "supabase_url", "URL")
        service_key = _normalize_jwt_key(_get_secret_value(
            "SUPABASE_SERVICE_ROLE_KEY",
            "supabase_service_role_key",
            "SUPABASE_SERVICE_KEY",
            "SERVICE_ROLE_KEY",
            "SUPABASE_SECRET_KEY"
        ))
        if not url or not service_key:
            return None
        return create_client(url, service_key)
    except Exception as e:
        print(f"[database] Failed to initialize admin Supabase client: {e}", file=sys.stderr)
        return None


def is_admin_db_ready() -> tuple[bool, str]:
    """Safe diagnostic checker: returns whether the admin client is initialized."""
    url = _get_secret_value("SUPABASE_URL", "supabase_url", "URL")
    service_key = _normalize_jwt_key(_get_secret_value(
        "SUPABASE_SERVICE_ROLE_KEY",
        "supabase_service_role_key",
        "SUPABASE_SERVICE_KEY",
        "SERVICE_ROLE_KEY",
        "SUPABASE_SECRET_KEY"
    ))
    if not url:
        return False, "SUPABASE_URL is missing from configuration."
    if not service_key:
        return False, "SUPABASE_SERVICE_ROLE_KEY is not configured in secrets."
    client = get_admin_db()
    if not client:
        return False, "Admin client initialization failed (check key validity)."
    return True, "Admin client connected successfully."



# Health Check

@st.cache_data(ttl=60, show_spinner=False)
def check_database_connection() -> bool:
    """Tests database connectivity (cached for 60s to avoid pinging every rerun)."""
    try:
        db = get_db()
        db.table("profiles").select("id").limit(1).execute()
        return True
    except Exception:
        return False



# Generic CRUD Operations

def fetch_all(table: str, user_id: Optional[str] = None) -> List[Dict]:
    """Fetch records from a table, optionally filtered by user_id."""
    try:
        db = get_db()
        query = db.table(table).select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        return query.execute().data
    except Exception:
        return []


def fetch_by_id(table: str, record_id: str) -> Optional[Dict]:
    """Fetch a single record by primary key."""
    try:
        db = get_db()
        response = db.table(table).select("*").eq("id", record_id).single().execute()
        return response.data
    except Exception:
        return None


def insert_record(table: str, data: dict) -> Optional[List[Dict]]:
    """Insert a new record and return the result."""
    try:
        db = get_db()
        return db.table(table).insert(data).execute().data
    except Exception:
        return None


def update_record(table: str, record_id: str, data: dict) -> Optional[List[Dict]]:
    """Update an existing record by ID."""
    try:
        db = get_db()
        return db.table(table).update(data).eq("id", record_id).execute().data
    except Exception:
        return None


def delete_record(table: str, record_id: str) -> Optional[List[Dict]]:
    """Delete a record by ID."""
    try:
        db = get_db()
        return db.table(table).delete().eq("id", record_id).execute().data
    except Exception:
        return None


def get_table_count(table: str) -> int:
    """Count records in a table using efficient count query."""
    try:
        db = get_db()
        response = db.table(table).select("id", count="exact").execute()
        return response.count or 0
    except Exception:
        return 0


def get_user_profile(user_id: str) -> Optional[Dict]:
    """Return user profile by ID."""
    try:
        db = get_db()
        response = db.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception:
        return None