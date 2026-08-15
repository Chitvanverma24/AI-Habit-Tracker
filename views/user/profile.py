"""

AI Habit Tracker SaaS
User Account & Profile Center

"""
import json
from datetime import datetime
from typing import Dict, Any

import streamlit as st

from database import get_db
from auth import auth
import utils
import ui_components


@st.cache_data(show_spinner=False)
def get_exportable_data(user_id: str) -> str:
    data = utils.app_summary()
    return json.dumps(data, default=str, indent=4)


def refresh_profile_data() -> None:
    get_exportable_data.clear()
    auth.clear_profile_cache()
    utils.clear_user_caches()
    st.rerun()


def update_profile(display_name: str, timezone: str) -> None:
    db = get_db()
    user_id = auth.get_user_id()
    now_str = utils.now().isoformat()
    try:
        db.table("profiles").update({
            "display_name": display_name.strip(),
            "timezone": timezone.strip(),
            "updated_at": now_str
        }).eq("id", user_id).execute()
        refresh_profile_data()
    except Exception as e:
        st.error(f"Failed to update profile: {e}")


def handle_password_reset(email: str) -> None:
    success, error_msg = auth.forgot_password(email)
    if success:
        st.success("Password reset instructions sent to your email!")
    else:
        st.error(f"Failed to send reset email: {error_msg}")


def process_account_deletion() -> None:
    db = get_db()
    user_id = auth.get_user_id()
    if not user_id:
        return
    try:
        # Unlink licenses
        try:
            db.table("licenses").update({"assigned_user_id": None, "activated_by": None}).eq("assigned_user_id", user_id).execute()
        except Exception:
            pass

        # Delete user records
        for tbl in ["habit_logs", "habits", "journal_entries", "achievements", "notifications", "feedback", "subscriptions"]:
            try:
                db.table(tbl).delete().eq("user_id", user_id).execute()
            except Exception:
                pass

        # Delete profile
        db.table("profiles").delete().eq("id", user_id).execute()
        auth.logout()
        st.session_state.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Failed to delete account: {e}")


def handle_logout() -> None:
    if auth.logout():
        st.session_state.clear()
        st.rerun()
    else:
        st.error("Failed to log out.")


@st.dialog("Edit Profile")
def dialog_edit_profile(current_name: str, current_timezone: str) -> None:
    st.markdown("Update your personal details below.")
    new_name = st.text_input("Display Name", value=current_name, max_chars=50, key="edit_profile_name")
    tz_options = ["UTC", "America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Paris", "Asia/Tokyo", "Asia/Kolkata", "Australia/Sydney"]
    if current_timezone not in tz_options:
        tz_options.append(current_timezone)
    new_timezone = st.selectbox("Timezone", tz_options, index=tz_options.index(current_timezone), key="edit_profile_tz")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, key="edit_profile_cancel"):
            st.rerun()
    with col2:
        if st.button("Save Changes", type="primary", use_container_width=True, key="edit_profile_save"):
            if new_name and len(new_name.strip()) >= 2:
                update_profile(new_name, new_timezone)
            else:
                st.error("Display name must be at least 2 characters long.")


@st.dialog("Delete Account")
def dialog_delete_account() -> None:
    st.error("⚠️ **DANGER ZONE**")
    st.markdown("Deleting your account will permanently wipe all your data. **This cannot be undone.**")
    confirmation = st.text_input('Type "DELETE" to confirm', placeholder="DELETE", key="delete_account_confirm")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True, key="delete_account_cancel"):
            st.rerun()
    with col2:
        if st.button("Confirm Deletion", type="primary", use_container_width=True, disabled=(confirmation != "DELETE"), key="delete_account_submit"):
            process_account_deletion()


