"""

AI Habit Tracker SaaS
Achievement Center

"""
import math
from datetime import datetime
from typing import List, Dict, Any, Tuple
import streamlit as st
import ui_components
import utils
from database import get_db

def init_session_state() -> None:
    if "achievements_page" not in st.session_state:
        st.session_state.achievements_page = 1

@st.cache_data(ttl=60, show_spinner=False)
def fetch_total_completed_habits(user_id: str) -> int:
    if not user_id:
        return 0
    try:
        db = get_db()
        response = db.table("habit_logs").select("id", count="exact").eq("user_id", user_id).eq("status", "completed").execute()
        return response.count or 0
    except Exception:
        return 0

@st.cache_data(ttl=60, show_spinner=False)
def fetch_total_active_days(user_id: str) -> int:
    if not user_id:
        return 0
    try:
        db = get_db()
        response = db.table("habit_logs").select("log_date").eq("user_id", user_id).eq("status", "completed").execute()
        if not response.data: return 0
        return len({row["log_date"] for row in response.data})
    except Exception:
        return 0

def refresh_data() -> None:
    fetch_total_completed_habits.clear()
    fetch_total_active_days.clear()
    utils.clear_user_caches()
    st.rerun()

def get_user_metrics(user_id: str) -> Dict[str, int]:
    stats = utils.get_dashboard_statistics(user_id)
    return {
        "total_habits": stats.get("total_habits", 0),
        "longest_streak": stats.get("longest_streak", 0),
        "current_streak": stats.get("current_streak", 0),
        "total_completed": fetch_total_completed_habits(user_id),
        "active_days": fetch_total_active_days(user_id)
    }

AVAILABLE_BADGES = [
    {"title": "First Step", "desc": "Create your first habit.", "metric": "total_habits", "target": 1, "icon": "🌱"},
    {"title": "Getting Serious", "desc": "Complete 10 habits in total.", "metric": "total_completed", "target": 10, "icon": "🚀"},
    {"title": "Habit Builder", "desc": "Complete 50 habits in total.", "metric": "total_completed", "target": 50, "icon": "🛠️"},
    {"title": "Century Club", "desc": "Complete 100 habits in total.", "metric": "total_completed", "target": 100, "icon": "💯"},
    {"title": "3 Day Streak", "desc": "Maintain a 3-day habit streak.", "metric": "longest_streak", "target": 3, "icon": "🔥"},
    {"title": "7 Day Streak", "desc": "Maintain a 7-day habit streak.", "metric": "longest_streak", "target": 7, "icon": "🌟"},
    {"title": "30 Day Streak", "desc": "Maintain a 30-day habit streak.", "metric": "longest_streak", "target": 30, "icon": "🏆"},
    {"title": "Consistency Master", "desc": "Maintain a 100-day habit streak.", "metric": "longest_streak", "target": 100, "icon": "👑"},
    {"title": "First Week", "desc": "Be active for 7 unique days.", "metric": "active_days", "target": 7, "icon": "📅"},
    {"title": "Dedication", "desc": "Be active for 30 unique days.", "metric": "active_days", "target": 30, "icon": "💎"},
]

def process_new_achievements(user_id: str, earned_entries: List[Dict[str, Any]], metrics: Dict[str, int]) -> List[Dict[str, Any]]:
    earned_titles = {e["title"] for e in earned_entries}
    newly_earned = False
    db = get_db()
    now_str = utils.now().isoformat()
    new_entries = []
    
    for badge in AVAILABLE_BADGES:
        if badge["title"] not in earned_titles:
            if metrics.get(badge["metric"], 0) >= badge["target"]:
                try:
                    entry = {
                        "user_id": user_id,
                        "title": badge["title"],
                        "description": badge["desc"],
                        "badge_url": badge["icon"],
                        "earned_at": now_str
                    }
                    db.table("achievements").insert(entry).execute()
                    new_entries.append(entry)
                    newly_earned = True
                    st.toast(f"🏆 Achievement Unlocked: {badge['title']}!")
                except Exception:
                    # Gracefully handle duplicate or schema restriction without exposing raw DB error
                    pass
                    
    if newly_earned:
        refresh_data()
    return new_entries

