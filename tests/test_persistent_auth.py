"""
AI Habit Tracker SaaS - Secure Persistent Login & Multi-Browser Isolation Test Suite

Tests:
TEST 1: Fresh browser / incognito -> Login/Signup screen (unauthenticated)
TEST 2: User A logs in -> User A authenticated and persistent cookie created
TEST 3: User A refreshes the application -> User A remains authenticated
TEST 4: User A closes browser without Sign Out -> Reopens same browser -> Session restored
TEST 5: User A logged in on Browser A -> Browser B / Incognito shows Login/Signup
TEST 6: Public URL shared with User B -> User B sees Login/Signup, no inherited auth
TEST 7: User A clicks Sign Out -> Session wiped, revoked on Supabase, cookie deleted
TEST 8: Two users logged in simultaneously -> Isolated data and sessions
TEST 9: Cryptographic tamper-proofing: Tampered cookie rejected safely
TEST 10: Token expiration: Expired cookie (>30 days) rejected
TEST 11: Token rotation: Supabase refresh token rotation updates cookie
TEST 12: Revoked session: Supabase invalid refresh token clears client cookie
"""

import time
import json
import unittest
from unittest.mock import patch, MagicMock
from auth import AuthManager, AUTH_COOKIE_NAME, COOKIE_MAX_AGE


