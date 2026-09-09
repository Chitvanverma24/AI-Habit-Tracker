"""

AI Habit Tracker SaaS
Authentication Manager — Supabase Auth

"""

import base64
import hashlib
import json
import time
import urllib.parse
from typing import Set, List, Optional

import streamlit as st
from cryptography.fernet import Fernet

from database import get_db, _get_secret_value

# Secure persistent authentication configuration
AUTH_COOKIE_NAME = "__habit_tracker_auth"
COOKIE_MAX_AGE = 30 * 86400  # 30 days in seconds


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

    # --- Persistent Session Cryptography & Cookie Management ---

    def _get_cipher(self) -> Fernet:
        """Derive an authenticated AES-128-CBC encryption cipher (Fernet) from server SECRET_KEY."""
        secret = _get_secret_value("SECRET_KEY", "secret_key", "SUPABASE_KEY") or "habit-tracker-secure-fallback-salt"
        key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)

    def _encrypt_session(self, user_id: str, refresh_token: str) -> str:
        """Encrypt user ID and Supabase refresh token into a tamper-proof ciphertext.
        Guarantees:
        - Refresh token is NEVER stored or exposed in plain text.
        - HMAC signature prevents client tampering or forgery.
        - Contains timestamp for TTL verification.
        """
        try:
            payload = json.dumps({
                "uid": str(user_id) if user_id is not None else "",
                "rt": str(refresh_token) if refresh_token is not None else "",
                "ts": int(time.time())
            })
            cipher = self._get_cipher()
            encrypted = cipher.encrypt(payload.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception:
            return ""

    def _decrypt_session(self, token_str: str) -> Optional[dict]:
        """Decrypt and verify an encrypted session token.
        Enforces:
        - Signature validity (rejects tampered tokens).
        - Expiration TTL (rejects tokens older than COOKIE_MAX_AGE).
        """
        if not token_str or not isinstance(token_str, str):
            return None
        try:
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(token_str.strip().encode("utf-8"), ttl=COOKIE_MAX_AGE)
            data = json.loads(decrypted.decode("utf-8"))
            if data and data.get("uid") and data.get("rt"):
                return data
            return None
        except Exception:
            return None

    def _read_auth_cookie(self) -> Optional[str]:
        """Read the persistent authentication cookie for the current client from st.context.cookies."""
        try:
            if hasattr(st, "context") and hasattr(st.context, "cookies"):
                cookies = st.context.cookies
                if cookies and AUTH_COOKIE_NAME in cookies:
                    raw_val = cookies.get(AUTH_COOKIE_NAME)
                    if raw_val:
                        return urllib.parse.unquote(str(raw_val).strip())
        except Exception:
            pass
        return None

    def render_set_cookie_script(self, token_str: str) -> None:
        """Render client-side persistent storage update."""
        if not token_str:
            return
        try:
            from components.auth_storage import sync_auth_storage
            sync_auth_storage(action="save", token=token_str, key="_auth_set_storage")
        except Exception:
            pass

    def render_clear_cookie_script(self) -> None:
        """Render client-side persistent storage clear."""
        try:
            from components.auth_storage import sync_auth_storage
            sync_auth_storage(action="clear", key="_auth_clear_storage")
        except Exception:
            pass

    def render_storage_fallback_script(self) -> None:
        """No-op fallback placeholder (managed directly by auth_storage component bridge)."""
        pass

    def restore_persistent_session(self, token_str: Optional[str] = None) -> bool:
        """Attempt to restore user session from the client's persistent storage or cookie.
        Guarantees:
        1. Only inspects THIS client's storage token or cookie.
        2. Validates and decrypts the encrypted session payload with server secret.
        3. Authenticates against Supabase Auth using the decrypted refresh token.
        4. Binds the authenticated session strictly to the current st.session_state.
        5. If invalid or revoked, clears the storage/cookie from the client and returns False.
        """
        # If already authenticated in current session, nothing to do
        if self.is_authenticated():
            return True

        # If user explicitly logged out in this session, do not restore
        if hasattr(st, "session_state") and (st.session_state.get("_auth_logged_out") or st.session_state.get("_auth_logged_out_done")):
            return False

        # Guard against repeating failed restore attempts in the same Streamlit session
        if hasattr(st, "session_state") and st.session_state.get("_auth_restore_attempted"):
            return False

        cookie_val = token_str if token_str else self._read_auth_cookie()
        if not cookie_val:
            return False

        if hasattr(st, "session_state"):
            st.session_state["_auth_restore_attempted"] = True

        payload = self._decrypt_session(cookie_val)
        if not payload:
            self.render_clear_cookie_script()
            if hasattr(st, "session_state"):
                st.session_state["_pending_auth_clear"] = True
            return False

        refresh_token = payload.get("rt")
        if not refresh_token:
            self.render_clear_cookie_script()
            if hasattr(st, "session_state"):
                st.session_state["_pending_auth_clear"] = True
            return False

        try:
            client = self.db
            response = client.auth.refresh_session(refresh_token)
            if response and hasattr(response, "user") and response.user:
                user = response.user
                session = getattr(response, "session", None)
                if session and hasattr(session, "access_token") and hasattr(st, "session_state"):
                    st.session_state["auth_user"] = user
                    st.session_state["auth_session"] = session
                    st.session_state["auth_user_id"] = user.id
                    st.session_state["auth_user_email"] = user.email
                    st.session_state["auth_token"] = session.access_token
                    try:
                        client.postgrest.auth(session.access_token)
                    except Exception:
                        pass
                    st.session_state["_supabase_client"] = client

                    # If refresh token was rotated, schedule updated persistent storage
                    new_rt = getattr(session, "refresh_token", None)
                    if new_rt and new_rt != refresh_token:
                        new_enc = self._encrypt_session(user.id, new_rt)
                        if new_enc:
                            st.session_state["_pending_auth_cookie"] = new_enc
                            st.session_state["_pending_auth_save"] = new_enc

                    return True

            self.render_clear_cookie_script()
            if hasattr(st, "session_state"):
                st.session_state["_pending_auth_clear"] = True
            return False
        except Exception:
            # Refresh token was invalid, expired, revoked, or user deleted
            self.render_clear_cookie_script()
            if hasattr(st, "session_state"):
                st.session_state["_pending_auth_clear"] = True
            return False

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
                    st.session_state.pop("_auth_logged_out", None)
                    st.session_state.pop("_auth_restore_attempted", None)

                    # Create encrypted persistent cookie payload
                    try:
                        if session and hasattr(session, "refresh_token") and session.refresh_token:
                            enc = self._encrypt_session(user.id, session.refresh_token)
                            if enc:
                                st.session_state["_pending_auth_cookie"] = enc
                                st.session_state["_pending_auth_save"] = enc
                    except Exception:
                        pass

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
                    st.session_state.pop("_auth_logged_out", None)
                    st.session_state.pop("_auth_restore_attempted", None)

                    # Create encrypted persistent cookie payload
                    try:
                        if hasattr(session, "refresh_token") and session.refresh_token:
                            enc = self._encrypt_session(response.user.id, session.refresh_token)
                            if enc:
                                st.session_state["_pending_auth_cookie"] = enc
                                st.session_state["_pending_auth_save"] = enc
                    except Exception:
                        pass

            return True, response
        except Exception as e:
            return False, self._format_auth_error(e)

    def logout(self):
        """Sign out current user, revoke session in Supabase, and completely wipe per-session auth state."""
        try:
            if hasattr(st, "session_state") and "_supabase_client" in st.session_state:
                try:
                    st.session_state["_supabase_client"].auth.sign_out()
                except Exception:
                    pass
        except Exception:
            pass

        if hasattr(st, "session_state"):
            for k in ["auth_user", "auth_session", "auth_user_id", "auth_user_email", "auth_token", "_supabase_client", "_pending_auth_cookie", "_pending_auth_save", "_auth_restore_attempted"]:
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

    # ──────────────────────────────────────────────────────────────────────────
    # TEMPORARILY DISABLED — PASSWORD RESET
    # Restore this feature after production domain/email configuration is completed.
    # To re-enable: uncomment the original method bodies below.
    # ──────────────────────────────────────────────────────────────────────────
    def forgot_password(self, email: str, redirect_url: str):
        """Send a password reset email via Supabase Auth + configured SMTP.
        The redirect_url must be allowed in Supabase Dashboard → Redirect URLs."""
        # TEMPORARILY DISABLED — PASSWORD RESET
        # Restore this feature after production domain/email configuration is completed.
        # try:
        #     self.db.auth.reset_password_for_email(
        #         email.strip().lower(),
        #         {"redirect_to": redirect_url}
        #     )
        #     return True, None
        # except Exception as e:
        #     return False, self._format_auth_error(e)
        return False, "Password reset is temporarily disabled until production domain and email configuration is completed."

    def set_session_from_recovery_code(self, code: str):
        """Exchange a PKCE auth code (from Supabase recovery redirect) for an
        authenticated session. Binds the session to current st.session_state."""
        # TEMPORARILY DISABLED — PASSWORD RESET
        # Restore this feature after production domain/email configuration is completed.
        # try:
        #     client = self.db
        #     response = client.auth.exchange_code_for_session({"auth_code": code})
        #     if response and hasattr(response, "user") and response.user:
        #         user = response.user
        #         session = getattr(response, "session", None)
        #         if hasattr(st, "session_state"):
        #             st.session_state["auth_user"] = user
        #             st.session_state["auth_session"] = session
        #             st.session_state["auth_user_id"] = user.id
        #             st.session_state["auth_user_email"] = user.email
        #             if session and hasattr(session, "access_token"):
        #                 st.session_state["auth_token"] = session.access_token
        #                 try:
        #                     client.postgrest.auth(session.access_token)
        #                 except Exception:
        #                     pass
        #             st.session_state["_supabase_client"] = client
        #     return True, response
        # except Exception as e:
        #     return False, self._format_auth_error(e)
        return False, "Password recovery is temporarily disabled until production domain and email configuration is completed."
    # ──────────────────────────────────────────────────────────────────────────
    # END TEMPORARILY DISABLED — PASSWORD RESET
    # ──────────────────────────────────────────────────────────────────────────

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
        """Refresh the authentication session token if needed."""
        if not self.is_authenticated():
            return None
        session = self.get_session()
        # Smart refresh: only refresh if token expires within 5 minutes
        if session and hasattr(session, "expires_at") and session.expires_at:
            if session.expires_at - int(time.time()) > 300:
                return session

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
                # If refresh token was rotated, update persistent cookie
                if hasattr(refreshed.session, "refresh_token") and refreshed.session.refresh_token:
                    user_id = self.get_user_id()
                    if user_id:
                        enc = self._encrypt_session(user_id, refreshed.session.refresh_token)
                        st.session_state["_pending_auth_cookie"] = enc
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