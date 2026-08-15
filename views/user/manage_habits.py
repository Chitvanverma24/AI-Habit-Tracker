"""

AI Habit Tracker SaaS
Manage Habits Dashboard

"""

import math
from datetime import date, datetime
from typing import List, Dict, Any, Tuple, Set

import streamlit as st

# Local modules
from database import get_db
from auth import auth
import utils
import ui_components



# Session State Initialization

def init_session_state() -> None:
    """Initializes session state variables required for the dashboard."""
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "Cards"
    if "bulk_selected" not in st.session_state:
        st.session_state.bulk_selected = set()
    if "habits_page_num" not in st.session_state:
        st.session_state.habits_page_num = 1
    if "items_per_page" not in st.session_state:
        st.session_state.items_per_page = 10



# Cached Database Queries

@st.cache_data(show_spinner=False, ttl=60)
def fetch_user_habits(user_id: str) -> List[Dict[str, Any]]:
    """Fetches all habits for the user from Supabase."""
    db = get_db()
    try:
        response = (
            db.table("habits")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=60)
def fetch_today_completed_ids(user_id: str) -> Set[str]:
    """Fetches habit IDs completed today to prevent N+1 query issues."""
    db = get_db()
    today_str = utils.today().isoformat()
    try:
        response = (
            db.table("habit_logs")
            .select("habit_id")
            .eq("user_id", user_id)
            .eq("log_date", today_str)
            .eq("status", "completed")
            .execute()
        )
        return {r["habit_id"] for r in response.data}
    except Exception:
        return set()



# Data Loading Functions

def refresh_data() -> None:
    """Clears cached habit data and triggers a Streamlit rerun."""
    fetch_user_habits.clear()
    fetch_today_completed_ids.clear()
    utils.clear_user_caches()
    st.session_state.bulk_selected.clear()
    st.rerun()



# Helper Functions

def toggle_view_mode(mode: str) -> None:
    """Switches between Card and Table view modes."""
    st.session_state.view_mode = mode
    st.session_state.habits_page_num = 1


def toggle_bulk_select(habit_id: str) -> None:
    """Toggles the selection state of a habit for bulk actions."""
    if habit_id in st.session_state.bulk_selected:
        st.session_state.bulk_selected.remove(habit_id)
    else:
        st.session_state.bulk_selected.add(habit_id)


def select_all_habits(habit_ids: List[str]) -> None:
    """Selects or deselects all currently filtered habits."""
    current_set = set(habit_ids)
    if st.session_state.bulk_selected.issuperset(current_set):
        st.session_state.bulk_selected -= current_set
    else:
        st.session_state.bulk_selected |= current_set



# Validation Functions

def validate_habit_input(title: str, target_count: int) -> bool:
    """Validates habit input fields based on schema constraints."""
    if not title or len(title.strip()) < 3 or len(title.strip()) > 100:
        return False
    if target_count < 1:
        return False
    return True


def check_can_create_habit(habits: List[Dict[str, Any]]) -> bool:
    """All users have access to create unlimited habits."""
    return True



# Search, Filter & Sort Functions

def process_habits(
    habits: List[Dict[str, Any]], 
    search: str, 
    freq_filter: str, 
    stat_filter: str, 
    sort_by: str
) -> List[Dict[str, Any]]:
    """Applies search, frequency/status filters, and sorting algorithms."""
    filtered = habits
    
    if search:
        search_lower = search.lower()
        filtered = [h for h in filtered if search_lower in h.get("title", "").lower()]
        
    if freq_filter != "All":
        filtered = [h for h in filtered if str(h.get("frequency", "")).lower() == freq_filter.lower()]
        
    if stat_filter != "All":
        is_active_target = (stat_filter == "Active")
        filtered = [h for h in filtered if h.get("is_active") == is_active_target]
        
    if sort_by == "Newest":
        filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    elif sort_by == "Oldest":
        filtered.sort(key=lambda x: x.get("created_at", ""))
    elif sort_by == "Alphabetical":
        filtered.sort(key=lambda x: x.get("title", "").lower())
    elif sort_by == "Recently Updated":
        filtered.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        
    return filtered


def get_paginated_data(data: List[Any], page: int, per_page: int) -> Tuple[List[Any], int]:
    """Returns a sliced list for pagination and total pages."""
    total_items = len(data)
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
    
    if page > total_pages:
        page = total_pages
    st.session_state.habits_page_num = page
        
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    return data[start_idx:end_idx], total_pages