def build_achievement_roster(earned_entries: List[Dict[str, Any]], metrics: Dict[str, int]) -> List[Dict[str, Any]]:
    earned_dict = {e["title"]: e for e in earned_entries}
    roster = []
    
    for badge in AVAILABLE_BADGES:
        title = badge["title"]
        target = badge["target"]
        current = min(metrics.get(badge["metric"], 0), target)
        
        if title in earned_dict or current >= target:
            earned_data = earned_dict.get(title, {})
            roster.append({
                "title": title,
                "description": earned_data.get("description", badge["desc"]),
                "icon": earned_data.get("badge_url", badge["icon"]),
                "target": target,
                "current": target,
                "status": "Earned",
                "earned_at": earned_data.get("earned_at")
            })
        else:
            status = "In Progress" if current > 0 else "Locked"
            roster.append({
                "title": title,
                "description": badge["desc"],
                "icon": badge["icon"],
                "target": target,
                "current": current,
                "status": status,
                "earned_at": None
            })
            
    standard_titles = {b["title"] for b in AVAILABLE_BADGES}
    for e in earned_entries:
        if e["title"] not in standard_titles:
            roster.append({
                "title": e["title"],
                "description": e.get("description", ""),
                "icon": e.get("badge_url", "🏅"),
                "target": 1,
                "current": 1,
                "status": "Earned",
                "earned_at": e.get("earned_at")
            })
    return roster

def render_achievements_dashboard(metrics: Dict[str, int], roster: List[Dict[str, Any]]) -> None:
    st.subheader("📊 Your Legend Status")
    earned_count = sum(1 for r in roster if r["status"] == "Earned")
    total_count = len(roster)
    completion_pct = int((earned_count / total_count) * 100) if total_count > 0 else 0

    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.metric("🏆 Achievements", f"{earned_count} / {total_count}")
        with col2: st.metric("🔥 Current Streak", f"{metrics['current_streak']} Days")
        with col3: st.metric("⭐ Longest Streak", f"{metrics['longest_streak']} Days")
        with col4: st.metric("🎯 Total Completed", metrics["total_completed"])
        with col5: st.metric("📅 Active Days", metrics["active_days"])

        st.write("")
        st.caption("Overall Achievement Progress")
        st.progress(completion_pct / 100.0)

def filter_achievements(roster: List[Dict[str, Any]], search: str, status_filter: str, sort_by: str) -> List[Dict[str, Any]]:
    filtered = roster
    if search:
        search_lower = search.lower()
        filtered = [a for a in filtered if search_lower in a["title"].lower() or search_lower in a["description"].lower()]
    if status_filter != "All":
        filtered = [a for a in filtered if a["status"] == status_filter]
    if sort_by == "Newest":
        filtered.sort(key=lambda x: x.get("earned_at") or "", reverse=True)
    elif sort_by == "Oldest":
        earned = sorted([a for a in filtered if a["earned_at"]], key=lambda x: x["earned_at"])
        unearned = [a for a in filtered if not a["earned_at"]]
        filtered = earned + unearned
    elif sort_by == "Alphabetical":
        filtered.sort(key=lambda x: x["title"].lower())
    return filtered

def get_paginated_data(data: List[Any], page: int, per_page: int) -> Tuple[List[Any], int]:
    total = len(data)
    pages = math.ceil(total / per_page) if total > 0 else 1
    if page > pages: page = pages
    st.session_state.achievements_page = page
    start = (page - 1) * per_page
    end = start + per_page
    return data[start:end], pages

@st.dialog("Achievement Details")
def dialog_achievement_details(achievement: Dict[str, Any]) -> None:
    st.markdown(f"<div style='text-align: center; font-size: 5rem; margin-bottom: 1rem;'>{achievement['icon']}</div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center; margin-top:0;'>{achievement['title']}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: var(--text-secondary);'>{achievement['description']}</p>", unsafe_allow_html=True)
    st.divider()
    
    if achievement["status"] == "Earned" and achievement.get("earned_at"):
        date_obj = datetime.fromisoformat(achievement["earned_at"])
        st.success(f"🎉 **Unlocked on:** {utils.format_date(date_obj.date())}")
    else:
        st.info(f"🔒 **Status:** {achievement['status']}")
        
    pct = min(achievement["current"] / achievement["target"], 1.0) if achievement["target"] > 0 else 0
    st.write(f"**Progress:** {achievement['current']} / {achievement['target']} ({int(pct * 100)}%)")
    st.progress(pct)
    
    st.write("")
    if st.button("Close", key=f"close_ach_{achievement['title']}", use_container_width=True):
        st.rerun()

