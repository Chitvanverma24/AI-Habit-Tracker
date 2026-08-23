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


import time
import secrets
import hashlib
import base64

# Process-level PKCE verifiers store (shared within Python process across browser tabs)
_PKCE_VERIFIERS: dict[str, float] = {}  # {verifier_string: timestamp}


def _generate_pkce_pair() -> tuple[str, str]:
    """Generates a high-entropy PKCE code_verifier and code_challenge (RFC 7636)."""
    charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
    verifier = "".join(secrets.choice(charset) for _ in range(64))
    sha256_hash = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(sha256_hash).rstrip(b"=").decode("utf-8")
    return verifier, challenge


def _store_pkce_verifier(verifier: str) -> None:
    """Stores verifier with timestamp and prunes expired entries (>1 hour)."""
    now = time.time()
    for k in list(_PKCE_VERIFIERS.keys()):
        if now - _PKCE_VERIFIERS[k] > 3600:
            _PKCE_VERIFIERS.pop(k, None)
    _PKCE_VERIFIERS[verifier] = now


def _get_candidate_pkce_verifiers() -> list[str]:
    """Returns candidate verifiers sorted by most recent first."""
    now = time.time()
    valid = [k for k, ts in _PKCE_VERIFIERS.items() if now - ts <= 3600]
    return sorted(valid, key=lambda k: _PKCE_VERIFIERS[k], reverse=True)


def get_app_url() -> str:
    """
    Returns the appropriate application base URL for redirects (e.g. password resets).
    Prioritizes:
    1. Secret configuration: APP_URL, SITE_URL, REDIRECT_URL, or BASE_URL in st.secrets
    2. Environment variables: APP_URL, SITE_URL, STREAMLIT_APP_URL, STREAMLIT_SERVER_BASE_URL
    3. Production vs Local detection:
       - Production on Streamlit Cloud (Linux container / /mount/src / Streamlit Cloud env):
         https://ai-habbit-tracker.streamlit.app/
       - Local development:
         http://localhost:8501/
    """
    import os
    import sys

    # 1. Check Streamlit secrets
    try:
        if hasattr(st, "secrets"):
            for key in ["APP_URL", "SITE_URL", "REDIRECT_URL", "BASE_URL"]:
                if key in st.secrets and st.secrets[key]:
                    url = str(st.secrets[key]).strip()
                    return url if url.endswith("/") else f"{url}/"
    except Exception:
        pass

    # 2. Check Environment Variables
    for env_key in ["APP_URL", "SITE_URL", "STREAMLIT_APP_URL", "STREAMLIT_SERVER_BASE_URL"]:
        val = os.environ.get(env_key)
        if val and val.strip():
            url = val.strip()
            return url if url.endswith("/") else f"{url}/"

    # 3. Environment detection: Streamlit Cloud vs Local development
    is_cloud = (
        os.path.exists("/mount/src") or
        os.path.exists("/app") or
        os.environ.get("STREAMLIT_SHARING_HOST") is not None or
        os.environ.get("STREAMLIT_SERVER_ENABLE_STATIC_SERVING") == "true" or
        (sys.platform.startswith("linux") and os.environ.get("HOSTNAME", "").startswith("streamlit"))
    )

    if is_cloud:
        return "https://ai-habbit-tracker.streamlit.app/"

    # Default to local development
    return "http://localhost:8501/"


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
        if "otp_expired" in msg_lower or "token has expired" in msg_lower:
            return "The password reset link has expired. Please request a new reset link."
        if "access_denied" in msg_lower:
            return "Access denied or reset link invalid. Please request a new reset link."
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
            for k in ["auth_user", "auth_session", "auth_user_id", "auth_user_email", "auth_token", "_supabase_client", "is_password_recovery"]:
                st.session_state.pop(k, None)
            st.session_state.clear()

        try:
            import utils
            utils.clear_user_caches()
        except Exception:
            pass

        return True

    def forgot_password(self, email: str, redirect_url: Optional[str] = None):
        """Send password reset email using Supabase's built-in flow with environment-aware redirect URL.

        Uses standard reset_password_email() which lets Supabase manage the
        recovery flow.  The previous custom PKCE approach stored the
        code_verifier in session_state / module-level dict, which is
        unavailable when the user opens the email link in a new browser
        tab (new Streamlit session / potentially different worker process).

        Returns (success: bool, error_msg?).
        """
        try:
            target_url = redirect_url or get_app_url()
            if target_url and not target_url.endswith("/"):
                target_url = f"{target_url}/"

            clean_email = email.strip().lower()

            # Use Supabase's standard password reset method.
            # This sends a recovery email whose link redirects back to
            # target_url with either ?code=... (PKCE managed by Supabase)
            # or #access_token=...&type=recovery (implicit flow).
            options = {"redirect_to": target_url} if target_url else {}
            self.db.auth.reset_password_email(clean_email, options=options)

            return True, None
        except Exception as e:
            return False, self._format_auth_error(e)

    def exchange_code(self, auth_code: str):
        """Exchange authorization code (?code=...) for an authenticated session.

        Tries the exchange without a code_verifier first (standard flow
        when no client-side PKCE challenge was sent), then falls back to
        any available candidate verifiers for backward compatibility.
        """
        try:
            import sys
            clean_code = auth_code.strip()
            client = self.db

            # Build ordered list of candidate verifiers to try.
            # None first (no verifier) since forgot_password no longer
            # injects a custom PKCE challenge.
            candidates = [None]

            # Add any session-stored verifier
            if hasattr(st, "session_state") and "_pkce_code_verifier" in st.session_state:
                candidates.append(st.session_state["_pkce_code_verifier"])
            # Add any client-storage verifier
            try:
                stored = client.auth._storage.get_item(f"{client.auth._storage_key}-code-verifier")
                if stored and stored not in candidates:
                    candidates.append(stored)
            except Exception:
                pass
            # Add any process-level verifiers
            for v in _get_candidate_pkce_verifiers():
                if v not in candidates:
                    candidates.append(v)

            last_err = None
            response = None
            for verifier in candidates:
                try:
                    params = {"auth_code": clean_code}
                    if verifier:
                        params["code_verifier"] = verifier
                    response = client.auth.exchange_code_for_session(params)
                    if response and hasattr(response, "user") and response.user:
                        print("[auth] Recovery code exchange succeeded", file=sys.stderr)
                        break
                except Exception as e:
                    last_err = e
                    response = None

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
                    st.session_state["is_password_recovery"] = True
                return True, response
            else:
                print(f"[auth] Recovery code exchange failed: {last_err}", file=sys.stderr)
                return False, self._format_auth_error(last_err or Exception("Failed to exchange authorization code."))
        except Exception as e:
            import sys
            print(f"[auth] Recovery code exchange exception: {e}", file=sys.stderr)
            return False, self._format_auth_error(e)

    def verify_recovery_token(self, token_hash: str):
        """Verify password recovery OTP/token_hash for an authenticated session."""
        try:
            client = self.db
            response = client.auth.verify_otp({"token_hash": token_hash.strip(), "type": "recovery"})
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

    def set_auth_session(self, access_token: str, refresh_token: str = ""):
        """Manually establish an authenticated session from an access token."""
        try:
            client = self.db
            response = client.auth.set_session(access_token.strip(), refresh_token.strip())
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