# Statistics Functions

def render_statistics_cards() -> None:
    """Renders advanced metrics and statistics using utils.py."""
    stats = utils.get_dashboard_statistics()
    pct = stats.get("completion_percentage", 0)
    
    st.subheader("📊 Your Progress")
    
    progress_val = min(max(pct / 100.0, 0.0), 1.0)
    st.progress(progress_val)
    st.caption(f"**{pct}%** of active habits completed today ({stats.get('completed_today', 0)} / {stats.get('total_habits', 0)})")
    
    st.write("")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Active Habits", stats.get("total_habits", 0))
    with col2:
        st.metric("Completed Today", stats.get("completed_today", 0))
    with col3:
        st.metric("Skipped Today", stats.get("skipped_today", 0))
    with col4:
        st.metric("Current Streak", f"{stats.get('current_streak', 0)} Days")
    with col5:
        st.metric("Longest Streak", f"{stats.get('longest_streak', 0)} Days")
        
    st.divider()



# Bulk Action Functions

def perform_bulk_action(action: str, habit_ids: Set[str]) -> None:
    """Executes bulk updates or deletes on selected habits."""
    if not habit_ids:
        st.warning("No habits selected.")
        return
        
    db = get_db()
    ids_list = list(habit_ids)
    now_str = utils.now().isoformat()
    
    try:
        if action == "delete":
            db.table("habit_logs").delete().in_("habit_id", ids_list).execute()
            db.table("habits").delete().in_("id", ids_list).execute()
            st.success(f"Successfully deleted {len(habit_ids)} habits.")
        elif action == "activate":
            db.table("habits").update({"is_active": True, "updated_at": now_str}).in_("id", ids_list).execute()
            st.success(f"Successfully activated {len(habit_ids)} habits.")
        elif action == "deactivate":
            db.table("habits").update({"is_active": False, "updated_at": now_str}).in_("id", ids_list).execute()
            st.success(f"Successfully deactivated {len(habit_ids)} habits.")
            
        refresh_data()
    except Exception as e:
        st.error(f"Failed to perform bulk action: {e}")



# CRUD Helper Functions

def create_habit_db(title: str, description: str, frequency: str, target_count: int) -> None:
    db = get_db()
    user_id = auth.get_user_id()
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
        st.success("Habit created successfully!")
        refresh_data()
    except Exception as e:
        st.error(f"Failed to create habit: {e}")


def update_habit_db(habit_id: str, title: str, description: str, frequency: str, target_count: int) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    now_str = datetime.now().isoformat()
    try:
        db.table("habits").update({
            "title": title.strip(),
            "description": description.strip() if description else None,
            "frequency": frequency.lower(),
            "target_count": target_count,
            "updated_at": now_str
        }).eq("id", habit_id).eq("user_id", user_id).execute()
        st.toast("Habit updated successfully!", icon="✅")
        refresh_data()
    except Exception as e:
        st.error(f"Failed to update habit: {e}")


def delete_habit_db(habit_id: str) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    try:
        db.table("habit_logs").delete().eq("habit_id", habit_id).eq("user_id", user_id).execute()
        db.table("habits").delete().eq("id", habit_id).eq("user_id", user_id).execute()
        st.toast("Habit completely removed!", icon="🗑️")
        refresh_data()
    except Exception as e:
        st.error(f"Failed to delete habit: {e}")


def toggle_habit_status_db(habit_id: str, set_active: bool) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    try:
        db.table("habits").update({
            "is_active": set_active,
            "updated_at": utils.now().isoformat()
        }).eq("id", habit_id).eq("user_id", user_id).execute()
        refresh_data()
    except Exception:
        st.error("Unable to change habit status. Please try again.")


def log_completion_db(habit_id: str) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    today_str = utils.today().isoformat()
    now_str = utils.now().isoformat()
    
    existing = (
        db.table("habit_logs")
        .select("id")
        .eq("habit_id", habit_id)
        .eq("user_id", user_id)
        .eq("log_date", today_str)
        .eq("status", "completed")
        .execute()
    )
    if existing.data:
        st.warning("Habit already logged for today!")
        return
        
    try:
        db.table("habit_logs").insert({
            "habit_id": habit_id,
            "user_id": user_id,
            "log_date": today_str,
            "status": "completed",
            "created_at": now_str,
            "updated_at": now_str
        }).execute()
        refresh_data()
    except Exception:
        st.error("Unable to record habit completion. Please try again.")


