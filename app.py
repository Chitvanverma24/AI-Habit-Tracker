"""

AI Habit Tracker SaaS
Main Application Entry Point — Production Ready Maintenance & Admin Guard

"""

import sys
import traceback
import streamlit as st


# Streamlit Page Configuration (MUST be first)

st.set_page_config(
    page_title="AI Habit Tracker",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Prevent sub-modules from calling set_page_config
st.set_page_config = lambda *args, **kwargs: None

from database import check_database_connection
from auth import auth
import utils
import ui_components
from services.license_service import (check_user_license, check_email_has_active_license,
                                     activate_purchase_key, normalize_email, normalize_license_key,
                                     is_valid_email)


# Session Initialization

def init_session() -> None:
    """Initialize global session state variables."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"


def navigate_to(page_name: str) -> None:
    """Route user to a new page."""
    st.session_state.current_page = page_name



# Maintenance Screen (Production SaaS Design)

def render_maintenance_page() -> None:
    """Renders a full-screen, production-grade SaaS Maintenance Page."""
    sys_name = utils.get_setting("system_name", "AI Habit Tracker")
    support_email = utils.get_setting("support_email", "support@habittracker.ai")

    st.markdown(f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 70vh; padding: 2rem; text-align: center;">
        <div style="width: 90px; height: 90px; background: linear-gradient(135deg, #eff6ff, #dbeafe);
                    border-radius: 50%; display: flex; align-items: center; justify-content: center;
                    margin-bottom: 1.5rem; border: 1px solid #bfdbfe; box-shadow: 0 8px 24px rgba(37, 99, 235, 0.12);">
            <span style="font-size: 3rem;">🛠️</span>
        </div>
        <h1 style="font-size: 2.4rem; font-weight: 800; color: #0f172a; margin-bottom: 0.75rem; letter-spacing: -0.03em;">
            Application Under Maintenance
        </h1>
        <p style="font-size: 1.15rem; color: #475569; max-width: 580px; line-height: 1.6; margin-bottom: 2rem;">
            We're currently performing scheduled maintenance to improve your experience on <strong>{sys_name}</strong>.<br>
            Please check back again shortly.
        </p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 50px; padding: 0.6rem 1.5rem;
                    display: inline-flex; align-items: center; gap: 0.6rem; margin-bottom: 2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
            <span style="width: 10px; height: 10px; background-color: #f59e0b; border-radius: 50%; display: inline-block;"></span>
            <span style="font-size: 0.95rem; color: #334155; font-weight: 600;">Status: Scheduled Upgrades in Progress &bull; Estimated Return: Shortly</span>
        </div>
        <div style="color: #64748b; font-size: 0.9rem; margin-bottom: 1.5rem;">
            Need assistance? Reach out to <a href="mailto:{support_email}" style="color: #2563eb; font-weight: 600; text-decoration: none;">{support_email}</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("🚪 Sign Out", key="maint_logout", use_container_width=True):
            auth.logout()
            st.session_state.clear()
            st.rerun()


def render_license_gate() -> None:
    """Renders the license activation page for unlicensed logged-in users."""
    from views.user import activate_license
    ui_components.inject_global_css()
    activate_license.main()



# Authentication UI

def render_auth_ui() -> None:
    """Renders login, purchase activation, signup, and reset password interface."""
    sys_name = utils.get_setting("system_name", "AI Habit Tracker")
    sys_logo = utils.get_setting("system_logo", "🎯")
    maint_active = bool(utils.get_setting("maintenance_mode", False))
    reg_enabled = bool(utils.get_setting("registration_enabled", True))

    st.markdown(f"""
    <div style="text-align: center; padding: 2rem 0 1rem 0;">
        <div style="display: inline-flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
            <div style="width: 46px; height: 46px; background: linear-gradient(135deg, #2563eb, #1d4ed8);
                        border-radius: 12px; display: flex; align-items: center; justify-content: center;
                        font-size: 1.4rem; color: white; font-weight: 800; box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);">{sys_logo}</div>
            <span style="font-size: 1.6rem; font-weight: 800; color: #0f172a; letter-spacing: -0.03em;">
                {sys_name}
            </span>
        </div>
        <p style="color: #475569; font-size: 0.95rem; margin-top: 0.25rem;">
            Build consistency with data-driven AI insights
        </p>
    </div>
    """, unsafe_allow_html=True)

    if maint_active:
        st.info("🚧 System is currently under maintenance. Only Administrators can sign in.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2, tab3, tab4 = st.tabs(["Sign In", "Activate Purchase", "Create Account", "Reset Password"])

        # Tab 1: Sign In
        with tab1:
            with st.form("login_form"):
                st.markdown("##### Welcome back")
                email = st.text_input("Email", placeholder="you@example.com", key="login_email")
                pwd = st.text_input("Password", type="password", key="login_pwd")
                st.write("")
                if st.form_submit_button("Sign In", type="primary", use_container_width=True):
                    if not email or not pwd:
                        st.error("Please fill in all fields.")
                    else:
                        success, result = auth.login(email, pwd)
                        if success:
                            st.rerun()
                        else:
                            st.error(f"Login failed: {result}")

        # Tab 2: Activate Purchase
        with tab2:
            st.markdown("##### Activate your Etsy purchase")
            st.caption("Enter your unique license key and email to unlock access.")
            with st.form("activate_purchase_form"):
                lic_key_in = st.text_input("License Key", placeholder="HT-XXXX-XXXX-XXXX-XXXX", key="landing_lic_key")
                lic_email_in = st.text_input("Email Address", placeholder="customer@email.com", key="landing_lic_email")
                st.write("")
                if st.form_submit_button("Activate Purchase", type="primary", use_container_width=True):
                    clean_key = normalize_license_key(lic_key_in)
                    clean_email = normalize_email(lic_email_in)
                    if not clean_key:
                        st.error("Invalid license key.")
                    elif not clean_email or not is_valid_email(clean_email):
                        st.error("Invalid email address.")
                    else:
                        success, msg = activate_purchase_key(clean_key, clean_email)
                        if success:
                            st.session_state["activated_email"] = clean_email
                            st.session_state["activated_license"] = clean_key
                            st.session_state["signup_email"] = clean_email
                            st.session_state["signup_lic_key"] = clean_key
                            st.success(f"🎉 {msg} You can now create your account in the 'Create Account' tab.")
                            st.balloons()
                        else:
                            st.error(f"❌ {msg}")

        # Tab 3: Create Account
        with tab3:
            if not reg_enabled:
                st.warning("⚠️ New registrations are temporarily disabled.")
                st.caption("Please contact system administration for access.")
            else:
                prefilled_email = st.session_state.get("activated_email", "")
                prefilled_license = st.session_state.get("activated_license", "")
                with st.form("signup_form"):
                    st.markdown("##### Create your account")
                    if prefilled_email:
                        st.info(f"🔑 License activated for: **{prefilled_email}**")
                    new_name = st.text_input("Full Name", placeholder="John Doe", key="signup_name")
                    new_email = st.text_input("Email", value=prefilled_email, placeholder="you@example.com", key="signup_email")
                    new_pwd = st.text_input("Password", type="password",
                                            help="Must be at least 6 characters", key="signup_pwd")
                    new_lic_key = st.text_input("License Key", value=prefilled_license,
                                                placeholder="HT-XXXX-XXXX-XXXX-XXXX (Optional if purchase already activated above)",
                                                key="signup_lic_key")
                    st.write("")
                    if st.form_submit_button("Create Account", type="primary", use_container_width=True):
                        clean_signup_email = normalize_email(new_email)
                        clean_signup_key = normalize_license_key(new_lic_key)
                        act_email = normalize_email(st.session_state.get("activated_email") or prefilled_email)
                        if not clean_signup_key and clean_signup_email == act_email:
                            clean_signup_key = normalize_license_key(st.session_state.get("activated_license") or prefilled_license)

                        if not new_name or not new_name.strip() or not clean_signup_email or not new_pwd:
                            st.error("Full Name, Email, and Password are required.")
                        elif len(new_pwd) < 6:
                            st.error("Password must be at least 6 characters.")
                        else:
                            lic_check = check_email_has_active_license(clean_signup_email, clean_signup_key)

                            # If license is not active yet for email, but license key is provided, attempt activation
                            if not lic_check and clean_signup_key:
                                act_ok, act_msg = activate_purchase_key(clean_signup_key, clean_signup_email)
                                if act_ok:
                                    lic_check = check_email_has_active_license(clean_signup_email, clean_signup_key)
                                else:
                                    st.error(f"❌ License activation failed: {act_msg}")
                                    lic_check = None

                            if not lic_check:
                                st.error("❌ No active Etsy purchase found for this email. Please enter a valid License Key or activate your purchase in the 'Activate Purchase' tab first.")
                            else:
                                success, result = auth.signup(clean_signup_email, new_pwd, new_name)
                                if success:
                                    st.success("🎉 Account created successfully! Logging you in...")

                                    # Auto-login if session is not active (Confirm Email is disabled)
                                    if not auth.is_authenticated():
                                        login_ok, login_res = auth.login(clean_signup_email, new_pwd)
                                        if not login_ok:
                                            st.error(f"Account created, but automatic sign-in failed: {login_res}")
                                            st.stop()

                                    user_id = auth.get_user_id()
                                    if user_id:
                                        if clean_signup_key:
                                            activate_purchase_key(clean_signup_key, clean_signup_email, user_id)
                                        else:
                                            check_user_license(user_id, clean_signup_email)

                                    st.session_state.pop("activated_email", None)
                                    st.session_state.pop("activated_license", None)
                                    st.session_state.pop("signup_email", None)
                                    st.session_state.pop("signup_lic_key", None)
                                    st.session_state.current_page = "Home"
                                    st.rerun()
                                else:
                                    st.error(f"Signup failed: {result}")


        # Tab 4: Reset Password
        with tab4:
            st.markdown("##### Forgot your password?")
            st.caption("We'll send you a link to reset it.")
            reset_email = st.text_input("Email address", placeholder="you@example.com", key="reset_email")
            if st.button("Send Reset Link", use_container_width=True, key="btn_send_reset"):
                if reset_email:
                    success, err = auth.forgot_password(reset_email)
                    if success:
                        st.success("✅ Reset link sent! Check your inbox.")
                    else:
                        st.error(f"Failed to send reset email: {err}")
                else:
                    st.error("Please enter your email address.")



# Sidebar Navigation

def render_sidebar() -> None:
    """Renders sidebar navigation respecting global settings and RBAC."""
    with st.sidebar:
        ui_components.render_sidebar_brand()

        is_maint = bool(utils.get_setting("maintenance_mode", False))

        # User info
        st.markdown(f"""
        <div style="padding: 0.5rem 0.25rem; margin-bottom: 0.25rem;">
            <div class="sidebar-user-title">{utils.get_display_name()}</div>
            <div class="sidebar-user-email">{auth.get_user_email()}</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # If maintenance mode is active, Admin is restricted to Admin pages only
        if is_maint:
            st.warning("🚧 Maintenance Mode Active\n(Admin Bypass)")

        if not is_maint:
            # Normal user navigation pages dynamically filtered by system settings
            st.markdown('<div class="nav-section-label">MENU</div>', unsafe_allow_html=True)

            user_pages = [("🏠", "Home", "Home")]

            if utils.get_setting("allow_habits", True):
                user_pages.append(("➕", "Add Habit", "Add Habit"))
                user_pages.append(("🎯", "Manage Habits", "Manage Habits"))

            if utils.get_setting("allow_journal", True):
                user_pages.append(("📔", "Journal", "Journal"))

            if utils.get_setting("allow_achievements", True):
                user_pages.append(("🏆", "Achievements", "Achievements"))

            if utils.get_setting("ai_enabled", True):
                user_pages.append(("🤖", "AI Coach", "AI Coach"))

            user_pages.append(("👤", "Profile", "Profile"))

            for icon, label, page in user_pages:
                is_active = st.session_state.current_page == page
                btn_type = "primary" if is_active else "secondary"
                if st.button(f"{icon}  {label}", key=f"nav_{page}",
                            use_container_width=True, type=btn_type):
                    navigate_to(page)
                    st.rerun()

        # Admin section
        if auth.is_admin() and utils.get_setting("allow_admin_panel", True):
            if not is_maint:
                st.divider()
            st.markdown('<div class="nav-section-label">ADMIN CONSOLE</div>', unsafe_allow_html=True)

            admin_pages = [
                ("🛡️", "Admin Home", "Admin Home"),
                ("📈", "User Analytics", "User Analytics"),
                ("👥", "Manage Users", "Manage Users"),
                ("🔑", "Licenses", "Manage Licenses"),
                ("⚙️", "Settings", "Admin Settings"),
            ]

            for icon, label, page in admin_pages:
                is_active = st.session_state.current_page == page
                btn_type = "primary" if is_active else "secondary"
                if st.button(f"{icon}  {label}", key=f"nav_{page}",
                            use_container_width=True, type=btn_type):
                    navigate_to(page)
                    st.rerun()

        st.divider()
        if st.button("🚪  Sign Out", key="nav_logout", use_container_width=True):
            auth.logout()
            st.session_state.clear()
            st.rerun()



