"""

AI Habit Tracker SaaS
Utility Functions — Business Logic & Data Access

"""

from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

import streamlit as st
from database import get_db
from auth import auth
from services.settings_service import (get_setting, get_all_settings, update_setting,
                                      update_settings, reload_settings)
from services.permissions import (can_bypass_maintenance, can_register_users,
                                  can_access_admin_panel, can_use_ai_coach,
                                  can_use_journal, can_use_habits, can_use_achievements)
from services.cache_manager import (clear_data_cache, clear_resource_cache,
                                    ping_database, reload_system_settings, sync_data)
from services.admin_service import update_user_role, delete_user, save_admin_settings
from services.license_service import (activate_license, activate_purchase_key, check_user_license,
                                      check_email_has_active_license, bulk_create_licenses,
                                      export_keys_csv, get_license_counts,
                                      get_licenses_paginated, revoke_license, reinstate_license)




# Current User Helper

def get_current_user_id() -> Optional[str]:
    """Return current logged-in user's UUID."""
    return auth.get_user_id()



# User Profile (Cached)

@st.cache_data(ttl=300, show_spinner=False)
def get_user_profile(user_id: str) -> Optional[Dict]:
    """Fetch user profile from the database (cached 5min)."""
    if not user_id:
        return None
    try:
        db = get_db()
        return db.table("profiles").select("*").eq("id", user_id).single().execute().data
    except Exception:
        return None


def get_display_name() -> str:
    """Return the current user's display name."""
    user_id = get_current_user_id()
    if not user_id:
        return "User"
    profile = get_user_profile(user_id)
    if not profile:
        return "User"
    return profile.get("display_name", "User")


def get_timezone() -> str:
    """Return the current user's timezone setting."""
    user_id = get_current_user_id()
    if not user_id:
        return "UTC"
    profile = get_user_profile(user_id)
    if not profile:
        return "UTC"
    return profile.get("timezone", "UTC")



# Date & Time Helpers

def today() -> date:
    return date.today()

def now() -> datetime:
    return datetime.now()

def week_start() -> date:
    return date.today() - timedelta(days=date.today().weekday())

def week_end() -> date:
    return week_start() + timedelta(days=6)

def format_date(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value).date()
        except ValueError:
            return value
    return value.strftime("%d %b %Y")

def format_time(value) -> str:
    if value is None:
        return "—"
    return value.strftime("%I:%M %p")

def greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    elif hour < 21:
        return "Good Evening"
    return "Good Night"

def last_n_days(days: int = 7) -> List[date]:
    return [date.today() - timedelta(days=i) for i in reversed(range(days))]



# Cache Invalidation Helper

def clear_user_caches() -> None:
    """Clear user-specific cached query data upon data mutation."""
    # Clear specific cached functions instead of all cache
    for func in [get_total_habits, get_today_habits, _get_today_status_count,
                 get_weekly_progress, get_recent_activity, calculate_current_streak,
                 calculate_longest_streak, get_dashboard_statistics,
                 get_total_achievements, get_user_achievements,
                 get_unread_notifications, get_notifications,
                 get_recent_journal_entries, get_user_profile]:
        try:
            func.clear()
        except Exception:
            pass



# Habit Data Access (Cached for high performance)

@st.cache_data(ttl=60, show_spinner=False)
def get_total_habits(user_id: Optional[str] = None) -> int:
    """Count of active habits for the user."""
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    try:
        db = get_db()
        response = (
            db.table("habits")
            .select("id", count="exact")
            .eq("user_id", uid)
            .eq("is_active", True)
            .execute()
        )
        return response.count or 0
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def get_today_habits(user_id: Optional[str] = None) -> List[Dict]:
    """Fetch all active habits for the user."""
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    try:
        db = get_db()
        response = (
            db.table("habits")
            .select("*")
            .eq("user_id", uid)
            .eq("is_active", True)
            .order("created_at")
            .execute()
        )
        return response.data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _get_today_status_count(status: str, user_id: Optional[str] = None) -> int:
    """Count logs with a given status for today."""
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    try:
        db = get_db()
        response = (
            db.table("habit_logs")
            .select("id", count="exact")
            .eq("user_id", uid)
            .eq("log_date", today().isoformat())
            .eq("status", status)
            .execute()
        )
        return response.count or 0
    except Exception:
        return 0