def undo_completion_db(habit_id: str) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    today_str = utils.today().isoformat()
    try:
        db.table("habit_logs").delete() \
            .eq("habit_id", habit_id) \
            .eq("user_id", user_id) \
            .eq("log_date", today_str) \
            .eq("status", "completed") \
            .execute()
        refresh_data()
    except Exception:
        st.error("Unable to undo completion. Please try again.")



# Dialogs (Modals)

@st.dialog("Create New Habit")
def dialog_create_habit(can_create: bool = True) -> None:

    title = st.text_input("Habit Title *", max_chars=100, placeholder="e.g., Drink 2L of Water")
    description = st.text_area("Description (Optional)", placeholder="Describe your goal...")
    
    col_a, col_b = st.columns(2)
    with col_a:
        frequency = st.selectbox("Frequency *", ["Daily", "Weekly", "Monthly"])
    with col_b:
        target_count = st.number_input("Target Count *", min_value=1, max_value=100, value=1)
    
    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Cancel", key="cancel_create", use_container_width=True):
            st.rerun()
    with btn_col2:
        if st.button("Save Habit", key="save_create", type="primary", use_container_width=True):
            if validate_habit_input(title, target_count):
                create_habit_db(title, description, frequency, target_count)
            else:
                st.error("Invalid Input: Title must be 3-100 characters and target count at least 1.")


@st.dialog("Edit Habit")
def dialog_edit_habit(habit: Dict[str, Any]) -> None:
    title = st.text_input("Habit Title *", value=habit.get("title", ""), max_chars=100)
    description = st.text_area("Description (Optional)", value=habit.get("description") or "")
    
    frequencies = ["Daily", "Weekly", "Monthly"]
    current_freq = str(habit.get("frequency", "Daily")).title()
    default_index = frequencies.index(current_freq) if current_freq in frequencies else 0
    
    col_a, col_b = st.columns(2)
    with col_a:
        frequency = st.selectbox("Frequency *", frequencies, index=default_index)
    with col_b:
        target_count = st.number_input("Target Count *", min_value=1, max_value=100, value=int(habit.get("target_count", 1)))
        
    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Cancel", key=f"cancel_edit_{habit['id']}", use_container_width=True):
            st.rerun()
    with btn_col2:
        if st.button("Save Changes", type="primary", key=f"save_edit_{habit['id']}", use_container_width=True):
            if validate_habit_input(title, target_count):
                update_habit_db(habit['id'], title, description, frequency, target_count)
            else:
                st.error("Invalid Input: Title must be 3-100 characters and target count at least 1.")