def render_profile_tab(profile: Dict[str, Any], email: str) -> None:
    display_name = profile.get("display_name", "User")
    initials = display_name[:2].upper() if display_name else "U"
    created_at = profile.get("created_at")
    member_since = utils.format_date(datetime.fromisoformat(created_at).date()) if created_at else "Unknown"
    is_admin = profile.get("is_admin", False)

    role_badge = ui_components.render_badge("ADMIN", "primary") if is_admin else ui_components.render_badge("USER", "active")

    with st.container(border=True):
        col_img, col_info = st.columns([0.15, 0.85])
        with col_img:
            st.markdown(f'<div class="avatar-circle">{initials}</div>', unsafe_allow_html=True)
        with col_info:
            st.markdown(f"<h2>{display_name} {role_badge}</h2>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="info-grid">
                <div class="info-item"><span class="info-label">Email</span><span class="info-value">{email}</span></div>
                <div class="info-item"><span class="info-label">Timezone</span><span class="info-value">{profile.get('timezone', 'UTC')}</span></div>
                <div class="info-item"><span class="info-label">Member Since</span><span class="info-value">{member_since}</span></div>
                <div class="info-item"><span class="info-label">Account Plan</span><span class="info-value">Licensed ✅</span></div>
            </div>
            """, unsafe_allow_html=True)
            st.write("")
            if st.button("✏️ Edit Profile Settings", key="btn_edit_profile"):
                dialog_edit_profile(display_name, profile.get('timezone', 'UTC'))


def render_statistics_tab(user_id: str) -> None:
    stats = utils.get_dashboard_statistics()
    st.subheader("📊 Lifetime Analytics")

    db = get_db()
    completed_res = db.table("habit_logs").select("id", count="exact").eq("user_id", user_id).eq("status", "completed").execute()
    total_completed = completed_res.count if completed_res else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Habits", stats.get("total_habits", 0))
    with col2:
        st.metric("Completed Logs", total_completed)
    with col3:
        st.metric("Current Streak", f"{stats.get('current_streak', 0)} 🔥")
    with col4:
        st.metric("Longest Streak", f"{stats.get('longest_streak', 0)} ⭐")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Completion Rate", f"{stats.get('completion_percentage', 0)}%")
    with col6:
        st.metric("Achievements Unlocked", stats.get("achievements", 0))
    with col7:
        st.metric("Unread Notifications", stats.get("notifications", 0))
    with col8:
        st.metric("AI Coach Ready", "Yes 🤖")


def render_security_tab(email: str, user_id: str) -> None:
    st.subheader("🔒 Security & Data")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### Password Management")
            st.write("Update your account password or request a reset link.")
            with st.expander("🔑 Change Password"):
                with st.form("change_pwd_form"):
                    new_p = st.text_input("New Password", type="password", key="profile_new_pwd", help="Must be at least 6 characters")
                    if st.form_submit_button("Update Password", type="primary", use_container_width=True):
                        if not new_p or len(new_p) < 6:
                            st.error("Password must be at least 6 characters.")
                        else:
                            ok, err = auth.update_password(new_p)
                            if ok:
                                st.success("Password updated successfully!")
                            else:
                                st.error(f"Failed to update password: {err}")
            if st.button("Send Password Reset Email", use_container_width=True, key="btn_reset_pwd"):
                handle_password_reset(email)

    with col2:
        with st.container(border=True):
            st.markdown("### Export Your Data")
            st.write("Download all your habits, logs, journals, and achievements.")
            export_data = get_exportable_data(user_id)
            st.download_button(
                label="📥 Download JSON Export",
                data=export_data,
                file_name=f"habit_tracker_export_{utils.today().isoformat()}.json",
                mime="application/json",
                use_container_width=True,
                key="btn_export_data"
            )

    st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
    st.markdown("### Danger Zone")
    st.write("Permanently remove your account and all associated data. This action cannot be reversed.")
    col_empty, col_btn = st.columns([0.7, 0.3])
    with col_btn:
        if st.button("Delete Account", type="primary", use_container_width=True, key="btn_delete_account"):
            dialog_delete_account()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    col_out1, col_out2 = st.columns([0.8, 0.2])
    with col_out2:
        if st.button("🚪 Sign Out", use_container_width=True, key="btn_sign_out"):
            handle_logout()


def render_main_layout(profile: Dict[str, Any], email: str, user_id: str) -> None:
    tab1, tab2, tab3 = st.tabs(["👤 Profile Overview", "📊 Statistics", "🔒 Security & Data"])
    with tab1:
        render_profile_tab(profile, email)
    with tab2:
        render_statistics_tab(user_id)
    with tab3:
        render_security_tab(email, user_id)


def main() -> None:
    auth.require_login()
    user_id = auth.get_user_id()
    if not user_id:
        st.stop()

    profile = utils.get_user_profile(user_id)
    email = auth.get_user_email()
    if not profile or not email:
        st.error("Failed to load profile data. Please try logging in again.")
        handle_logout()
        st.stop()

    ui_components.render_hero(
        title="Account Center",
        subtitle="Manage your profile, view statistics, and adjust your preferences.",
        icon="👤"
    )
    render_main_layout(profile, email, user_id)


if __name__ == "__main__":
    main()