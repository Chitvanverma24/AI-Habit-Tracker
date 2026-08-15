"""

AI Habit Tracker SaaS
License Activation Page — One-Time Purchase Gate

"""

import streamlit as st
from auth import auth
import ui_components
from services.license_service import (activate_purchase_key, check_user_license,
                                     normalize_email, normalize_license_key)


def main() -> None:
    user_id = auth.get_user_id()
    user_email = auth.get_user_email() or ""

    # If logged in and already licensed, redirect
    if user_id:
        existing = check_user_license(user_id, user_email)
        if existing:
            st.success("Your license is active!")
            st.info("Redirecting to dashboard...")
            st.session_state.current_page = "Home"
            st.rerun()
            return

    st.markdown("""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;
                padding: 1.5rem 1rem; text-align: center;">
        <div style="width: 70px; height: 70px; background: linear-gradient(135deg, #eff6ff, #dbeafe);
                    border-radius: 50%; display: flex; align-items: center; justify-content: center;
                    margin-bottom: 1rem; border: 1px solid #bfdbfe;
                    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.12);">
            <span style="font-size: 2.2rem;">🔑</span>
        </div>
        <h2 style="font-size: 1.8rem; font-weight: 800; color: #0f172a; margin-bottom: 0.4rem;
                   letter-spacing: -0.03em;">
            Activate Purchase
        </h2>
        <p style="font-size: 0.95rem; color: #475569; max-width: 460px; line-height: 1.5;
                  margin-bottom: 1rem;">
            Enter your Etsy order details below to activate your account license.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            default_email = st.session_state.get("activated_email") or user_email

            license_key = st.text_input(
                "License Key",
                placeholder="HT-XXXX-XXXX-XXXX-XXXX",
                max_chars=30,
                key="activate_lic_key"
            )

            email_input = st.text_input(
                "Email Address",
                value=default_email,
                placeholder="customer@email.com",
                key="activate_lic_email"
            )

            st.write("")
            if st.button("🔓 Activate Purchase", type="primary", use_container_width=True,
                         key="btn_activate_purchase"):
                clean_key = normalize_license_key(license_key)
                clean_email = normalize_email(email_input)
                if not clean_key:
                    st.error("Invalid license key.")
                elif not clean_email:
                    st.error("Invalid email address.")
                else:
                    with st.spinner("Validating license key..."):
                        success, message = activate_purchase_key(clean_key, clean_email, user_id)
                    if success:
                        st.session_state["activated_email"] = clean_email
                        st.session_state["activated_license"] = clean_key
                        st.session_state["signup_email"] = clean_email
                        st.session_state["signup_lic_key"] = clean_key
                        st.success(f"🎉 {message}")
                        st.balloons()
                        st.cache_data.clear()
                        if auth.is_authenticated():
                            st.session_state.current_page = "Home"
                        else:
                            st.info("Purchase verified! Proceed to Create Account or Sign In.")
                        import time
                        time.sleep(1.2)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

            st.divider()
            st.caption("Don't have a license key? Purchase one from our official Etsy store.")

        if auth.is_authenticated():
            st.write("")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🚪 Sign Out", use_container_width=True, key="lic_signout"):
                    auth.logout()
                    st.session_state.clear()
                    st.rerun()


if __name__ == "__main__":
    main()