@st.dialog("Delete Confirmation")
def dialog_delete_habit(habit_id: str) -> None:
    st.warning("⚠️ **Are you sure?**\n\nThis will permanently remove the habit and all its execution logs.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", key=f"cancel_del_{habit_id}", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Delete", key=f"confirm_del_{habit_id}", type="primary", use_container_width=True):
            delete_habit_db(habit_id)


@st.dialog("Bulk Delete Confirmation")
def dialog_bulk_delete() -> None:
    count = len(st.session_state.bulk_selected)
    st.error(f"⚠️ **Are you sure you want to permanently delete {count} habit(s)?**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", key="cancel_bulk_del", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Confirm Delete", key="confirm_bulk_del", type="primary", use_container_width=True):
            perform_bulk_action("delete", st.session_state.bulk_selected)



# UI Components

def render_header(can_create: bool) -> None:
    ui_components.render_hero("🎯 Manage Habits", "Build consistency, track routines, and crush your goals.")
    col1, col2 = st.columns([0.75, 0.25])
    with col2:
        if st.button("➕ Create New Habit", key="create_new_habit_top", type="primary", use_container_width=True):
            dialog_create_habit(can_create)
    st.divider()


def render_empty_state_view(can_create: bool) -> None:
    ui_components.render_empty_state(
        "🌱", 
        "Start Your Journey Today", 
        "You haven't created any habits yet. Build a better routine by creating your first habit!"
    )
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Create Your First Habit", key="create_first_habit", type="primary", use_container_width=True):
            dialog_create_habit(can_create)


def render_toolbar() -> Tuple[str, str, str, str]:
    st.subheader("Filters & Options")
    
    col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
    with col1:
        search_query = st.text_input("🔍 Search", placeholder="Title...")
    with col2:
        freq_filter = st.selectbox("📅 Frequency", ["All", "Daily", "Weekly", "Monthly"])
    with col3:
        status_filter = st.selectbox("⚡ Status", ["All", "Active", "Inactive"])
    with col4:
        sort_by = st.selectbox("↕️ Sort", ["Newest", "Oldest", "Alphabetical", "Recently Updated"])
    with col5:
        st.write("")
        st.write("")
        view = st.session_state.view_mode
        if st.button(f"👁️ Switch to {'Table' if view == 'Cards' else 'Cards'}", key="switch_view_mode", use_container_width=True):
            toggle_view_mode("Table" if view == "Cards" else "Cards")
            st.rerun()
            
    return search_query, freq_filter, status_filter, sort_by


def render_bulk_actions(filtered_ids: List[str]) -> None:
    selected_count = len(st.session_state.bulk_selected)
    
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1, 1, 2])
        with col1:
            if st.button("☑️ Select / Deselect All", key="bulk_select_all", use_container_width=True):
                select_all_habits(filtered_ids)
                st.rerun()
                
        if selected_count > 0:
            with col2:
                if st.button("▶️ Activate", key="bulk_activate", type="primary", use_container_width=True):
                    perform_bulk_action("activate", st.session_state.bulk_selected)
            with col3:
                if st.button("⏸️ Deactivate", key="bulk_deactivate", use_container_width=True):
                    perform_bulk_action("deactivate", st.session_state.bulk_selected)
            with col4:
                if st.button("🗑️ Delete", key="bulk_delete", use_container_width=True):
                    dialog_bulk_delete()
            with col5:
                st.markdown(f"<div style='padding-top:0.5rem;'><b>{selected_count}</b> habits selected</div>", unsafe_allow_html=True)


def render_habit_card(habit: Dict[str, Any], is_completed_today: bool) -> None:
    habit_id = habit["id"]
    title = habit.get("title", "Untitled")
    description = habit.get("description", "")
    freq = str(habit.get("frequency", "daily")).title()
    target = habit.get("target_count", 1)
    is_active = habit.get("is_active", True)
    is_selected = habit_id in st.session_state.bulk_selected
    
    with st.container(border=True):
        row1_col1, row1_col2 = st.columns([0.05, 0.95])
        with row1_col1:
            st.checkbox("", value=is_selected, key=f"sel_{habit_id}", on_change=toggle_bulk_select, args=(habit_id,))
            
        with row1_col2:
            col1, col2 = st.columns([0.65, 0.35])
            with col1:
                st.subheader(title)
                status_badge = ui_components.render_badge("Active", "active") if is_active else ui_components.render_badge("Inactive", "inactive")
                freq_badge = ui_components.render_badge(freq, "primary")
                
                st.markdown(f"{status_badge} {freq_badge}", unsafe_allow_html=True)
                st.caption(f"🎯 Target: {target} time(s) per {freq.lower()}")
                
                if description:
                    st.write(description)
                        
            with col2:
                st.write("") 
                if is_active:
                    if is_completed_today:
                        if st.button("↩️ Undo", key=f"undo_{habit_id}", use_container_width=True):
                            undo_completion_db(habit_id)
                    else:
                        if st.button("✅ Complete", key=f"comp_{habit_id}", type="primary", use_container_width=True):
                            log_completion_db(habit_id)
                            
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("✏️", key=f"edit_{habit_id}", use_container_width=True, help="Edit Habit"):
                        dialog_edit_habit(habit)
                with btn_col2:
                    if is_active:
                        if st.button("⏸️", key=f"deact_{habit_id}", use_container_width=True, help="Deactivate"):
                            toggle_habit_status_db(habit_id, False)
                    else:
                        if st.button("▶️", key=f"act_{habit_id}", use_container_width=True, help="Activate"):
                            toggle_habit_status_db(habit_id, True)
                with btn_col3:
                    if st.button("🗑️", key=f"del_{habit_id}", use_container_width=True, help="Delete Habit"):
                        dialog_delete_habit(habit_id)