def get_completed_today() -> int:
    return _get_today_status_count("completed")

def get_failed_today() -> int:
    return _get_today_status_count("failed")

def get_skipped_today() -> int:
    return _get_today_status_count("skipped")


def get_completion_percentage() -> float:
    total = get_total_habits()
    if total == 0:
        return 0
    completed = get_completed_today()
    return round((completed / total) * 100, 1)



# Weekly Progress (Cached)

@st.cache_data(ttl=60, show_spinner=False)
def get_weekly_progress(user_id: Optional[str] = None) -> List[Dict]:
    """Fetch habit logs for the current week."""
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    try:
        db = get_db()
        response = (
            db.table("habit_logs")
            .select("log_date,status")
            .eq("user_id", uid)
            .gte("log_date", week_start().isoformat())
            .lte("log_date", week_end().isoformat())
            .order("log_date")
            .execute()
        )
        return response.data or []
    except Exception:
        return []



# Recent Activity (Cached)

@st.cache_data(ttl=60, show_spinner=False)
def get_recent_activity(limit: int = 10, user_id: Optional[str] = None) -> List[Dict]:
    """Fetch recent habit log entries with habit titles."""
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    try:
        db = get_db()
        response = (
            db.table("habit_logs")
            .select("*, habits(title)")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        return []



# Streak Calculations (Cached)

@st.cache_data(ttl=60, show_spinner=False)
def calculate_current_streak(user_id: Optional[str] = None) -> int:
    """Calculate current consecutive-day streak."""
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    try:
        db = get_db()
        response = (
            db.table("habit_logs")
            .select("log_date")
            .eq("user_id", uid)
            .eq("status", "completed")
            .order("log_date", desc=True)
            .execute()
        )
        logs = response.data
        if not logs:
            return 0

        dates = sorted({row["log_date"] for row in logs}, reverse=True)
        streak = 0
        current = today()
        if dates[0] != current.isoformat():
            yesterday = (current - timedelta(days=1)).isoformat()
            if dates[0] != yesterday:
                return 0
            current = current - timedelta(days=1)

        for d in dates:
            if d == current.isoformat():
                streak += 1
                current -= timedelta(days=1)
            elif d < current.isoformat():
                break
        return streak
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def calculate_longest_streak(user_id: Optional[str] = None) -> int:
    """Calculate the longest consecutive-day streak ever."""
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    try:
        db = get_db()
        response = (
            db.table("habit_logs")
            .select("log_date")
            .eq("user_id", uid)
            .eq("status", "completed")
            .order("log_date")
            .execute()
        )
        logs = response.data
        if not logs:
            return 0

        dates = sorted({datetime.fromisoformat(row["log_date"]).date() for row in logs})

        if len(dates) == 0:
            return 0

        longest = 1
        current = 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days == 1:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        return longest
    except Exception:
        return 0



# Dashboard Statistics (Aggregated & Cached)

@st.cache_data(ttl=60, show_spinner=False)
def get_dashboard_statistics(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Compile all dashboard metrics in a single cached call."""
    uid = user_id or get_current_user_id()
    tot = get_total_habits(uid)
    comp = _get_today_status_count("completed", uid)
    fail = _get_today_status_count("failed", uid)
    skip = _get_today_status_count("skipped", uid)
    pct = round((comp / tot) * 100, 1) if tot > 0 else 0.0
    c_streak = calculate_current_streak(uid)
    l_streak = calculate_longest_streak(uid)
    ach = get_total_achievements(uid)
    notif = get_unread_notifications(uid)

    return {
        "total_habits": tot,
        "completed_today": comp,
        "failed_today": fail,
        "skipped_today": skip,
        "completion_percentage": pct,
        "current_streak": c_streak,
        "longest_streak": l_streak,
        "achievements": ach,
        "notifications": notif
    }



# Achievements (Cached)

@st.cache_data(ttl=60, show_spinner=False)
def get_total_achievements(user_id: Optional[str] = None) -> int:
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    try:
        db = get_db()
        response = (
            db.table("achievements")
            .select("id", count="exact")
            .eq("user_id", uid)
            .execute()
        )
        return response.count or 0
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def get_user_achievements(limit: Optional[int] = None, user_id: Optional[str] = None) -> List[Dict]:
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    try:
        db = get_db()
        query = (
            db.table("achievements")
            .select("*")
            .eq("user_id", uid)
            .order("earned_at", desc=True)
        )
        if limit:
            query = query.limit(limit)
        return query.execute().data or []
    except Exception:
        return []



# Notifications (Cached)

@st.cache_data(ttl=60, show_spinner=False)
def get_unread_notifications(user_id: Optional[str] = None) -> int:
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    try:
        db = get_db()
        response = (
            db.table("notifications")
            .select("id", count="exact")
            .eq("user_id", uid)
            .eq("is_read", False)
            .execute()
        )
        return response.count or 0
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def get_notifications(limit: int = 20, user_id: Optional[str] = None) -> List[Dict]:
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    try:
        db = get_db()
        query = (
            db.table("notifications")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
        )
        if limit:
            query = query.limit(limit)
        return query.execute().data or []
    except Exception:
        return []


def mark_notification_read(notification_id: str) -> bool:
    try:
        db = get_db()
        db.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
        clear_user_caches()
        return True
    except Exception:
        return False



# Journal Helpers (Cached)

@st.cache_data(ttl=60, show_spinner=False)
def get_recent_journal_entries(limit: int = 5, user_id: Optional[str] = None) -> List[Dict]:
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    try:
        db = get_db()
        return (
            db.table("journal_entries")
            .select("*")
            .eq("user_id", uid)
            .order("entry_date", desc=True)
            .limit(limit)
            .execute()
        ).data or []
    except Exception:
        return []


def get_latest_journal() -> Optional[Dict]:
    entries = get_recent_journal_entries(1)
    return entries[0] if entries else None



# Feedback

def submit_feedback(feedback_type: str, message: str) -> bool:
    user_id = get_current_user_id()
    if not user_id:
        return False
    try:
        db = get_db()
        db.table("feedback").insert({
            "user_id": user_id,
            "feedback_type": feedback_type,
            "message": message
        }).execute()
        return True
    except Exception:
        return False



# UI Formatters

def percentage(value) -> str:
    return f"{value:.0f}%"

def status_badge(status: str) -> str:
    badges = {
        "completed": "✅ Completed",
        "failed": "❌ Failed",
        "skipped": "⏭️ Skipped",
        "active": "🟢 Active",
        "inactive": "⚪ Inactive"
    }
    return badges.get(status, status.title())

def mood_emoji(score) -> str:
    if score is None:
        return "😐"
    if score <= 2:
        return "😞"
    if score <= 4:
        return "🙁"
    if score <= 6:
        return "😐"
    if score <= 8:
        return "😊"
    return "😁"



# Application Summary (for data export)

def app_summary() -> Dict[str, Any]:
    """Full application data summary for export."""
    user_id = get_current_user_id()
    return {
        "profile": get_user_profile(user_id),
        "stats": get_dashboard_statistics(),
        "recent_activity": get_recent_activity(5),
        "journal": get_latest_journal(),
        "achievements": get_user_achievements(3),
        "notifications": get_notifications(5)
    }