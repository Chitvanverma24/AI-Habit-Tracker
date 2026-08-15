"""

AI Habit Tracker SaaS
Journal Management Page

"""
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Tuple
import streamlit as st
import ui_components
from database import get_db
from auth import auth
import utils

MOOD_OPTIONS = {
    "great": "😁 Great (9-10)",
    "good": "😊 Good (7-8)",
    "neutral": "😐 Neutral (5-6)",
    "poor": "🙁 Poor (3-4)",
    "bad": "😞 Bad (1-2)"
}


def init_session_state() -> None:
    if "journal_page" not in st.session_state:
        st.session_state.journal_page = 1
    if "journal_per_page" not in st.session_state:
        st.session_state.journal_per_page = 10


@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_journals(user_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    try:
        response = db.table("journal_entries").select("*").eq("user_id", user_id).order("entry_date", desc=True).execute()
        return response.data or []
    except Exception:
        return []


def refresh_data() -> None:
    fetch_all_journals.clear()
    utils.clear_user_caches()
    st.rerun()


def validate_journal_input(content: str, entry_date: date) -> bool:
    if not content or len(content.strip()) < 5:
        st.error("Journal content must be at least 5 characters long.")
        return False
    if entry_date > utils.today():
        st.error("Cannot create a journal entry for a future date.")
        return False
    return True


def check_existing_entry(target_date: date) -> bool:
    db = get_db()
    user_id = auth.get_user_id()
    try:
        response = db.table("journal_entries").select("id").eq("user_id", user_id).eq("entry_date", target_date.isoformat()).execute()
        return len(response.data or []) > 0
    except Exception:
        return False


def create_journal_db(entry_date: date, content: str, mood_score: int) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    now_str = utils.now().isoformat()
    try:
        db.table("journal_entries").insert({
            "user_id": user_id,
            "entry_date": entry_date.isoformat(),
            "content": content.strip(),
            "mood_score": mood_score,
            "created_at": now_str,
            "updated_at": now_str
        }).execute()
        st.toast("Journal entry saved successfully!", icon="✅")
        refresh_data()
    except Exception:
        st.error("Unable to save journal entry. Please try again.")


def update_journal_db(entry_id: str, content: str, mood_score: int) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    now_str = utils.now().isoformat()
    try:
        db.table("journal_entries").update({
            "content": content.strip(),
            "mood_score": mood_score,
            "updated_at": now_str
        }).eq("id", entry_id).eq("user_id", user_id).execute()
        st.toast("Journal entry updated successfully!", icon="✅")
        refresh_data()
    except Exception:
        st.error("Unable to update journal entry. Please try again.")


def delete_journal_db(entry_id: str) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    try:
        db.table("journal_entries").delete().eq("id", entry_id).eq("user_id", user_id).execute()
        st.toast("Journal entry removed!", icon="🗑️")
        refresh_data()
    except Exception:
        st.error("Unable to delete journal entry. Please try again.")


def search_entries(entries: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    if not query:
        return entries
    query_lower = query.lower()
    return [
        e for e in entries
        if query_lower in e.get("content", "").lower() or query_lower in e.get("entry_date", "").lower()
    ]


def filter_by_timeframe(entries: List[Dict[str, Any]], timeframe: str) -> List[Dict[str, Any]]:
    if timeframe == "All Entries":
        return entries

    today = utils.today()
    filtered = []
    for e in entries:
        try:
            entry_date = datetime.fromisoformat(e["entry_date"]).date()
        except ValueError:
            continue

        if timeframe == "Today" and entry_date == today:
            filtered.append(e)
        elif timeframe == "Last 7 Days" and today - timedelta(days=7) <= entry_date <= today:
            filtered.append(e)
        elif timeframe == "Last 30 Days" and today - timedelta(days=30) <= entry_date <= today:
            filtered.append(e)
        elif timeframe == "This Month" and entry_date.month == today.month and entry_date.year == today.year:
            filtered.append(e)

    return filtered


def sort_entries(entries: List[Dict[str, Any]], sort_order: str) -> List[Dict[str, Any]]:
    return sorted(entries, key=lambda x: x.get("entry_date", ""), reverse=(sort_order == "Newest"))


def get_paginated_data(data: List[Any], page: int, per_page: int) -> Tuple[List[Any], int]:
    total = len(data)
    pages = math.ceil(total / per_page) if total > 0 else 1
    if page > pages:
        page = pages
    st.session_state.journal_page = page
    start = (page - 1) * per_page
    end = start + per_page
    return data[start:end], pages


def get_mood_key(score: int) -> str:
    if score >= 9:
        return "great"
    elif score >= 7:
        return "good"
    elif score >= 5:
        return "neutral"
    elif score >= 3:
        return "poor"
    return "bad"


@st.dialog("Write Journal Entry")
def dialog_create_journal(all_entries: List[Dict[str, Any]]) -> None:
    st.markdown("### Daily Reflection & Thoughts")
    st.caption("Record how your day went, track your mood, and clear your mind.")

    entry_date = st.date_input("Entry Date", value=utils.today(), max_value=utils.today(), key="new_journal_date")

    if check_existing_entry(entry_date):
        st.warning(f"⚠️ You already have a journal entry for {utils.format_date(entry_date)}.")

    mood_str = st.selectbox("Overall Mood", list(MOOD_OPTIONS.values()), index=1, key="new_journal_mood")

    default_template = "### 🌟 Daily Reflection\n- **What went well today?** \n- **What challenges did I face?** \n- **Key takeaway for tomorrow:** \n"
    content = st.text_area("Journal Entry", value=default_template, height=220, key="new_journal_content")

    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Cancel", key="cancel_create_journal", use_container_width=True):
            st.rerun()
    with btn_col2:
        has_existing = check_existing_entry(entry_date)
        if st.button("Save Journal", type="primary", key="save_create_journal", use_container_width=True, disabled=has_existing):
            mood_score = 8
            for k, v in MOOD_OPTIONS.items():
                if v == mood_str:
                    mood_score = 10 if k == "great" else (8 if k == "good" else (6 if k == "neutral" else (4 if k == "poor" else 2)))
            if validate_journal_input(content, entry_date):
                create_journal_db(entry_date, content, mood_score)


@st.dialog("Edit Journal Entry")
def dialog_edit_journal(entry: Dict[str, Any]) -> None:
    raw_date = datetime.fromisoformat(entry.get("entry_date", utils.today().isoformat())).date()
    st.markdown(f"**Editing Entry:** {utils.format_date(raw_date)}")
    current_mood = get_mood_key(entry.get("mood_score", 6))
    mood_list = list(MOOD_OPTIONS.values())
    default_index = list(MOOD_OPTIONS.keys()).index(current_mood)

    mood_str = st.selectbox("Overall Mood", mood_list, index=default_index, key=f"edit_mood_{entry['id']}")
    content = st.text_area("Journal Entry", value=entry.get("content", ""), height=260, key=f"edit_content_{entry['id']}")

    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Cancel", key=f"cancel_edit_{entry['id']}", use_container_width=True):
            st.rerun()
    with btn_col2:
        if st.button("Save Changes", type="primary", key=f"save_edit_{entry['id']}", use_container_width=True):
            mood_score = 6
            for k, v in MOOD_OPTIONS.items():
                if v == mood_str:
                    mood_score = 10 if k == "great" else (8 if k == "good" else (6 if k == "neutral" else (4 if k == "poor" else 2)))
            if validate_journal_input(content, raw_date):
                update_journal_db(entry["id"], content, mood_score)


@st.dialog("Delete Journal Entry")
def dialog_delete_journal(entry_id: str) -> None:
    st.error("⚠️ **Confirm Deletion**\n\nThis action cannot be undone.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", key=f"cancel_del_{entry_id}", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Confirm Delete", type="primary", key=f"confirm_del_{entry_id}", use_container_width=True):
            delete_journal_db(entry_id)


@st.dialog("Read Journal Entry")
def dialog_view_journal(entry: Dict[str, Any]) -> None:
    raw_date = datetime.fromisoformat(entry.get("entry_date", utils.today().isoformat())).date()
    mood_score = entry.get("mood_score", 6)
    st.subheader(f"Journal Entry — {utils.format_date(raw_date)}")
    st.markdown(f"**Mood:** {MOOD_OPTIONS.get(get_mood_key(mood_score), '😐 Neutral (5-6)')}")
    st.divider()
    st.markdown(entry.get("content", ""))
    st.divider()
    if st.button("Close", key=f"close_view_{entry['id']}", use_container_width=True):
        st.rerun()


def render_header(all_entries: List[Dict[str, Any]]) -> None:
    col1, col2 = st.columns([0.75, 0.25])
    with col1:
        ui_components.render_hero("📔 Daily Journal", "Reflect on your habit journey, track your mood, and clear your mind.", icon="📔")
    with col2:
        st.write("")
        if st.button("➕ Write Journal Entry", key="header_write_journal", type="primary", use_container_width=True):
            dialog_create_journal(all_entries)


def render_empty_state(all_entries: List[Dict[str, Any]]) -> None:
    ui_components.render_empty_state("✍️", "Your Mind, Your Canvas", "You haven't written any journal entries yet. Start tracking your daily reflections and mental well-being.")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Write First Entry", key="empty_create_journal", type="primary", use_container_width=True):
            dialog_create_journal(all_entries)


def render_toolbar() -> Tuple[str, str, str]:
    st.subheader("Browse Entries")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_query = st.text_input("🔍 Search Reflections", placeholder="Search thoughts, reflections, or dates...", key="search_query")
    with col2:
        time_filter = st.selectbox("📅 Timeframe", ["All Entries", "Today", "Last 7 Days", "Last 30 Days", "This Month"], key="time_filter")
    with col3:
        sort_order = st.selectbox("↕️ Sort By", ["Newest", "Oldest"], key="sort_order")
    return search_query, time_filter, sort_order


def render_journal_card(entry: Dict[str, Any]) -> None:
    entry_id = entry["id"]
    raw_date = datetime.fromisoformat(entry.get("entry_date", utils.today().isoformat())).date()
    formatted_date = utils.format_date(raw_date)
    mood_score = entry.get("mood_score", 6)
    mood_display = MOOD_OPTIONS.get(get_mood_key(mood_score), "😐 Neutral (5-6)")
    content = entry.get("content", "")

    with st.container(border=True):
        st.markdown(f"**{formatted_date}**")
        st.caption(f"Mood: {mood_display}")
        preview = content[:150] + "..." if len(content) > 150 else content
        st.markdown(f"<div style='color:var(--text-secondary); margin-bottom:1rem;'>{preview}</div>", unsafe_allow_html=True)

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("📖 Read", key=f"read_card_{entry_id}", use_container_width=True):
                dialog_view_journal(entry)
        with btn_col2:
            if st.button("✏️ Edit", key=f"edit_card_{entry_id}", use_container_width=True):
                dialog_edit_journal(entry)
        with btn_col3:
            if st.button("🗑️ Delete", key=f"del_card_{entry_id}", use_container_width=True):
                dialog_delete_journal(entry_id)


def render_pagination_controls(total_pages: int) -> None:
    if total_pages <= 1:
        return
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous", key="page_prev", disabled=(st.session_state.journal_page <= 1), use_container_width=True):
            st.session_state.journal_page -= 1
            st.rerun()
    with col2:
        st.markdown(f"<div style='text-align:center; padding-top:0.5rem;'>Page <b>{st.session_state.journal_page}</b> of {total_pages}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("Next ➡️", key="page_next", disabled=(st.session_state.journal_page >= total_pages), use_container_width=True):
            st.session_state.journal_page += 1
            st.rerun()


def main() -> None:
    auth.require_login()
    if not utils.get_setting("allow_journal", True):
        st.error("Journal feature is currently disabled by the administrator.")
        return
    init_session_state()

    user_id = auth.get_user_id()
    if not user_id:
        st.error("User not authenticated.")
        return

    all_entries = fetch_all_journals(user_id)
    render_header(all_entries)

    if not all_entries:
        render_empty_state(all_entries)
        return

    search_query, time_filter, sort_order = render_toolbar()
    st.divider()

    filtered_entries = search_entries(all_entries, search_query)
    filtered_entries = filter_by_timeframe(filtered_entries, time_filter)
    sorted_entries = sort_entries(filtered_entries, sort_order)

    if not sorted_entries:
        st.info("No journal entries match your filters.")
        return

    paginated_entries, total_pages = get_paginated_data(sorted_entries, st.session_state.journal_page, st.session_state.journal_per_page)

    cols = st.columns(2)
    for index, entry in enumerate(paginated_entries):
        with cols[index % 2]:
            render_journal_card(entry)

    render_pagination_controls(total_pages)


if __name__ == "__main__":
    main()