"""

AI Habit Tracker SaaS
Authentication Manager — Supabase Auth

"""

import streamlit as st
from database import get_db


from typing import Set, List, Optional


class Role:
    """Extensible Role Registry."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"
    COACH = "coach"
    ANALYST = "analyst"

    @classmethod
    def all_roles(cls) -> List[str]:
        return [cls.USER, cls.ADMIN, cls.MODERATOR, cls.COACH, cls.ANALYST]

    @classmethod
    def get_permissions(cls, role_name: str) -> Set[str]:
        permissions_matrix = {
            cls.USER: {"view_dashboard", "manage_habits", "write_journal", "use_ai_coach"},
            cls.COACH: {"view_dashboard", "manage_habits", "write_journal", "use_ai_coach", "view_analytics"},
            cls.MODERATOR: {"view_dashboard", "manage_habits", "write_journal", "use_ai_coach", "view_analytics", "manage_content"},
            cls.ANALYST: {"view_dashboard", "view_analytics", "export_data"},
            cls.ADMIN: {"*"}  # Wildcard grant for full admin access
        }
        return permissions_matrix.get(role_name.lower(), {cls.USER})





class AuthManager:
    """Handles all authentication and Role-Based Access Control (RBAC).
    Guarantees strict per-session user isolation in Streamlit."""

    @property
    def db(self):
        return get_db()

    def _format_auth_error(self, err: Exception) -> str:
        """Parse raw Supabase Auth errors into clean user-friendly messages."""
        msg = str(err)
        msg_lower = msg.lower()
        if "rate limit" in msg_lower or "over_email_send_rate_limit" in msg_lower or "email_rate_limit" in msg_lower:
            return "Email rate limit reached by the authentication provider. Please wait a few minutes before trying again."
        if "user already registered" in msg_lower or "already exists" in msg_lower:
            return "An account with this email address already exists. Please Sign In."
        if "invalid login credentials" in msg_lower or "invalid_credentials" in msg_lower:
            return "Invalid email or password. Please check your credentials and try again."
        if "email not confirmed" in msg_lower:
            return "Email address not verified. Please check your inbox for the confirmation email."
        if "password should be at least" in msg_lower:
            return "Password must be at least 6 characters long."
        if "invalid email" in msg_lower or "unable to validate email" in msg_lower:
            return "Please enter a valid email address."
        return msg

    # --- Core Auth Operations ---

    def login(self, email: str, password: str):
        """Login user and bind authenticated session strictly to the current st.session_state."""
        try:
            client = self.db
            response = client.auth.sign_in_with_password({
                "email": email.strip().lower(),
                "password": password
            })
            if response and hasattr(response, "user") and response.user:
                user = response.user
                session = getattr(response, "session", None)
                if hasattr(st, "session_state"):
                    st.session_state["auth_user"] = user
                    st.session_state["auth_session"] = session
                    st.session_state["auth_user_id"] = user.id
                    st.session_state["auth_user_email"] = user.email
                    if session and hasattr(session, "access_token"):
                        st.session_state["auth_token"] = session.access_token
                        try:
                            client.postgrest.auth(session.access_token)
                        except Exception:
                            pass
                    st.session_state["_supabase_client"] = client
            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def signup(self, email: str, password: str, display_name: str):
        """Register a new user. If session is returned, bind to current st.session_state."""
        try:
            import utils
            if not utils.get_setting("registration_enabled", True):
                return False, "New user registrations are currently disabled by the administrator."
        except Exception:
            pass

        try:
            client = self.db
            response = client.auth.sign_up({
                "email": email.strip().lower(),
                "password": password,
                "options": {
                    "data": {"display_name": display_name.strip()}
                }
            })
            if response and hasattr(response, "user") and response.user:
                if hasattr(response.user, "identities") and response.user.identities == []:
                    return False, "An account with this email address already exists. Please Sign In."
                session = getattr(response, "session", None)
                if session and hasattr(st, "session_state"):
                    st.session_state["auth_user"] = response.user
                    st.session_state["auth_session"] = session
                    st.session_state["auth_user_id"] = response.user.id
                    st.session_state["auth_user_email"] = response.user.email
                    if hasattr(session, "access_token"):
                        st.session_state["auth_token"] = session.access_token
                        try:
                            client.postgrest.auth(session.access_token)
                        except Exception:
                            pass
                    st.session_state["_supabase_client"] = client
            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def logout(self):
        """Sign out current user and completely wipe per-session auth state."""
        try:
            if hasattr(st, "session_state") and "_supabase_client" in st.session_state:
                try:
                    st.session_state["_supabase_client"].auth.sign_out()
                except Exception:
                    pass
        except Exception:
            pass

        if hasattr(st, "session_state"):
            for k in ["auth_user", "auth_session", "auth_user_id", "auth_user_email", "auth_token", "_supabase_client"]:
                st.session_state.pop(k, None)
            st.session_state.clear()

        try:
            import utils
            utils.clear_user_caches()
        except Exception:
            pass

        return True

    def update_password(self, new_password: str):
        """Update password for the active authenticated session."""
        try:
            response = self.db.auth.update_user({"password": new_password})
            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def forgot_password(self, email: str, redirect_url: str):
        """Send a password reset email via Supabase Auth + configured SMTP.
        The redirect_url must be allowed in Supabase Dashboard → Redirect URLs."""
        try:
            self.db.auth.reset_password_for_email(
                email.strip().lower(),
                {"redirect_to": redirect_url}
            )
            return True, None
        except Exception as e:
            return False, self._format_auth_error(e)

    def set_session_from_recovery_code(self, code: str):
        """Exchange a PKCE auth code (from Supabase recovery redirect) for an
        authenticated session. Binds the session to current st.session_state."""
        try:
            client = self.db
            response = client.auth.exchange_code_for_session({"auth_code": code})
            if response and hasattr(response, "user") and response.user:
                user = response.user
                session = getattr(response, "session", None)
                if hasattr(st, "session_state"):
                    st.session_state["auth_user"] = user
                    st.session_state["auth_session"] = session
                    st.session_state["auth_user_id"] = user.id
                    st.session_state["auth_user_email"] = user.email
                    if session and hasattr(session, "access_token"):
                        st.session_state["auth_token"] = session.access_token
                        try:
                            client.postgrest.auth(session.access_token)
                        except Exception:
                            pass
                    st.session_state["_supabase_client"] = client
            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def resend_verification_email(self, email: str):
        """Resend verification email."""
        try:
            self.db.auth.resend({"type": "signup", "email": email.strip().lower()})
            return True, None
        except Exception as e:
            return False, self._format_auth_error(e)


    # --- Session & User Queries ---

    def get_session(self):
        """Return current per-session auth session or None."""
        if hasattr(st, "session_state"):
            return st.session_state.get("auth_session")
        return None

    def get_user(self):
        """Return current per-session auth user object or None."""
        if hasattr(st, "session_state"):
            user = st.session_state.get("auth_user")
            if user is not None:
                class UserWrapper:
                    def __init__(self, u):
                        self.user = u
                return UserWrapper(user)
        return None

    def is_authenticated(self) -> bool:
        """Check whether the current Streamlit session has an active logged-in user."""
        if hasattr(st, "session_state"):
            return bool(st.session_state.get("auth_user_id"))
        return False

    def get_user_id(self) -> Optional[str]:
        """Return the current session's user UUID or None."""
        if hasattr(st, "session_state"):
            return st.session_state.get("auth_user_id")
        return None

    def get_user_email(self) -> Optional[str]:
        """Return the current session's user email or None."""
        if hasattr(st, "session_state"):
            return st.session_state.get("auth_user_email")
        return None

    # --- Profile & Role RBAC ---

    def get_profile(self):
        """Fetch current user's profile from the database (cached in current session)."""
        user_id = self.get_user_id()
        if not user_id:
            return None
        # Cache in session state to avoid repeated DB calls per page render
        cache_key = f"_profile_cache_{user_id}"
        if hasattr(st, "session_state") and cache_key in st.session_state:
            return st.session_state[cache_key]
        try:
            response = (
                self.db.table("profiles")
                .select("*")
                .eq("id", user_id)
                .single()
                .execute()
            )
            profile = response.data
            if hasattr(st, "session_state"):
                st.session_state[cache_key] = profile
            return profile
        except Exception:
            return None

    def get_user_role(self) -> str:
        """Return the current user's assigned role string."""
        if not self.is_authenticated():
            return Role.USER
        profile = self.get_profile()
        if not profile:
            return Role.USER
        if profile.get("role"):
            return str(profile["role"]).lower()
        return Role.ADMIN if profile.get("is_admin", False) else Role.USER

    def has_role(self, *allowed_roles: str) -> bool:
        """Check if user has any of the specified roles or is Admin."""
        if not self.is_authenticated():
            return False
        user_role = self.get_user_role()
        if user_role == Role.ADMIN:
            return True
        allowed_normalized = [r.lower() for r in allowed_roles]
        return user_role in allowed_normalized

    def has_permission(self, permission: str) -> bool:
        """Check if current user's role grants a specific permission."""
        if not self.is_authenticated():
            return False
        user_role = self.get_user_role()
        perms = Role.get_permissions(user_role)
        return "*" in perms or permission in perms

    def is_admin(self) -> bool:
        """Check if current user has admin privileges (backward compatible)."""
        if not self.is_authenticated():
            return False
        return self.has_role(Role.ADMIN)

    # --- Route Protection & Guards ---

    def require_login(self):
        """Halt execution if user is not logged in."""
        if not self.is_authenticated():
            st.warning("Please login to continue.")
            st.stop()

    def require_role(self, *roles: str):
        """Halt execution if user does not possess any of the required roles."""
        self.require_login()
        if not self.has_role(*roles):
            st.error(f"⛔ Access Denied — Requires one of roles: {', '.join(roles)}.")
            st.stop()

    def require_permission(self, permission: str):
        """Halt execution if user lacks a required permission."""
        self.require_login()
        if not self.has_permission(permission):
            st.error(f"⛔ Access Denied — Lacks required permission: '{permission}'.")
            st.stop()

    def require_admin(self):
        """Halt execution if user is not an admin."""
        self.require_role(Role.ADMIN)

    # --- Session Management ---

    def refresh_session(self):
        """Refresh the authentication session token."""
        if not self.is_authenticated():
            return None
        try:
            refreshed = self.db.auth.refresh_session()
            if refreshed and hasattr(refreshed, "session") and refreshed.session and hasattr(st, "session_state"):
                st.session_state["auth_session"] = refreshed.session
                if hasattr(refreshed.session, "access_token"):
                    st.session_state["auth_token"] = refreshed.session.access_token
                    try:
                        self.db.postgrest.auth(refreshed.session.access_token)
                    except Exception:
                        pass
            return refreshed
        except Exception:
            return None

    def clear_profile_cache(self):
        """Clear the cached profile data for the current user."""
        user_id = self.get_user_id()
        if user_id and hasattr(st, "session_state"):
            cache_key = f"_profile_cache_{user_id}"
            st.session_state.pop(cache_key, None)



# Global Singleton

auth = AuthManager()