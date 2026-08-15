"""

AI Habit Tracker SaaS
User Home Dashboard

"""

import streamlit as st
from datetime import date, datetime
from database import get_db
import ui_components
import utils


def complete_habit(habit_id: str) -> None:
    db = get_db()
    try:
        db.table("habit_logs").insert({
            "habit_id": habit_id,
            "user_id": utils.get_current_user_id(),
            "log_date": utils.today().isoformat(),
            "status": "completed",
            "created_at": utils.now().isoformat(),
            "updated_at": utils.now().isoformat()
        }).execute()
        utils.clear_user_caches()
        st.rerun()
    except Exception:
        st.error("Failed to log habit completion.")
        utils.clear_user_caches()
        st.rerun()


def undo_completion(habit_id: str) -> None:
    db = get_db()
    try:
        db.table("habit_logs").delete() \
            .eq("habit_id", habit_id) \
            .eq("user_id", utils.get_current_user_id()) \
            .eq("log_date", utils.today().isoformat()) \
            .eq("status", "completed").execute()
        utils.clear_user_caches()
        st.rerun()
    except Exception:
        st.error("Failed to undo habit completion.")
        utils.clear_user_caches()
        st.rerun()


@st.cache_data(ttl=60, show_spinner=False)
def get_completed_ids(user_id: str) -> set:
    db = get_db()
    try:
        resp = db.table("habit_logs").select("habit_id").eq("user_id", user_id).eq("log_date", utils.today().isoformat()).eq("status", "completed").execute()
        return {r["habit_id"] for r in resp.data} if resp.data else set()
    except Exception:
        return set()


def main():
    user_id = utils.get_current_user_id()
    if not user_id:
        st.error("Please log in to view dashboard.")
        return

    stats = utils.get_dashboard_statistics()
    user_name = utils.get_display_name()
    welcome = utils.greeting()

    ui_components.render_hero(f"{welcome}, {user_name}! 👋", "Consistency is the key to building lasting habits. Let's make today count.", icon="🏠")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 Total Habits", stats["total_habits"])
    with col2:
        st.metric("✅ Completed Today", stats["completed_today"])
    with col3:
        st.metric("🔥 Current Streak", f"{stats['current_streak']} days")
    with col4:
        st.metric("📈 Completion Rate", f"{stats['completion_percentage']}%")

    st.write("")
    left, right = st.columns([2, 1])

    with left:
        st.subheader("📊 Today's Progress")
        progress = stats["completion_percentage"]
        st.progress(progress / 100)
        st.caption(f"**{progress}%** of your daily goals reached")

        st.write("")
        st.subheader("📅 Today's Habits")
        habits = utils.get_today_habits()
        if not habits:
            ui_components.render_empty_state("🌱", "No active habits found", "Start building routines by creating your first habit!")
            if st.button("➕ Add Your First Habit", type="primary", key="home_add_first_habit"):
                st.session_state.current_page = "Add Habit"
                st.rerun()
        else:
            completed_ids = get_completed_ids(user_id)
            for habit in habits:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1.2])
                    c1.markdown(f"**{habit['title']}**")
                    if habit.get('description'):
                        c1.caption(habit['description'])
                    h_id = habit['id']
                    if h_id in completed_ids:
                        if c2.button("↩️ Undo", key=f"undo_home_{h_id}", use_container_width=True):
                            undo_completion(h_id)
                    else:
                        if c2.button("✅ Complete", key=f"log_home_{h_id}", type="primary", use_container_width=True):
                            complete_habit(h_id)

    with right:
        st.subheader("🤖 AI Coach Insight")
        with st.container(border=True):
            if stats['current_streak'] >= 7:
                st.success("🔥 You're on fire! Keep that momentum going.")
            elif stats['completed_today'] == stats['total_habits'] and stats['total_habits'] > 0:
                st.success("🎉 Perfect day! All daily habits completed.")
            else:
                st.info("💡 Every journey starts with a single step. Complete a habit today!")

        st.write("")
        st.subheader("🕒 Recent Activity")
        with st.container(border=True):
            activities = utils.get_recent_activity(5)
            if not activities:
                st.caption("No log activity recorded yet.")
            for act in activities:
                title = act.get('habits', {}).get('title', 'Habit Log')
                st.markdown(f"<div style='font-size:0.88rem; padding:0.25rem 0;'>✅ <b>{title}</b> · <span style='color:var(--text-muted);'>{act['log_date']}</span></div>", unsafe_allow_html=True)

        st.write("")
        st.subheader("🏆 Recent Badges")
        achievements = utils.get_user_achievements(3)
        if achievements:
            for ach in achievements:
                with st.container(border=True):
                    st.markdown(f"🏅 **{ach['title']}**")
                    st.caption(ach['description'])
        else:
            st.caption("Complete habits and build streaks to earn badges!")


if __name__ == "__main__":
    main()