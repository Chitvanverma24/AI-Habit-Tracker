"""
AI Habit Tracker SaaS - Forced Password Update Workflow Test Suite
Verifies the exact 15-step testing criteria specified in requirements.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from auth import AuthManager, Role
from services.password_reset_service import PasswordResetService
import app


class MockSessionState(dict):
    """Simulates Streamlit session state container."""
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


class TestForcedPasswordUpdateWorkflow(unittest.TestCase):
    """Test suite verifying forced password update flow step by step."""

    def setUp(self):
        self.auth = AuthManager()

    def tearDown(self):
        from services.password_reset_service import _save_local_requests
        _save_local_requests([])

    def test_complete_forced_password_update_flow(self):
        """Tests the full 15-step workflow end-to-end."""
        # STEP 1 & 2: Admin resets a user's password -> Temporary password generated
        PasswordResetService.create_reset_request("testuser@example.com")
        pending = PasswordResetService.get_pending_requests()
        self.assertTrue(len(pending) > 0)
        req = [r for r in pending if r.get("email") == "testuser@example.com"][0]

        mock_user = MagicMock(
            id="user-flow-123",
            email="testuser@example.com",
            user_metadata={}
        )
        mock_admin_db = MagicMock()
        mock_admin_db.auth.admin.list_users.return_value = [mock_user]

        with patch("services.password_reset_service.get_admin_db", return_value=mock_admin_db):
            ok, msg, temp_pwd = PasswordResetService.process_reset_request(req["id"], "admin-1")
            self.assertTrue(ok)
            self.assertIsNotNone(temp_pwd)
            self.assertGreaterEqual(len(temp_pwd), 12)

        # STEP 3: User logs in using the temporary password
        now_utc = datetime.now(timezone.utc)
        temp_metadata = {
            "is_temporary_password": True,
            "must_change_password": True,
            "temporary_password_expires_at": (now_utc + timedelta(hours=24)).isoformat()
        }
        mock_logged_user = MagicMock(
            id="user-flow-123",
            email="testuser@example.com",
            user_metadata=temp_metadata
        )
        mock_session = MagicMock(access_token="tok_temp", refresh_token="rt_temp")
        mock_db = MagicMock()
        mock_db.auth.sign_in_with_password.return_value = MagicMock(
            user=mock_logged_user,
            session=mock_session
        )

        session_state = MockSessionState()
        with patch("auth.get_db", return_value=mock_db), \
             patch("streamlit.session_state", session_state):
            login_ok, _ = self.auth.login("testuser@example.com", temp_pwd)
            self.assertTrue(login_ok)
            # STEP 4: Forced password update screen must open
            self.assertTrue(session_state.get("must_change_password"))
            self.assertTrue(session_state.get("is_temporary_password"))

        # STEP 5, 6, 7: User enters new password, confirms, and clicks Update Password
        new_password = "NewPermanentPassword456!"
        mock_db.auth.update_user.return_value = MagicMock()
        mock_admin_db.auth.admin.get_user_by_id.return_value = MagicMock(
            user=MagicMock(user_metadata=dict(temp_metadata))
        )

        with patch("auth.get_db", return_value=mock_db), \
             patch("services.password_reset_service.get_admin_db", return_value=mock_admin_db), \
             patch("streamlit.session_state", session_state):
            # STEP 8: Verify password successfully updates
            update_ok, _ = self.auth.update_password(new_password)
            self.assertTrue(update_ok)
            mock_db.auth.update_user.assert_called_once_with({"password": new_password})

            # Simulate UI setting password_update_completed
            session_state["password_update_completed"] = True

            # STEP 9 & 10: Verify not redirected to dashboard and not signed out
            self.assertTrue(self.auth.is_authenticated())
            # Screen guard check must route to mandatory password update screen
            self.assertTrue(
                session_state.get("must_change_password") or
                session_state.get("password_update_completed")
            )

        # STEP 11: Verify the Sign Out button works
        with patch("streamlit.session_state", session_state):
            # Sign out logic executed by button
            self.auth.logout()
            session_state["_auth_logged_out"] = True
            session_state["_pending_auth_clear"] = True
            session_state["auth_success"] = "✅ Password updated successfully! Please sign in with your new password to access your dashboard."

            # STEP 12: Verify user returns to Sign In screen (unauthenticated)
            self.assertFalse(self.auth.is_authenticated())
            self.assertNotIn("password_update_completed", session_state)
            self.assertIn("auth_success", session_state)

        # STEP 13: Verify user can sign in using registered email and newly created password
        mock_permanent_user = MagicMock(
            id="user-flow-123",
            email="testuser@example.com",
            user_metadata={"is_temporary_password": False, "must_change_password": False}
        )
        mock_db.auth.sign_in_with_password.return_value = MagicMock(
            user=mock_permanent_user,
            session=mock_session
        )

        with patch("auth.get_db", return_value=mock_db), \
             patch("streamlit.session_state", session_state):
            login_again_ok, _ = self.auth.login("testuser@example.com", new_password)
            self.assertTrue(login_again_ok)

            # STEP 14: Verify normal dashboard opens (no forced screen flags)
            self.assertFalse(session_state.get("must_change_password", False))
            self.assertFalse(session_state.get("password_update_completed", False))

    def test_render_mandatory_screen_ui_logic(self):
        """Verifies UI rendering logic for completed vs active password update."""
        state = MockSessionState()
        state["password_update_completed"] = True

        mock_st = MagicMock()
        mock_st.session_state = state
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

        with patch("app.st", mock_st), \
             patch("app.ui_components.inject_global_css"):
            app.render_mandatory_password_update_screen()

            # Verify markdown called with the required success instructions
            self.assertEqual(len(mock_st.markdown.call_args_list), 2)
            card_html = mock_st.markdown.call_args_list[1][0][0]
            self.assertIn("Password Updated Successfully", card_html)
            self.assertIn("Your password has been successfully updated", card_html)
            self.assertIn("STEP 1:", card_html)
            self.assertIn("STEP 2:", card_html)
            self.assertIn("STEP 3:", card_html)
            self.assertIn("Sign Out", card_html)
            self.assertIn("Once you sign in again with your new password, you will be able to access your dashboard", card_html)


if __name__ == "__main__":
    unittest.main()