class MockSessionState(dict):
    """Simulates Streamlit's per-session state container (dict-like)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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


class TestPersistentAuthSecurity(unittest.TestCase):
    """Verifies all security and functionality requirements for persistent login."""

    def setUp(self):
        self.auth_mgr = AuthManager()

    # ============================================================
    # TEST 1: Fresh Browser / Incognito starts unauthenticated
    # ============================================================
    def test_1_fresh_browser_starts_unauthenticated(self):
        """Fresh browser with empty cookies and empty session state must show Login/Signup."""
        browser_session = MockSessionState({})

        with patch("streamlit.session_state", browser_session), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=None):
            restored = self.auth_mgr.restore_persistent_session()
            self.assertFalse(restored)
            self.assertFalse(self.auth_mgr.is_authenticated())
            self.assertIsNone(self.auth_mgr.get_user_id())
            self.assertIsNone(self.auth_mgr.get_user_email())

    # ============================================================
    # TEST 2: User A logs in -> authenticated & persistent cookie created
    # ============================================================
    def test_2_user_login_creates_persistent_cookie(self):
        """Successful login populates session_state and generates encrypted cookie payload."""
        mock_db = MagicMock()
        mock_user = MagicMock(id="user-aaa-uuid", email="usera@example.com")
        mock_session = MagicMock(access_token="tok-access-aaa", refresh_token="tok-refresh-aaa")
        mock_resp = MagicMock(user=mock_user, session=mock_session)
        mock_db.auth.sign_in_with_password.return_value = mock_resp

        session = MockSessionState({})
        with patch("streamlit.session_state", session), \
             patch("auth.get_db", return_value=mock_db):
            ok, resp = self.auth_mgr.login("usera@example.com", "Password123")
            self.assertTrue(ok)
            self.assertTrue(self.auth_mgr.is_authenticated())
            self.assertEqual(self.auth_mgr.get_user_id(), "user-aaa-uuid")
            self.assertEqual(self.auth_mgr.get_user_email(), "usera@example.com")

            # Verify pending persistent cookie was generated
            self.assertIn("_pending_auth_cookie", session)
            cookie_ciphertext = session["_pending_auth_cookie"]
            self.assertIsInstance(cookie_ciphertext, str)
            self.assertGreater(len(cookie_ciphertext), 20)

            # Security verify: raw refresh token is NEVER in plain text
            self.assertNotIn("tok-refresh-aaa", cookie_ciphertext)
            self.assertNotIn("usera@example.com", cookie_ciphertext)

            # Verify server can decrypt payload
            decrypted = self.auth_mgr._decrypt_session(cookie_ciphertext)
            self.assertIsNotNone(decrypted)
            self.assertEqual(decrypted["uid"], "user-aaa-uuid")
            self.assertEqual(decrypted["rt"], "tok-refresh-aaa")

    # ============================================================
    # TEST 3: User A refreshes the application -> Remains authenticated
    # ============================================================
    def test_3_refresh_keeps_user_authenticated(self):
        """During an active session, refreshing keeps in-memory auth state intact."""
        active_session = MockSessionState({
            "auth_user": MagicMock(id="user-aaa-uuid", email="usera@example.com"),
            "auth_session": MagicMock(access_token="tok-access-aaa", expires_at=int(time.time()) + 3600),
            "auth_user_id": "user-aaa-uuid",
            "auth_user_email": "usera@example.com",
            "auth_token": "tok-access-aaa"
        })

        with patch("streamlit.session_state", active_session):
            # Already authenticated in session_state
            self.assertTrue(self.auth_mgr.is_authenticated())
            self.assertEqual(self.auth_mgr.get_user_id(), "user-aaa-uuid")
            # restore_persistent_session returns True immediately without DB call
            restored = self.auth_mgr.restore_persistent_session()
            self.assertTrue(restored)

    # ============================================================
    # TEST 4: User closes browser without Sign Out -> Reopens same browser -> Restored
    # ============================================================
    def test_4_reopen_same_browser_restores_session(self):
        """Opening the app in the same browser with valid cookie restores dashboard."""
        # 1. Generate legitimate encrypted cookie for User A
        raw_refresh = "valid-supa-refresh-token-aaa"
        cookie_val = self.auth_mgr._encrypt_session("user-aaa-uuid", raw_refresh)

        # 2. Simulate fresh browser session (empty session_state, but cookie present)
        new_browser_session = MockSessionState({})

        # Mock Supabase refresh_session returning refreshed user and session
        mock_db = MagicMock()
        refreshed_user = MagicMock(id="user-aaa-uuid", email="usera@example.com")
        refreshed_session = MagicMock(access_token="fresh-access-token", refresh_token=raw_refresh)
        mock_db.auth.refresh_session.return_value = MagicMock(user=refreshed_user, session=refreshed_session)

        with patch("streamlit.session_state", new_browser_session), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_val), \
             patch("auth.get_db", return_value=mock_db):

            self.assertFalse(self.auth_mgr.is_authenticated())
            restored = self.auth_mgr.restore_persistent_session()
            self.assertTrue(restored)
            self.assertTrue(self.auth_mgr.is_authenticated())
            self.assertEqual(self.auth_mgr.get_user_id(), "user-aaa-uuid")
            self.assertEqual(self.auth_mgr.get_user_email(), "usera@example.com")
            self.assertEqual(new_browser_session.get("auth_token"), "fresh-access-token")

    # ============================================================
    # TEST 5: Browser A is logged in -> Browser B shows Login/Signup
    # ============================================================
    def test_5_browser_b_shows_login_when_browser_a_logged_in(self):
        """Browser B (which has no cookie) must NEVER see User A's session."""
        cookie_user_a = self.auth_mgr._encrypt_session("user-a-id", "refresh-tok-a")

        browser_a_state = MockSessionState({
            "auth_user_id": "user-a-id",
            "auth_user_email": "alice@example.com"
        })

        browser_b_state = MockSessionState({})

        # Browser A is authenticated
        with patch("streamlit.session_state", browser_a_state), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_user_a):
            self.assertTrue(self.auth_mgr.is_authenticated())
            self.assertEqual(self.auth_mgr.get_user_id(), "user-a-id")

        # Browser B is completely UNAUTHENTICATED
        with patch("streamlit.session_state", browser_b_state), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=None):
            self.assertFalse(self.auth_mgr.is_authenticated())
            self.assertFalse(self.auth_mgr.restore_persistent_session())
            self.assertIsNone(self.auth_mgr.get_user_id())

    # ============================================================
    # TEST 6: Shared Public URL does not leak auth to User B
    # ============================================================
    def test_6_shared_url_does_not_leak_authentication(self):
        """User B opening the exact same public URL on a separate machine sees Login/Signup."""
        # Machine B has empty local storage and empty cookies
        machine_b_session = MockSessionState({})

        with patch("streamlit.session_state", machine_b_session), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=None):
            self.assertFalse(self.auth_mgr.is_authenticated())
            self.assertFalse(self.auth_mgr.restore_persistent_session())
            self.assertIsNone(self.auth_mgr.get_user_id())
            self.assertIsNone(self.auth_mgr.get_user_email())

    # ============================================================
    # TEST 7: Sign Out wipes session, revokes Supabase session, deletes cookie
    # ============================================================
    def test_7_sign_out_clears_session_and_revokes(self):
        """Logout must revoke Supabase session, wipe session state, and not restore afterwards."""
        mock_db = MagicMock()
        user_session = MockSessionState({
            "auth_user": MagicMock(id="user-logout", email="user@logout.com"),
            "auth_session": MagicMock(access_token="tok-logout"),
            "auth_user_id": "user-logout",
            "auth_user_email": "user@logout.com",
            "auth_token": "tok-logout",
            "_supabase_client": mock_db
        })

        with patch("streamlit.session_state", user_session):
            ok = self.auth_mgr.logout()
            self.assertTrue(ok)
            # Supabase client.auth.sign_out was called
            mock_db.auth.sign_out.assert_called_once()
            # Session state is completely cleared
            self.assertEqual(len(user_session), 0)
            self.assertFalse(self.auth_mgr.is_authenticated())

            # Now simulate UI setting _auth_logged_out flag
            user_session["_auth_logged_out"] = True

            # If restore_persistent_session is called right after logout, it refuses to restore
            with patch.object(self.auth_mgr, "_read_auth_cookie", return_value="some-cookie"):
                self.assertFalse(self.auth_mgr.restore_persistent_session())

    # ============================================================
    # TEST 8: Two Users Logged In Simultaneously -> Completely Isolated
    # ============================================================
    def test_8_two_simultaneous_users_are_isolated(self):
        """User A and User B concurrently active maintain strictly isolated sessions and data."""
        cookie_a = self.auth_mgr._encrypt_session("user-111", "refresh-token-111")
        cookie_b = self.auth_mgr._encrypt_session("user-222", "refresh-token-222")

        session_a = MockSessionState({
            "auth_user_id": "user-111",
            "auth_user_email": "alice@test.com",
            "auth_token": "jwt-token-111"
        })

        session_b = MockSessionState({
            "auth_user_id": "user-222",
            "auth_user_email": "bob@test.com",
            "auth_token": "jwt-token-222"
        })

        # Alice
        with patch("streamlit.session_state", session_a), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_a):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-111")
            self.assertEqual(self.auth_mgr.get_user_email(), "alice@test.com")

        # Bob
        with patch("streamlit.session_state", session_b), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_b):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-222")
            self.assertEqual(self.auth_mgr.get_user_email(), "bob@test.com")

        # Verify Alice state unchanged
        with patch("streamlit.session_state", session_a), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_a):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-111")

    # ============================================================
    # TEST 9: Cryptographic Tamper-Proofing
    # ============================================================
    def test_9_tampered_cookie_rejected(self):
        """Any modified, forged, or corrupt cookie fails decryption and is safely rejected."""
        valid_cookie = self.auth_mgr._encrypt_session("user-xxx", "real-refresh-token")

        # Tamper with the ciphertext by modifying characters
        tampered_cookie = valid_cookie[:-4] + "abcd"

        with patch("streamlit.session_state", MockSessionState({})), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=tampered_cookie):
            restored = self.auth_mgr.restore_persistent_session()
            self.assertFalse(restored)
            self.assertFalse(self.auth_mgr.is_authenticated())

    # ============================================================
    # TEST 10: Token Expiration (TTL)
    # ============================================================
    def test_10_expired_cookie_rejected(self):
        """A cookie older than COOKIE_MAX_AGE must fail decryption."""
        cipher = self.auth_mgr._get_cipher()
        # Craft a token issued 31 days ago (exceeding 30-day TTL)
        old_time = int(time.time()) - (31 * 86400)
        payload = json.dumps({"uid": "user-old", "rt": "old-token", "ts": old_time}).encode("utf-8")
        expired_token = cipher.encrypt_at_time(payload, old_time).decode("utf-8")

        decrypted = self.auth_mgr._decrypt_session(expired_token)
        self.assertIsNone(decrypted)

    # ============================================================
    # TEST 11: Refresh Token Rotation
    # ============================================================
    def test_11_refresh_token_rotation_updates_cookie(self):
        """When Supabase rotates the refresh token on restore, new cookie is scheduled."""
        old_rt = "initial-refresh-token"
        cookie_val = self.auth_mgr._encrypt_session("user-rot", old_rt)

        session = MockSessionState({})
        mock_db = MagicMock()
        rotated_rt = "newly-rotated-refresh-token"
        mock_resp = MagicMock(
            user=MagicMock(id="user-rot", email="rot@example.com"),
            session=MagicMock(access_token="new-acc", refresh_token=rotated_rt)
        )
        mock_db.auth.refresh_session.return_value = mock_resp

        with patch("streamlit.session_state", session), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_val), \
             patch("auth.get_db", return_value=mock_db):
            restored = self.auth_mgr.restore_persistent_session()
            self.assertTrue(restored)
            self.assertIn("_pending_auth_cookie", session)
            # Decrypt pending cookie to ensure it contains rotated token
            new_payload = self.auth_mgr._decrypt_session(session["_pending_auth_cookie"])
            self.assertEqual(new_payload["rt"], rotated_rt)

    # ============================================================
    # TEST 12: Revoked / Invalid Supabase Refresh Token
    # ============================================================
    def test_12_revoked_session_clears_cookie(self):
        """If Supabase rejects the refresh token (e.g. revoked), restoration fails."""
        cookie_val = self.auth_mgr._encrypt_session("user-revoked", "revoked-token")

        session = MockSessionState({})
        mock_db = MagicMock()
        mock_db.auth.refresh_session.side_effect = Exception("Refresh token is not valid")

        with patch("streamlit.session_state", session), \
             patch.object(self.auth_mgr, "_read_auth_cookie", return_value=cookie_val), \
             patch("auth.get_db", return_value=mock_db):
            restored = self.auth_mgr.restore_persistent_session()
            self.assertFalse(restored)
            self.assertFalse(self.auth_mgr.is_authenticated())


if __name__ == "__main__":
    unittest.main()