# Page Router

def route_page() -> None:
    """Routes to page module, verifying dynamic system settings permissions."""
    page = st.session_state.current_page
    is_maint = bool(utils.get_setting("maintenance_mode", False))
    is_admin = auth.is_admin()

    # Maintenance guard for normal users
    if is_maint and not is_admin:
        render_maintenance_page()
        return

    # If Admin is accessing during maintenance mode, direct to Admin Console
    if is_maint and is_admin and page not in ("Admin Home", "User Analytics", "Manage Users", "Manage Licenses", "Admin Settings"):
        st.session_state.current_page = "Admin Home"
        page = "Admin Home"

    from views.user import (home, add_habit, manage_habits, journal,
                            achievements, habit_coach, profile, activate_license)
    from views.admin import (admin_home, user_analysis, manage_user, admin_settings,
                             manage_licenses)

    PAGE_REGISTRY = {
        "Home": home.main,
        "Add Habit": add_habit.main,
        "Manage Habits": manage_habits.main,
        "Journal": journal.main,
        "Achievements": achievements.main,
        "AI Coach": habit_coach.main,
        "Profile": profile.main,
        "Activate License": activate_license.main,
        "Admin Home": admin_home.main,
        "User Analytics": user_analysis.main,
        "Manage Users": manage_user.main,
        "Manage Licenses": manage_licenses.main,
        "Admin Settings": admin_settings.main,
    }

    # Guard checks for disabled features
    if page == "AI Coach" and not utils.get_setting("ai_enabled", True):
        st.error("AI Coach is currently disabled by the administrator.")
        return
    if page == "Journal" and not utils.get_setting("allow_journal", True):
        st.error("Journal feature is currently disabled by the administrator.")
        return
    if page in ("Add Habit", "Manage Habits") and not utils.get_setting("allow_habits", True):
        st.error("Habits management is currently disabled by the administrator.")
        return
    if page == "Achievements" and not utils.get_setting("allow_achievements", True):
        st.error("Achievements module is currently disabled by the administrator.")
        return

    func = PAGE_REGISTRY.get(page)
    if func:
        if page in ("Admin Home", "User Analytics", "Manage Users", "Manage Licenses", "Admin Settings"):
            auth.require_admin()
        func()
    else:
        st.error(f"Page '{page}' not found.")



# Main Application Loop

def main() -> None:
    ui_components.inject_global_css()
    init_session()

    if not check_database_connection():
        st.error("🚨 System Offline — Unable to connect to database. Please check configuration.")
        return

    if not auth.is_authenticated():
        render_auth_ui()
        return

    auth.refresh_session()

    # Maintenance Mode Guard
    is_maint = bool(utils.get_setting("maintenance_mode", False))
    if is_maint and not auth.is_admin():
        render_maintenance_page()
        return

    # License Gate — require active license for non-admin users
    if not auth.is_admin():
        license_data = check_user_license(auth.get_user_id(), auth.get_user_email())
        if not license_data:
            render_license_gate()
            return

    render_sidebar()

    try:
        route_page()
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        st.error(f"An unexpected error occurred: {str(e)}")
        if st.button("🔄 Refresh Page"):
            st.rerun()

    sys_name = utils.get_setting("system_name", "AI Habit Tracker")
    ui_components.render_footer(sys_name, "2.0.0", utils.today().year)


main()