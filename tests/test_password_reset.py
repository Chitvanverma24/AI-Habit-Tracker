"""
AI Habit Tracker SaaS - Password Reset & Redirect URL Test Suite

Verifies:
1. Environment-aware redirect URL generation (Local vs Cloud vs Secrets vs Env).
2. forgot_password() correctly passes the environment-aware redirect_to option to Supabase.
3. PKCE code exchange flow (exchange_code).
4. OTP recovery token verification flow (verify_recovery_token).
5. Access token session setting (set_auth_session).
6. Password update execution (update_password).
7. handle_auth_redirects query parameter handling (code, token_hash, access_token, error_code).
8. Password reset error formatting.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from auth import AuthManager, get_app_url


class MockSessionState(dict):
    """Simulates Streamlit's per-session state container."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)


class TestPasswordResetRedirectURL(unittest.TestCase):
    """Test environment-aware redirect URLs and password reset flows."""

    def setUp(self):
        self.auth = AuthManager()

    # ============================================================
    # 1. Environment-Aware URL Detection
    # ============================================================
    def test_get_app_url_local_default(self):
        """In local development without cloud markers or secrets, default to localhost:8501."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("streamlit.secrets", {}):
                with patch("os.path.exists", return_value=False):
                    url = get_app_url()
                    self.assertEqual(url, "http://localhost:8501/")

    def test_get_app_url_secrets_override(self):
        """If APP_URL / SITE_URL is defined in secrets, it takes highest precedence."""
        with patch("streamlit.secrets", {"APP_URL": "https://custom-domain.com"}):
            url = get_app_url()
            self.assertEqual(url, "https://custom-domain.com/")

    def test_get_app_url_env_override(self):
        """If APP_URL is in environment variables, it takes precedence over auto-detection."""
        with patch.dict(os.environ, {"APP_URL": "https://env-domain.com"}):
            with patch("streamlit.secrets", {}):
                url = get_app_url()
                self.assertEqual(url, "https://env-domain.com/")

    def test_get_app_url_cloud_detection(self):
        """When running on Streamlit Cloud container (/mount/src exists), return production URL."""
        def mock_exists(path):
            return path == "/mount/src"

        with patch.dict(os.environ, {}, clear=True):
            with patch("streamlit.secrets", {}):
                with patch("os.path.exists", side_effect=mock_exists):
                    url = get_app_url()
                    self.assertEqual(url, "https://ai-habbit-tracker.streamlit.app/")

    # ============================================================
    # 2. forgot_password passing redirect_to
    # ============================================================
    def test_forgot_password_passes_environment_aware_redirect_to(self):
        """forgot_password must pass options={'redirect_to': target_url} to Supabase reset_password_email."""
        mock_db = MagicMock()
        with patch("auth.get_db", return_value=mock_db):
            with patch("auth.get_app_url", return_value="https://ai-habbit-tracker.streamlit.app/"):
                ok, err = self.auth.forgot_password("user@example.com")
                self.assertTrue(ok)
                self.assertIsNone(err)
                mock_db.auth.reset_password_email.assert_called_once_with(
                    "user@example.com",
                    options={"redirect_to": "https://ai-habbit-tracker.streamlit.app/"}
                )

    def test_forgot_password_passes_custom_redirect_url(self):
        """If explicit redirect_url is passed, use it."""
        mock_db = MagicMock()
        with patch("auth.get_db", return_value=mock_db):
            ok, err = self.auth.forgot_password("user@example.com", redirect_url="http://localhost:8501/")
            self.assertTrue(ok)
            mock_db.auth.reset_password_email.assert_called_once_with(
                "user@example.com",
                options={"redirect_to": "http://localhost:8501/"}
            )

    # ============================================================
    # 3. PKCE Code Exchange (exchange_code)
    # ============================================================
    def test_exchange_code_success(self):
        """exchange_code must exchange code for session and populate session state."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="user-pkce", email="pkce@example.com")
        mock_session = MagicMock(access_token="pkce-token")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.exchange_code_for_session.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, res = self.auth.exchange_code("valid-auth-code")
                self.assertTrue(ok)
                mock_db.auth.exchange_code_for_session.assert_called_once_with({"auth_code": "valid-auth-code"})
                self.assertEqual(session.get("auth_user_id"), "user-pkce")
                self.assertEqual(session.get("auth_user_email"), "pkce@example.com")
                self.assertEqual(session.get("auth_token"), "pkce-token")

    # ============================================================
    # 4. OTP / Token Hash Verification (verify_recovery_token)
    # ============================================================
    def test_verify_recovery_token_success(self):
        """verify_recovery_token must call verify_otp and populate session state."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="user-otp", email="otp@example.com")
        mock_session = MagicMock(access_token="otp-token")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.verify_otp.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, res = self.auth.verify_recovery_token("token-hash-123")
                self.assertTrue(ok)
                mock_db.auth.verify_otp.assert_called_once_with({"token_hash": "token-hash-123", "type": "recovery"})
                self.assertEqual(session.get("auth_user_id"), "user-otp")
                self.assertEqual(session.get("auth_user_email"), "otp@example.com")

    # ============================================================
    # 5. Set Auth Session (set_auth_session)
    # ============================================================
    def test_set_auth_session_success(self):
        """set_auth_session must call set_session and populate session state."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="user-direct", email="direct@example.com")
        mock_session = MagicMock(access_token="access-123")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.set_session.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, res = self.auth.set_auth_session("access-123", "refresh-123")
                self.assertTrue(ok)
                mock_db.auth.set_session.assert_called_once_with("access-123", "refresh-123")
                self.assertEqual(session.get("auth_user_id"), "user-direct")

    # ============================================================
    # 6. Update Password (update_password)
    # ============================================================
    def test_update_password_success(self):
        """update_password must call update_user with new password."""
        mock_db = MagicMock()
        mock_db.auth.update_user.return_value = MagicMock()

        with patch("auth.get_db", return_value=mock_db):
            ok, res = self.auth.update_password("NewSecretPassword123")
            self.assertTrue(ok)
            mock_db.auth.update_user.assert_called_once_with({"password": "NewSecretPassword123"})

    # ============================================================
    # 7. Query Params Handling (handle_auth_redirects)
    # ============================================================
    def test_handle_auth_redirects_otp_expired_error(self):
        """When query params contain error=access_denied / error_code=otp_expired, set user-friendly error."""
        from app import handle_auth_redirects
        import streamlit as st

        mock_query_params = MockSessionState({
            "error": "access_denied",
            "error_code": "otp_expired",
            "error_description": "Email link is invalid or has expired"
        })
        mock_session_state = MockSessionState({})

        with patch("streamlit.query_params", mock_query_params):
            with patch("streamlit.session_state", mock_session_state):
                is_recovery = handle_auth_redirects()
                self.assertFalse(is_recovery)
                self.assertIn("auth_error", mock_session_state)
                self.assertIn("expired", mock_session_state["auth_error"].lower())

    def test_handle_auth_redirects_with_pkce_code(self):
        """When query params contain code=..., exchange code and enter recovery mode."""
        from app import handle_auth_redirects
        mock_query_params = MockSessionState({"code": "auth-code-xyz"})
        mock_session_state = MockSessionState({})

        with patch("streamlit.query_params", mock_query_params):
            with patch("streamlit.session_state", mock_session_state):
                with patch.object(self.auth, "exchange_code", return_value=(True, MagicMock())) as mock_exchange:
                    with patch("app.auth", self.auth):
                        is_recovery = handle_auth_redirects()
                        self.assertTrue(is_recovery)
                        mock_exchange.assert_called_once_with("auth-code-xyz")
                        self.assertTrue(mock_session_state.get("is_password_recovery"))

    def test_handle_auth_redirects_with_token_hash_recovery(self):
        """When query params contain token_hash=... and type=recovery, verify token and enter recovery mode."""
        from app import handle_auth_redirects
        mock_query_params = MockSessionState({"token_hash": "hash-abc", "type": "recovery"})
        mock_session_state = MockSessionState({})

        with patch("streamlit.query_params", mock_query_params):
            with patch("streamlit.session_state", mock_session_state):
                with patch.object(self.auth, "verify_recovery_token", return_value=(True, MagicMock())) as mock_verify:
                    with patch("app.auth", self.auth):
                        is_recovery = handle_auth_redirects()
                        self.assertTrue(is_recovery)
                        mock_verify.assert_called_once_with("hash-abc")
                        self.assertTrue(mock_session_state.get("is_password_recovery"))

    def test_handle_auth_redirects_with_access_token(self):
        """When query params contain access_token=... (from hash bridge), establish session and enter recovery mode."""
        from app import handle_auth_redirects
        mock_query_params = MockSessionState({"access_token": "jwt-token-123", "refresh_token": "ref-123", "type": "recovery"})
        mock_session_state = MockSessionState({})

        with patch("streamlit.query_params", mock_query_params):
            with patch("streamlit.session_state", mock_session_state):
                with patch.object(self.auth, "set_auth_session", return_value=(True, MagicMock())) as mock_set_session:
                    with patch("app.auth", self.auth):
                        is_recovery = handle_auth_redirects()
                        self.assertTrue(is_recovery)
                        mock_set_session.assert_called_once_with("jwt-token-123", "ref-123")
                        self.assertTrue(mock_session_state.get("is_password_recovery"))

    def test_handle_auth_redirects_invalid_access_token(self):
        """When access_token fails to establish session, set user-friendly error and stay on login."""
        from app import handle_auth_redirects
        mock_query_params = MockSessionState({"access_token": "expired-token"})
        mock_session_state = MockSessionState({})

        with patch("streamlit.query_params", mock_query_params):
            with patch("streamlit.session_state", mock_session_state):
                with patch.object(self.auth, "set_auth_session", return_value=(False, "JWT expired")):
                    with patch("app.auth", self.auth):
                        is_recovery = handle_auth_redirects()
                        self.assertFalse(is_recovery)
                        self.assertIn("auth_error", mock_session_state)


if __name__ == "__main__":
    unittest.main()