def render_toolbar() -> Tuple[str, str, str]:
    st.subheader("Browse Badges")
    col1, col2, col3 = st.columns([2, 1.5, 1.5])
    with col1: search_query = st.text_input("🔍 Search Badges", placeholder="Search by name or description...", key="search_badges")
    with col2: status_filter = st.selectbox("⚡ Status", ["All", "Earned", "In Progress", "Locked"], key="status_badges")
    with col3: sort_by = st.selectbox("↕️ Sort", ["Newest", "Oldest", "Alphabetical"], key="sort_badges")
    return search_query, status_filter, sort_by

def render_achievement_card(achievement: Dict[str, Any]) -> None:
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        with c1: st.markdown(f"<div style='font-size: 2.5rem; text-align: center;'>{achievement['icon']}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"### {achievement['title']}")
            st.caption(achievement["description"])
        st.divider()
        
        status = achievement["status"]
        if status == "Earned":
            badge_html = ui_components.render_badge("🏆 EARNED", "active")
        elif status == "In Progress":
            badge_html = ui_components.render_badge("⚡ IN PROGRESS", "primary")
        else:
            badge_html = ui_components.render_badge("🔒 LOCKED", "inactive")

        st.markdown(f"<div>{badge_html}</div>", unsafe_allow_html=True)

        pct = min(achievement["current"] / achievement["target"], 1.0) if achievement["target"] > 0 else 0
        st.progress(pct)
        st.caption(f"Progress: {achievement['current']} / {achievement['target']} ({int(pct * 100)}%)")
        
        if st.button("View Details", key=f"btn_{achievement['title']}_{achievement['target']}", use_container_width=True):
            dialog_achievement_details(achievement)

def render_pagination(total_pages: int) -> None:
    if total_pages <= 1: return
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Prev", key="prev_ach", disabled=(st.session_state.achievements_page <= 1), use_container_width=True):
            st.session_state.achievements_page -= 1
            st.rerun()
    with col2:
        st.markdown(f"<div style='text-align:center; padding-top:0.5rem;'>Page <b>{st.session_state.achievements_page}</b> of {total_pages}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("Next ➡️", key="next_ach", disabled=(st.session_state.achievements_page >= total_pages), use_container_width=True):
            st.session_state.achievements_page += 1
            st.rerun()

def main() -> None:
    init_session_state()
    user_id = utils.get_current_user_id()
    if not user_id:
        st.error("User not authenticated.")
        return
        
    earned_entries = utils.get_user_achievements(user_id=user_id)
    metrics = get_user_metrics(user_id)
    new_entries = process_new_achievements(user_id, earned_entries, metrics)
    if new_entries:
        earned_entries.extend(new_entries)

    roster = build_achievement_roster(earned_entries, metrics)
    ui_components.render_hero("🏆 Achievement Center", "Track your milestones, unlock badges, and visualize your habit-building journey.")
    
    render_achievements_dashboard(metrics, roster)
    st.write("")
    
    search, status_filter, sort_by = render_toolbar()
    st.divider()
    
    filtered_roster = filter_achievements(roster, search, status_filter, sort_by)
    
    if not filtered_roster:
        if search or status_filter != "All":
            st.info("No badges match your current filters.")
        else:
            st.markdown("""
                <div style="text-align: center; padding: 5rem 2rem; border-radius: 1rem; border: 1px dashed var(--border); background-color: var(--surface);">
                    <h1 style="font-size: 3.5rem;">🚀</h1>
                    <h2>Your Journey Begins Here</h2>
                    <p style="color: var(--text-secondary);">Complete habits and build streaks to start earning premium badges.</p>
                </div>
            """, unsafe_allow_html=True)
        return
        
    per_page = 9
    paginated_roster, total_pages = get_paginated_data(filtered_roster, st.session_state.achievements_page, per_page)
    
    cols = st.columns(3)
    for index, ach in enumerate(paginated_roster):
        with cols[index % 3]: render_achievement_card(ach)
            
    render_pagination(total_pages)

if __name__ == "__main__":
    main()