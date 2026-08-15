"""

AI Habit Tracker SaaS
Add Habit View — Clean Creation Interface

"""

import streamlit as st
from datetime import datetime
from database import get_db
import ui_components
import utils


def validate_habit(title: str, target_count: int) -> bool:
    if not title or len(title.strip()) < 3 or len(title.strip()) > 100:
        return False
    return target_count >= 1


def create_habit(title: str, description: str, frequency: str, target_count: int) -> bool:
    db = get_db()
    user_id = utils.get_current_user_id()
    now_str = utils.now().isoformat()
    try:
        db.table("habits").insert({
            "user_id": user_id,
            "title": title.strip(),
            "description": description.strip() if description else None,
            "frequency": frequency.lower(),
            "target_count": target_count,
            "is_active": True,
            "created_at": now_str,
            "updated_at": now_str
        }).execute()
        utils.clear_user_caches()
        return True
    except Exception:
        st.error("Failed to create habit. Please try again.")
        return False


@st.cache_data(ttl=60, show_spinner=False)
def get_active_habits_count(user_id: str) -> int:
    db = get_db()
    try:
        resp = db.table("habits").select("id", count="exact").eq("user_id", user_id).eq("is_active", True).execute()
        return resp.count or 0
    except Exception:
        return 0


def main():
    user_id = utils.get_current_user_id()
    if not user_id:
        st.error("User not authenticated.")
        return

    ui_components.render_hero("➕ Add New Habit", "Create a new routine to track and build consistency.")

    active_count = get_active_habits_count(user_id)

    col1, col2 = st.columns([2, 1])

    with col2:
        with st.container(border=True):
            st.markdown("### Your Routines")
            st.metric("Active Habits", active_count)
            st.caption("You have full access to create unlimited habits!")

        with st.container(border=True):
            st.markdown("### Quick Templates")
            st.caption("Click a preset to populate the creation form:")
            templates = [
                ("💧 Drink Water", "Drink 2L of water daily for hydration", "Daily", 1),
                ("📚 Read Pages", "Read 10 pages of a book every day", "Daily", 1),
                ("🏃 Daily Exercise", "30 minutes of physical workout", "Daily", 1),
                ("🧘 Mindful Meditation", "10 minutes of morning meditation", "Daily", 1),
                ("✍️ Journal Entry", "Write a daily reflection entry", "Daily", 1),
            ]
            for t_title, t_desc, t_freq, t_target in templates:
                if st.button(t_title, key=f"tpl_{t_title}", use_container_width=True):
                    st.session_state["draft_title"] = t_title
                    st.session_state["draft_desc"] = t_desc
                    st.session_state["draft_freq"] = t_freq
                    st.rerun()

    with col1:
        with st.container(border=True):
            st.subheader("Habit Configuration")

            default_title = st.session_state.get("draft_title", "")
            default_desc = st.session_state.get("draft_desc", "")
            default_freq = st.session_state.get("draft_freq", "Daily")

            title = st.text_input("Habit Title *", value=default_title, max_chars=100, placeholder="e.g., Read 15 pages")
            description = st.text_area("Description (Optional)", value=default_desc, placeholder="Why is this habit important to you?")

            c1, c2 = st.columns(2)
            with c1:
                freq_options = ["Daily", "Weekly", "Monthly"]
                freq_idx = freq_options.index(default_freq) if default_freq in freq_options else 0
                frequency = st.selectbox("Frequency *", freq_options, index=freq_idx)
            with c2:
                target_count = st.number_input("Daily Target Count *", min_value=1, max_value=100, value=1)

            st.write("")
            if st.button("🚀 Create Habit", type="primary", use_container_width=True):
                if validate_habit(title, target_count):
                    success = create_habit(title, description, frequency, target_count)
                    if success:
                        st.toast(f"🎉 Habit '{title}' created successfully!", icon="✅")
                        st.session_state.pop("draft_title", None)
                        st.session_state.pop("draft_desc", None)
                        st.session_state.pop("draft_freq", None)
                        st.session_state.current_page = "Manage Habits"
                        st.rerun()
                else:
                    st.error("Invalid Input: Title must be 3-100 characters and target count at least 1.")


if __name__ == "__main__":
    main()