def render_table_row(habit: Dict[str, Any], is_completed_today: bool) -> None:
    habit_id = habit["id"]
    is_selected = habit_id in st.session_state.bulk_selected
    is_active = habit.get("is_active", True)
    
    col_sel, col_title, col_freq, col_status, col_action, col_edit = st.columns([0.5, 3, 1, 1.5, 2, 2])
    
    with col_sel:
        st.checkbox("", value=is_selected, key=f"tbl_sel_{habit_id}", on_change=toggle_bulk_select, args=(habit_id,))
    with col_title:
        st.write(f"**{habit.get('title', 'Untitled')}**")
    with col_freq:
        st.write(str(habit.get("frequency", "")).title())
    with col_status:
        st.markdown(ui_components.render_badge("Active", "active") if is_active else ui_components.render_badge("Inactive", "inactive"), unsafe_allow_html=True)
    with col_action:
        if is_active:
            if is_completed_today:
                if st.button("Undo", key=f"tbl_undo_{habit_id}", use_container_width=True):
                    undo_completion_db(habit_id)
            else:
                if st.button("Complete", key=f"tbl_comp_{habit_id}", type="primary", use_container_width=True):
                    log_completion_db(habit_id)
    with col_edit:
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("✏️", key=f"tbl_edit_{habit_id}", help="Edit"):
                dialog_edit_habit(habit)
        with b2:
            if is_active:
                if st.button("⏸️", key=f"tbl_deact_{habit_id}", help="Deactivate"):
                    toggle_habit_status_db(habit_id, False)
            else:
                if st.button("▶️", key=f"tbl_act_{habit_id}", help="Activate"):
                    toggle_habit_status_db(habit_id, True)
        with b3:
            if st.button("🗑️", key=f"tbl_del_{habit_id}", help="Delete"):
                dialog_delete_habit(habit_id)


def render_pagination(total_pages: int) -> None:
    if total_pages <= 1:
        return
        
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("⬅️ Previous", key="prev_page", disabled=(st.session_state.habits_page_num <= 1), use_container_width=True):
            st.session_state.habits_page_num -= 1
            st.rerun()
            
    with col2:
        st.markdown(f"<div style='text-align:center; padding-top:0.5rem;'>Page <b>{st.session_state.habits_page_num}</b> of {total_pages}</div>", unsafe_allow_html=True)
        
    with col3:
        if st.button("Next ➡️", key="next_page", disabled=(st.session_state.habits_page_num >= total_pages), use_container_width=True):
            st.session_state.habits_page_num += 1
            st.rerun()



# Main Layout & Rendering

def render_habits_list(habits: List[Dict[str, Any]], completed_ids: Set[str]) -> None:
    if not habits:
        st.info("No habits found matching your criteria.")
        return
        
    if st.session_state.view_mode == "Cards":
        cols = st.columns(2)
        for index, habit in enumerate(habits):
            with cols[index % 2]:
                render_habit_card(habit, habit["id"] in completed_ids)
    else:
        h1, h2, h3, h4, h5, h6 = st.columns([0.5, 3, 1, 1.5, 2, 2])
        h1.markdown("**☑️**")
        h2.markdown("**Title**")
        h3.markdown("**Freq**")
        h4.markdown("**Status**")
        h5.markdown("**Quick Action**")
        h6.markdown("**Manage**")
        
        for habit in habits:
            render_table_row(habit, habit["id"] in completed_ids)
            st.divider()



# Event Handling and Main Function

def main() -> None:
    """Main function combining all components to render the Manage Habits page."""
    auth.require_login()
    init_session_state()
    
    user_id = auth.get_user_id()
    if not user_id:
        st.stop()
        
    raw_habits = fetch_user_habits(user_id)
    completed_ids = fetch_today_completed_ids(user_id)
    can_create = check_can_create_habit(raw_habits)
    
    render_header(can_create)
    
    if not raw_habits:
        render_empty_state_view(can_create)
        return
        
    render_statistics_cards()
    
    search, freq, stat, sort_by = render_toolbar()
    
    filtered_habits = process_habits(raw_habits, search, freq, stat, sort_by)
    filtered_ids = [h["id"] for h in filtered_habits]
    
    st.write("")
    render_bulk_actions(filtered_ids)
    st.write("")
    
    items_per_page = 10 if st.session_state.view_mode == "Cards" else 15
    paginated_habits, total_pages = get_paginated_data(filtered_habits, st.session_state.habits_page_num, items_per_page)
    
    render_habits_list(paginated_habits, completed_ids)
    render_pagination(total_pages)


if __name__ == "__main__":
    main()