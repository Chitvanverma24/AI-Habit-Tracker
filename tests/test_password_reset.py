"""
AI Habit Tracker SaaS - Password Reset Feature Test Suite

Verifies:
1. forgot_password method sends reset email via Supabase Auth.
2. set_session_from_recovery_code exchanges PKCE code for authenticated session.
3. update_password updates password for the active session.
4. Auth error formatting produces user-friendly messages.
5. Session state is properly populated after recovery code exchange.
6. Password is never stored in plain text in session state.
7. Login/signup/logout continue to work correctly.
8. Forgot password handles various error cases.
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from auth import AuthManager, Role


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


class TestPasswordResetFeature(unittest.TestCase):
    """Test suite verifying password reset functionality and proper auth behavior."""

    def setUp(self):
        self.auth = AuthManager()

    # ============================================================
    # 1. forgot_password Method
    # ============================================================
    def test_forgot_password_exists(self):
        """forgot_password must exist on AuthManager."""
        self.assertTrue(hasattr(self.auth, "forgot_password"))

    def test_forgot_password_calls_supabase_reset(self):
        """forgot_password must call Supabase reset_password_for_email with correct args."""
        mock_db = MagicMock()
        redirect_url = "https://ai-habbit-tracker.streamlit.app"

        with patch("auth.get_db", return_value=mock_db):
            ok, err = self.auth.forgot_password("user@example.com", redirect_url)
            self.assertTrue(ok)
            self.assertIsNone(err)
            mock_db.auth.reset_password_for_email.assert_called_once_with(
                "user@example.com",
                {"redirect_to": redirect_url}
            )

    def test_forgot_password_normalizes_email(self):
        """forgot_password must strip and lowercase the email."""
        mock_db = MagicMock()
        redirect_url = "https://ai-habbit-tracker.streamlit.app"

        with patch("auth.get_db", return_value=mock_db):
            self.auth.forgot_password("  User@Example.COM  ", redirect_url)
            mock_db.auth.reset_password_for_email.assert_called_once_with(
                "user@example.com",
                {"redirect_to": redirect_url}
            )

    def test_forgot_password_handles_rate_limit(self):
        """forgot_password must return user-friendly error on rate limit."""
        mock_db = MagicMock()
        mock_db.auth.reset_password_for_email.side_effect = Exception("over_email_send_rate_limit")

        with patch("auth.get_db", return_value=mock_db):
            ok, err = self.auth.forgot_password("user@example.com", "https://example.com")
            self.assertFalse(ok)
            self.assertIn("rate limit", err.lower())

    def test_forgot_password_handles_invalid_email(self):
        """forgot_password must return user-friendly error for invalid email."""
        mock_db = MagicMock()
        mock_db.auth.reset_password_for_email.side_effect = Exception("unable to validate email address")

        with patch("auth.get_db", return_value=mock_db):
            ok, err = self.auth.forgot_password("invalid", "https://example.com")
            self.assertFalse(ok)
            self.assertIn("valid email", err.lower())

    # ============================================================
    # 2. set_session_from_recovery_code Method
    # ============================================================
    def test_set_session_from_recovery_code_exists(self):
        """set_session_from_recovery_code must exist on AuthManager."""
        self.assertTrue(hasattr(self.auth, "set_session_from_recovery_code"))

    def test_set_session_from_recovery_code_success(self):
        """set_session_from_recovery_code must exchange code and populate session state."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="recovery-user-id", email="user@example.com")
        mock_session = MagicMock(access_token="recovery-access-token")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.exchange_code_for_session.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, res = self.auth.set_session_from_recovery_code("test-code-123")
                self.assertTrue(ok)
                self.assertEqual(session.get("auth_user_id"), "recovery-user-id")
                self.assertEqual(session.get("auth_user_email"), "user@example.com")
                self.assertEqual(session.get("auth_token"), "recovery-access-token")
                mock_db.auth.exchange_code_for_session.assert_called_once_with(
                    {"auth_code": "test-code-123"}
                )

    def test_set_session_from_recovery_code_invalid_code(self):
        """set_session_from_recovery_code must return error for invalid/expired code."""
        mock_db = MagicMock()
        mock_db.auth.exchange_code_for_session.side_effect = Exception("invalid code or expired")

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, err = self.auth.set_session_from_recovery_code("bad-code")
                self.assertFalse(ok)
                self.assertNotIn("auth_user_id", session)

    # ============================================================
    # 3. update_password Method (Retained)
    # ============================================================
    def test_update_password_retained_and_works(self):
        """update_password must remain available on AuthManager for password changes."""
        self.assertTrue(hasattr(self.auth, "update_password"))
        mock_db = MagicMock()
        mock_db.auth.update_user.return_value = MagicMock()

        with patch("auth.get_db", return_value=mock_db):
            ok, res = self.auth.update_password("NewSecretPassword123")
            self.assertTrue(ok)
            mock_db.auth.update_user.assert_called_once_with({"password": "NewSecretPassword123"})

    def test_update_password_handles_weak_password(self):
        """update_password must return user-friendly error for weak password."""
        mock_db = MagicMock()
        mock_db.auth.update_user.side_effect = Exception("password should be at least 6 characters")

        with patch("auth.get_db", return_value=mock_db):
            ok, err = self.auth.update_password("ab")
            self.assertFalse(ok)
            self.assertIn("6 characters", err)

    # ============================================================
    # 4. User Login Operation
    # ============================================================
    def test_user_login_success(self):
        """login must authenticate valid credentials and populate session state."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="test-user-id", email="user@example.com")
        mock_session = MagicMock(access_token="test-access-token")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.sign_in_with_password.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, res = self.auth.login("user@example.com", "Password123")
                self.assertTrue(ok)
                self.assertEqual(session.get("auth_user_id"), "test-user-id")
                self.assertEqual(session.get("auth_user_email"), "user@example.com")
                self.assertEqual(session.get("auth_token"), "test-access-token")
                # Ensure is_password_recovery is not set on normal login
                self.assertNotIn("is_password_recovery", session)

    def test_user_login_failure(self):
        """login must return user-friendly error on invalid credentials."""
        mock_db = MagicMock()
        mock_db.auth.sign_in_with_password.side_effect = Exception("invalid login credentials")

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, err = self.auth.login("user@example.com", "WrongPassword")
                self.assertFalse(ok)
                self.assertIn("Invalid email or password", err)

    # ============================================================
    # 5. User Signup Operation
    # ============================================================
    def test_user_signup_success(self):
        """signup must register a user and bind session if returned."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="new-user-id", email="newuser@example.com", identities=["id1"])
        mock_session = MagicMock(access_token="new-token")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.sign_up.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                ok, res = self.auth.signup("newuser@example.com", "SecurePass123", "New User")
                self.assertTrue(ok)
                self.assertEqual(session.get("auth_user_id"), "new-user-id")
                self.assertEqual(session.get("auth_user_email"), "newuser@example.com")

    # ============================================================
    # 6. User Logout Operation
    # ============================================================
    def test_logout_clears_session_state(self):
        """logout must cleanly wipe all session state."""
        mock_db = MagicMock()
        session = MockSessionState({
            "auth_user_id": "test-user-id",
            "auth_user_email": "user@example.com",
            "auth_token": "token-123",
            "_supabase_client": mock_db,
        })
        with patch("streamlit.session_state", session):
            with patch("auth.get_db", return_value=mock_db):
                self.auth.logout()
                self.assertEqual(len(session), 0)
                self.assertFalse(self.auth.is_authenticated())

    # ============================================================
    # 7. Password Security
    # ============================================================
    def test_password_is_never_stored_in_plain_text_in_session(self):
        """Session state must never contain plain text password keys."""
        session = MockSessionState({})
        with patch("streamlit.session_state", session):
            mock_db = MagicMock()
            mock_user = MagicMock(id="user-123", email="user@example.com")
            mock_resp = MagicMock(user=mock_user, session=MagicMock(access_token="tok"))
            mock_db.auth.sign_in_with_password.return_value = mock_resp

            self.auth.login("user@example.com", "SuperSecretPassword999")

            # Check that password value is never in session values or keys
            for k, v in session.items():
                self.assertNotIn("SuperSecretPassword999", str(k))
                self.assertNotIn("SuperSecretPassword999", str(v))
                self.assertNotIn("password", str(k).lower())

    # ============================================================
    # 8. Auth Error Formatting
    # ============================================================
    def test_error_format_rate_limit(self):
        """Rate limit error must be user-friendly."""
        msg = self.auth._format_auth_error(Exception("over_email_send_rate_limit"))
        self.assertIn("rate limit", msg.lower())

    def test_error_format_already_registered(self):
        """Already registered error must be user-friendly."""
        msg = self.auth._format_auth_error(Exception("user already registered"))
        self.assertIn("already exists", msg.lower())

    def test_error_format_invalid_credentials(self):
        """Invalid credentials error must be user-friendly."""
        msg = self.auth._format_auth_error(Exception("invalid login credentials"))
        self.assertIn("invalid email or password", msg.lower())


if __name__ == "__main__":
    unittest.main()
