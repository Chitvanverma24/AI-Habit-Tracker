"""

AI Habit Tracker SaaS - Manage Users
Admin user management dashboard to view, search, inspect, and manage user roles.

"""

import math
import pandas as pd
import streamlit as st
from database import get_db
from auth import auth
import utils
import ui_components


def init_session_state() -> None:
    if "admin_users_page" not in st.session_state:
        st.session_state.admin_users_page = 1
    if "delete_confirm" not in st.session_state:
        st.session_state.delete_confirm = None


@st.cache_data(show_spinner=False, ttl=30)
def fetch_users_paginated(caller_user_id: str, page: int = 1, per_page: int = 10,
                          search: str = "", role: str = "All") -> tuple:
    """
    Fetch paginated user profiles with habit & completion counts.
    Uses crash-proof dictionary mapping instead of pandas merge collisions.
    """
    db = get_db()
    try:
        query = db.table("profiles").select("*", count="exact")

        if search:
            query = query.ilike("display_name", f"%{search}%")
        if role == "Admin":
            query = query.eq("is_admin", True)
        elif role == "User":
            query = query.eq("is_admin", False)

        offset = (page - 1) * per_page
        query = query.order("created_at", desc=True).range(offset, offset + per_page - 1)

        result = query.execute()
        total = result.count or 0
        records = result.data or []

        if not records:
            return pd.DataFrame(), total

        profs = pd.DataFrame(records)

        # Get habit counts for this page of users
        user_ids = profs["id"].tolist()
        try:
            habs_res = db.table("habits").select("user_id").in_("user_id", user_ids).execute()
            habs_data = habs_res.data or []
            if habs_data:
                habs_df = pd.DataFrame(habs_data)
                if "user_id" in habs_df.columns:
                    hc_series = habs_df.groupby("user_id").size()
                    profs["total_habits"] = profs["id"].map(hc_series).fillna(0).astype(int)
                else:
                    profs["total_habits"] = 0
            else:
                profs["total_habits"] = 0
        except Exception:
            profs["total_habits"] = 0

        # Get completion counts for this page of users
        try:
            logs_res = (
                db.table("habit_logs")
                .select("user_id")
                .in_("user_id", user_ids)
                .eq("status", "completed")
                .execute()
            )
            logs_data = logs_res.data or []
            if logs_data:
                logs_df = pd.DataFrame(logs_data)
                if "user_id" in logs_df.columns:
                    lc_series = logs_df.groupby("user_id").size()
                    profs["current_streak"] = profs["id"].map(lc_series).fillna(0).astype(int)
                else:
                    profs["current_streak"] = 0
            else:
                profs["current_streak"] = 0
        except Exception:
            profs["current_streak"] = 0

        return profs, total
    except Exception as e:
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), 0


def db_update_role(uid: str, is_admin: bool) -> None:
    ok, msg = utils.update_user_role(uid, is_admin)
    if ok:
        fetch_users_paginated.clear()
        st.cache_data.clear()
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)


def db_delete_user(uid: str) -> None:
    ok, msg = utils.delete_user(uid)
    if ok:
        fetch_users_paginated.clear()
        st.cache_data.clear()
        st.session_state.delete_confirm = None
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)


@st.dialog("User Details")
def dialog_user_details(row: pd.Series, caller_id: str = "") -> None:
    uid = row["id"]
    is_self = (uid == caller_id)

    st.subheader(row.get("display_name", "Unknown User"))
    st.caption(f"User ID: {uid}")
    if is_self:
        st.info("👤 This is your active administrator account.")

    c1, c2 = st.columns(2)
    c1.metric("Habits", row.get("total_habits", 0))
    c2.metric("Completions", f"{row.get('current_streak', 0)} 🔥")

    st.write(f"Role: **{'Admin' if row.get('is_admin') else 'User'}**")

    c3, c4 = st.columns(2)
    if row.get("is_admin"):
        if c3.button("Remove Admin", key=f"rm_{uid}", use_container_width=True, disabled=is_self):
            db_update_role(uid, False)
    else:
        if c3.button("Make Admin", key=f"mk_{uid}", use_container_width=True):
            db_update_role(uid, True)

    if is_self:
        c4.button("Delete User", key=f"del_{uid}", use_container_width=True, disabled=True, help="You cannot delete your own account from the Admin Console.")
    elif st.session_state.delete_confirm == uid:
        st.error("⚠️ Confirm deletion? This will permanently delete user records and cannot be undone.")
        cc1, cc2 = st.columns(2)
        if cc1.button("🗑️ Confirm Delete", type="primary", key=f"cdel_{uid}", use_container_width=True):
            db_delete_user(uid)
        if cc2.button("Cancel", key=f"cncl_{uid}", use_container_width=True):
            st.session_state.delete_confirm = None
            st.rerun()
    else:
        if c4.button("Delete User", key=f"del_{uid}", use_container_width=True):
            st.session_state.delete_confirm = uid
            st.rerun()


def main() -> None:
    auth.require_admin()
    init_session_state()

    ui_components.render_hero("👥 Manage Users", "View, filter, manage permissions, and inspect platform users.", icon="👥")

    caller_id = auth.get_user_id()

    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input("🔍 Search Users", placeholder="Search by name...", key="user_search")
    with col2:
        role = st.selectbox("Role Filter", ["All", "User", "Admin"], key="role_filter")

    per_page = 10
    page = st.session_state.admin_users_page

    filtered_df, total_count = fetch_users_paginated(caller_id, page, per_page, search, role)
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    if page > total_pages:
        st.session_state.admin_users_page = total_pages
        page = total_pages
        filtered_df, total_count = fetch_users_paginated(caller_id, page, per_page, search, role)

    st.markdown(f"Showing **{len(filtered_df)}** of **{total_count:,}** users")

    if filtered_df.empty:
        ui_components.render_empty_state("👥", "No users found", "Try adjusting your search query or filters.")
        return

    for _, row in filtered_df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"**{row.get('display_name','User')}**")
            c1.caption(row['id'])
            c2.write(f"Role: **{'Admin' if row.get('is_admin') else 'User'}**")
            c3.write(f"Habits: **{row.get('total_habits', 0)}** | Completions: **{row.get('current_streak', 0)}**")
            if c4.button("Inspect", key=f"inspect_{row['id']}", use_container_width=True):
                dialog_user_details(row, caller_id)

    if total_pages > 1:
        st.write("")
        pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
        with pcol1:
            if st.button("⬅️ Prev", disabled=(page <= 1), key="prev_users_page"):
                st.session_state.admin_users_page -= 1
                st.rerun()
        with pcol2:
            st.markdown(f"<div style='text-align:center;'>Page <b>{page}</b> of {total_pages}</div>", unsafe_allow_html=True)
        with pcol3:
            if st.button("Next ➡️", disabled=(page >= total_pages), key="next_users_page"):
                st.session_state.admin_users_page += 1
                st.rerun()


if __name__ == "__main__":
    main()