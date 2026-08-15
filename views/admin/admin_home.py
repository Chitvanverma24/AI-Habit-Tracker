"""

AI Habit Tracker SaaS - Admin Dashboard Overview

"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
import streamlit as st
from database import get_db
from auth import auth
import utils
import ui_components


def init_session_state() -> None:
    if "admin_search_query" not in st.session_state:
        st.session_state.admin_search_query = ""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Admin Home"


@st.cache_data(show_spinner=False, ttl=300)
def fetch_platform_counts() -> Dict[str, Any]:
    db = get_db()
    today_str = utils.today().isoformat()
    counts = {"users": 0, "habits": 0, "today_completions": 0, "journals": 0, "achievements": 0, "health": "Optimal 🟢"}
    try:
        counts["users"] = db.table("profiles").select("id", count="exact").execute().count or 0
        counts["habits"] = db.table("habits").select("id", count="exact").execute().count or 0
        counts["today_completions"] = db.table("habit_logs").select("id", count="exact").eq("log_date", today_str).eq("status", "completed").execute().count or 0
        counts["journals"] = db.table("journal_entries").select("id", count="exact").execute().count or 0
        counts["achievements"] = db.table("achievements").select("id", count="exact").execute().count or 0
    except Exception:
        counts["health"] = "Degraded 🔴"
    return counts


@st.cache_data(show_spinner=False, ttl=600)
def fetch_user_growth_data(days: int = 30) -> pd.DataFrame:
    db = get_db()
    start_date = (utils.now() - timedelta(days=days)).isoformat()
    try:
        res = db.table("profiles").select("created_at").gte("created_at", start_date).execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        df['date'] = pd.to_datetime(df['created_at']).dt.date
        return df.groupby('date').size().reset_index(name='new_users')
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=600)
def fetch_habit_frequency_dist() -> pd.DataFrame:
    db = get_db()
    try:
        res = db.table("habits").select("frequency").execute()
        if not res.data:
            return pd.DataFrame()
        dist = pd.DataFrame(res.data)['frequency'].value_counts().reset_index()
        dist.columns = ['Frequency', 'Count']
        return dist
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=300)
def fetch_recent_profiles(limit: int = 10) -> List[Dict[str, Any]]:
    db = get_db()
    try:
        return db.table("profiles").select("*").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=300)
def fetch_recent_habits(limit: int = 10) -> List[Dict[str, Any]]:
    db = get_db()
    try:
        return db.table("habits").select("*, profiles(display_name)").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


def search_admin_users(query: str) -> List[Dict[str, Any]]:
    if not query:
        return []
    try:
        return get_db().table("profiles").select("*").ilike("display_name", f"%{query}%").limit(20).execute().data or []
    except Exception:
        return []


def refresh_admin_data() -> None:
    """Clear admin-specific cached data and rerun."""
    for func in [fetch_platform_counts, fetch_user_growth_data,
                 fetch_habit_frequency_dist, fetch_recent_profiles,
                 fetch_recent_habits]:
        try:
            func.clear()
        except Exception:
            pass
    st.rerun()


def render_top_metrics() -> None:
    counts = fetch_platform_counts()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Users", f"{counts['users']:,}")
    c2.metric("Total Habits", f"{counts['habits']:,}")
    c3.metric("Today's Completions", f"{counts['today_completions']:,}")
    c4.metric("Journal Entries", f"{counts['journals']:,}")
    c5.metric("System Health", counts["health"])


def render_charts() -> None:
    import plotly.express as px

    counts = fetch_platform_counts()
    growth_df = fetch_user_growth_data(30)
    freq_df = fetch_habit_frequency_dist()

    c1, c2 = st.columns([0.6, 0.4])
    with c1:
        st.subheader("📈 30-Day User Growth")
        if not growth_df.empty:
            start_date = utils.now().date() - timedelta(days=29)
            date_range = pd.date_range(start=start_date, end=utils.now().date()).date
            growth_df.set_index('date', inplace=True)
            growth_df = growth_df.reindex(date_range, fill_value=0).reset_index()
            growth_df.rename(columns={'index': 'date'}, inplace=True)
            growth_df['cumulative'] = growth_df['new_users'].cumsum()
            fig = px.area(growth_df, x='date', y='cumulative', color_discrete_sequence=['#2563eb'])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            ui_components.render_empty_state("📈", "No growth data", "Not enough user registrations yet.")

    with c2:
        st.subheader("📊 Habit Frequencies")
        if not freq_df.empty:
            fig = px.bar(freq_df, x='Frequency', y='Count', color_discrete_sequence=['#10b981'])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            ui_components.render_empty_state("📊", "No habit data", "No habits created yet.")

    st.subheader("📝 Platform Activity Overview")
    with st.container(border=True):
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Total Users", f"{counts['users']:,}")
        sc2.metric("Journal Reflections", f"{counts['journals']:,}")
        sc3.metric("Badges Unlocked", f"{counts['achievements']:,}")
        sc4.metric("Active System Status", counts["health"])


def render_recent_activity() -> None:
    t1, t2 = st.tabs(["👥 Recent Users", "🎯 Recent Habits"])
    with t1:
        users = fetch_recent_profiles(10)
        if users:
            for u in users:
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{u.get('display_name','User')}** {'(Admin)' if u.get('is_admin') else ''}")
                c2.write(u.get('timezone', 'UTC'))
                c3.write(utils.format_date(datetime.fromisoformat(u['created_at'])))
        else:
            st.info("No recent users.")
    with t2:
        habits = fetch_recent_habits(10)
        if habits:
            for h in habits:
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{h.get('title','Habit')}**")
                c2.write(f"Freq: {h.get('frequency','daily').title()}")
                c3.write(utils.format_date(datetime.fromisoformat(h['created_at'])))
        else:
            st.info("No recent habits.")


def main() -> None:
    auth.require_admin()
    init_session_state()

    ui_components.render_hero("🛡️ Admin Console", "Monitor platform metrics, user growth, and system performance.", icon="🛡️")

    render_top_metrics()
    st.write("")
    render_charts()
    st.write("")
    render_recent_activity()


if __name__ == "__main__":
    main()