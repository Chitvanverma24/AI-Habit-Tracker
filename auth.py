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
    """Handles all authentication and Role-Based Access Control (RBAC)."""

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
        """Login existing user. Returns (success: bool, result)."""
        try:
            response = self.db.auth.sign_in_with_password({
                "email": email.strip().lower(),
                "password": password
            })
            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def signup(self, email: str, password: str, display_name: str):
        """Register a new user. Returns (success: bool, result)."""
        try:
            import utils
            if not utils.get_setting("registration_enabled", True):
                return False, "New user registrations are currently disabled by the administrator."
        except Exception:
            pass

        try:
            response = self.db.auth.sign_up({
                "email": email.strip().lower(),
                "password": password,
                "options": {
                    "data": {"display_name": display_name.strip()}
                }
            })
            if response and hasattr(response, "user") and response.user:
                if hasattr(response.user, "identities") and response.user.identities == []:
                    return False, "An account with this email address already exists. Please Sign In."
            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def logout(self):
        """Sign out current user."""
        try:
            self.db.auth.sign_out()
            return True
        except Exception:
            return False

    def forgot_password(self, email: str):
        """Send password reset email. Returns (success: bool, error_msg?)."""
        try:
            self.db.auth.reset_password_email(email.strip().lower())
            return True, None
        except Exception as e:
            return False, self._format_auth_error(e)

    def update_password(self, new_password: str):
        """Update password for the active authenticated session."""
        try:
            response = self.db.auth.update_user({"password": new_password})
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
        """Return current auth session or None."""
        try:
            return self.db.auth.get_session()
        except Exception:
            return None

    def get_user(self):
        """Return current auth user object or None."""
        try:
            return self.db.auth.get_user()
        except Exception:
            return None

    def is_authenticated(self) -> bool:
        """Check whether a user is logged in."""
        return self.get_session() is not None

    def get_user_id(self):
        """Return the current user's UUID or None."""
        user = self.get_user()
        if user is None:
            return None
        try:
            return user.user.id
        except Exception:
            return None

    def get_user_email(self):
        """Return the current user's email or None."""
        user = self.get_user()
        if user is None:
            return None
        try:
            return user.user.email
        except Exception:
            return None

    # --- Profile & Role RBAC ---

    def get_profile(self):
        """Fetch current user's profile from the database (cached in session)."""
        user_id = self.get_user_id()
        if user_id is None:
            return None
        # Cache in session state to avoid repeated DB calls per page render
        cache_key = f"_profile_cache_{user_id}"
        if cache_key in st.session_state:
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
            st.session_state[cache_key] = profile
            return profile
        except Exception:
            return None

    def get_user_role(self) -> str:
        """Return the current user's assigned role string."""
        profile = self.get_profile()
        if not profile:
            return Role.USER
        if profile.get("role"):
            return str(profile["role"]).lower()
        return Role.ADMIN if profile.get("is_admin", False) else Role.USER

    def has_role(self, *allowed_roles: str) -> bool:
        """Check if user has any of the specified roles or is Admin."""
        user_role = self.get_user_role()
        if user_role == Role.ADMIN:
            return True
        allowed_normalized = [r.lower() for r in allowed_roles]
        return user_role in allowed_normalized

    def has_permission(self, permission: str) -> bool:
        """Check if current user's role grants a specific permission."""
        user_role = self.get_user_role()
        perms = Role.get_permissions(user_role)
        return "*" in perms or permission in perms

    def is_admin(self) -> bool:
        """Check if current user has admin privileges (backward compatible)."""
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
        try:
            return self.db.auth.refresh_session()
        except Exception:
            return None

    def clear_profile_cache(self):
        """Clear the cached profile data for the current user."""
        user_id = self.get_user_id()
        if user_id:
            cache_key = f"_profile_cache_{user_id}"
            st.session_state.pop(cache_key, None)



# Global Singleton

auth = AuthManager()