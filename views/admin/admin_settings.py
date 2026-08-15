"""

AI Habit Tracker SaaS - Platform Settings
Fully functional Admin Settings connected to Supabase backend.

"""

import platform
from datetime import datetime
import streamlit as st
from database import get_db
from auth import auth
import utils
import ui_components


def check_db_health() -> tuple[bool, str]:
    return utils.ping_database()


def handle_setting_change(setting_key: str, widget_key: str) -> None:
    """Callback triggered on widget state change."""
    if widget_key in st.session_state:
        new_val = st.session_state[widget_key]
        success, msg = utils.update_setting(setting_key, new_val)
        if success:
            st.session_state["settings_feedback"] = ("success", f"✅ Setting updated successfully: {setting_key} = {new_val}")
        else:
            st.session_state["settings_feedback"] = ("error", f"❌ {msg}")


def render_setting_row(title: str, description: str, widget_func) -> None:
    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        st.markdown(f"**{title}**<br><span style='color: var(--text-muted); font-size:0.85em;'>{description}</span>", unsafe_allow_html=True)
    with c2:
        widget_func()
    st.divider()


def render_platform_settings() -> None:
    st.subheader("🏢 General Platform Settings")

    curr_name = utils.get_setting("system_name", "AI Habit Tracker")
    curr_email = utils.get_setting("support_email", "support@habittracker.ai")
    curr_tz = utils.get_setting("default_timezone", "UTC")

    tz_options = ["UTC", "America/New_York", "Europe/London", "Asia/Kolkata"]
    tz_index = tz_options.index(curr_tz) if curr_tz in tz_options else 0

    render_setting_row(
        "Platform Name",
        "Public title of the SaaS application",
        lambda: st.text_input(
            "Name",
            value=curr_name,
            label_visibility="collapsed",
            key="s_name",
            on_change=handle_setting_change,
            args=("system_name", "s_name")
        )
    )

    render_setting_row(
        "Support Email",
        "Contact email for support inquiries",
        lambda: st.text_input(
            "Email",
            value=curr_email,
            label_visibility="collapsed",
            key="s_email",
            on_change=handle_setting_change,
            args=("support_email", "s_email")
        )
    )

    render_setting_row(
        "Default Timezone",
        "Default timezone for new users",
        lambda: st.selectbox(
            "TZ",
            tz_options,
            index=tz_index,
            label_visibility="collapsed",
            key="s_tz",
            on_change=handle_setting_change,
            args=("default_timezone", "s_tz")
        )
    )


def render_security_settings() -> None:
    st.subheader("🔐 Security & Access")

    curr_reg = bool(utils.get_setting("registration_enabled", True))
    curr_maint = bool(utils.get_setting("maintenance_mode", False))

    render_setting_row(
        "New User Registration",
        "Allow new users to sign up",
        lambda: st.toggle(
            "Reg Enabled",
            value=curr_reg,
            key="s_reg",
            on_change=handle_setting_change,
            args=("registration_enabled", "s_reg")
        )
    )

    render_setting_row(
        "Maintenance Mode",
        "Temporarily restrict non-admin access",
        lambda: st.toggle(
            "Maint Mode",
            value=curr_maint,
            key="s_maint",
            on_change=handle_setting_change,
            args=("maintenance_mode", "s_maint")
        )
    )


def render_ai_settings() -> None:
    st.subheader("🤖 AI Coach Integration")

    curr_ai = bool(utils.get_setting("ai_enabled", True))
    curr_model = utils.get_setting("selected_ai_model", "gemini-1.5-flash")

    models_list = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash"]
    model_idx = models_list.index(curr_model) if curr_model in models_list else 0

    render_setting_row(
        "Enable AI Coach",
        "Globally enable AI coaching features",
        lambda: st.toggle(
            "AI Enabled",
            value=curr_ai,
            key="s_ai",
            on_change=handle_setting_change,
            args=("ai_enabled", "s_ai")
        )
    )

    render_setting_row(
        "AI Model",
        "Primary Google Gemini model",
        lambda: st.selectbox(
            "Model",
            models_list,
            index=model_idx,
            label_visibility="collapsed",
            key="s_mod",
            on_change=handle_setting_change,
            args=("selected_ai_model", "s_mod")
        )
    )


def render_cache_tools() -> None:
    st.subheader("🛠️ System Tools")
    c1, c2, c3 = st.columns(3)

    if c1.button("🧹 Clear Data Cache", use_container_width=True, key="t_cache"):
        with st.spinner("Clearing data cache..."):
            ok, msg = utils.clear_data_cache()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    if c2.button("🔌 Reset Resource Connections", use_container_width=True, key="t_res"):
        with st.spinner("Resetting connections..."):
            ok, msg = utils.clear_resource_cache()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    if c3.button("📡 Ping Database", use_container_width=True, key="t_db"):
        with st.spinner("Pinging database..."):
            ok, msg = check_db_health()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.write("")
    c4, c5, _ = st.columns([1, 1, 1])
    if c4.button("🔄 Reload Settings", use_container_width=True, key="t_reload"):
        with st.spinner("Reloading settings from Supabase..."):
            utils.reload_settings()
            st.success("Settings reloaded live!")

    if c5.button("⚡ Sync Platform Data", use_container_width=True, key="t_sync"):
        with st.spinner("Synchronizing data..."):
            ok, msg = utils.sync_data()
            if ok:
                st.success(msg)
            else:
                st.error(msg)


def render_system_info(db_health: bool, db_latency: str) -> None:
    st.subheader("💻 System Environment")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("App Version", "v2.0.0-prod")
    c2.metric("Python Version", platform.python_version())
    c3.metric("OS Platform", platform.system())
    c4.metric("DB Status", f"Connected ({db_latency}) 🟢" if db_health else "Disconnected 🔴")


def main() -> None:
    auth.require_admin()
    ui_components.render_hero("⚙️ Platform Settings", "Configure application options, AI integration, and maintenance tools.", icon="⚙️")

    # Display feedback message if setting changed
    if "settings_feedback" in st.session_state:
        kind, text = st.session_state.pop("settings_feedback")
        if kind == "success":
            st.success(text)
        else:
            st.error(text)

    db_health, db_latency = check_db_health()

    t1, t2, t3, t4 = st.tabs(["General & System", "Security", "AI Integration", "System Tools"])
    with t1:
        render_platform_settings()
        st.write("")
        render_system_info(db_health, db_latency)
    with t2:
        render_security_settings()
    with t3:
        render_ai_settings()
    with t4:
        render_cache_tools()


if __name__ == "__main__":
    main()