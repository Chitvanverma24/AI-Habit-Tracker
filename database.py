"""

AI Habit Tracker SaaS
Database Manager — Supabase Connection Layer

"""

from typing import Optional, List, Dict, Any

import streamlit as st
from supabase import Client, create_client



# Cached Supabase Client

@st.cache_resource(show_spinner=False)
def get_db() -> Client:
    """Returns a cached Supabase client instance."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


@st.cache_resource(show_spinner=False)
def get_admin_db() -> Optional[Client]:
    """Returns a privileged Supabase client using the service_role key.
    Used exclusively for server-side admin operations (e.g., deleting auth users).
    Returns None if the service_role key is not configured.
    NEVER expose this client or its key to the frontend."""
    try:
        url = st.secrets["SUPABASE_URL"]
        service_key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        if not service_key or service_key == "YOUR_SERVICE_ROLE_KEY":
            return None
        return create_client(url, service_key)
    except (KeyError, Exception):
        return None



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