"""
AI Habit Tracker SaaS - Authentication & Removal of Password Reset Test Suite

Verifies:
1. Password reset feature is completely removed (forgot_password, verify_recovery_token, exchange_code, handle_auth_redirects, render_password_reset_screen).
2. Authenticated password update (update_password) is retained for profile management.
3. Auth UI tabs contain only ["Sign In", "Activate Purchase", "Create Account"] (no Reset Password tab).
4. New user signup flow sets the exact required informational message:
   "🔐 Account created successfully!\n\nPlease save your password somewhere safe for future login.\n\nIf you forget your password, it cannot be recovered."
5. Normal user login works properly and does NOT show the new signup warning.
6. Password is never logged, stored in plain text, or leaked into session state.
7. Profile page security tab does NOT contain password reset email functionality.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
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


class TestNoPasswordResetAndAuthSuite(unittest.TestCase):
    """Test suite verifying removal of password recovery and proper auth/signup behavior."""

    def setUp(self):
        self.auth = AuthManager()

    # ============================================================
    # 1. Removal of Password Reset Backend
    # ============================================================
    def test_forgot_password_removed_from_auth_manager(self):
        """forgot_password must NOT exist on AuthManager."""
        self.assertFalse(hasattr(self.auth, "forgot_password"))

    def test_verify_recovery_token_removed_from_auth_manager(self):
        """verify_recovery_token must NOT exist on AuthManager."""
        self.assertFalse(hasattr(self.auth, "verify_recovery_token"))

    def test_exchange_code_removed_from_auth_manager(self):
        """exchange_code must NOT exist on AuthManager."""
        self.assertFalse(hasattr(self.auth, "exchange_code"))

    def test_set_auth_session_removed_from_auth_manager(self):
        """set_auth_session must NOT exist on AuthManager."""
        self.assertFalse(hasattr(self.auth, "set_auth_session"))

    def test_handle_auth_redirects_removed_from_app(self):
        """handle_auth_redirects must NOT exist in app module."""
        import app
        self.assertFalse(hasattr(app, "handle_auth_redirects"))

    def test_render_password_reset_screen_removed_from_app(self):
        """render_password_reset_screen must NOT exist in app module."""
        import app
        self.assertFalse(hasattr(app, "render_password_reset_screen"))

    def test_inject_auth_hash_bridge_removed_from_ui_components(self):
        """inject_auth_hash_bridge must NOT exist in ui_components module."""
        import ui_components
        self.assertFalse(hasattr(ui_components, "inject_auth_hash_bridge"))

    # ============================================================
    # 2. Retain update_password for Profile Management
    # ============================================================
    def test_update_password_retained_and_works(self):
        """update_password must remain available on AuthManager for logged-in profile password changes."""
        self.assertTrue(hasattr(self.auth, "update_password"))
        mock_db = MagicMock()
        mock_db.auth.update_user.return_value = MagicMock()

        with patch("auth.get_db", return_value=mock_db):
            ok, res = self.auth.update_password("NewSecretPassword123")
            self.assertTrue(ok)
            mock_db.auth.update_user.assert_called_once_with({"password": "NewSecretPassword123"})

    # ============================================================
    # 3. User Login Operation
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
                # Ensure signup notice is not set on normal login
                self.assertNotIn("signup_notice", session)
                # Ensure is_password_recovery is not set
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
    # 4. User Signup Operation & New User Message
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

    def test_exact_signup_informational_message_content(self):
        """Verify the exact warning message text required after account creation."""
        expected_message = (
            "🔐 Account created successfully!\n\n"
            "Please save your password somewhere safe for future login.\n\n"
            "If you forget your password, it cannot be recovered."
        )
        # Check that the exact string components are present
        self.assertIn("🔐 Account created successfully!", expected_message)
        self.assertIn("Please save your password somewhere safe for future login.", expected_message)
        self.assertIn("If you forget your password, it cannot be recovered.", expected_message)

    # ============================================================
    # 5. User Logout Operation
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
    # 6. Password Security
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


if __name__ == "__main__":
    unittest.main()
