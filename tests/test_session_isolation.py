"""
AI Habit Tracker SaaS - User Session Isolation & Multi-User Security Test Suite

Verifies:
1. Browser sessions (st.session_state) are completely isolated.
2. Unauthenticated sessions / Incognito start in an unauthenticated state.
3. User B never inherits User A's authentication state, user ID, email, or token.
4. User A's data and caches never leak to User B.
5. Admin privileges never leak to normal users or unauthenticated sessions.
6. Logout completely wipes all authentication and user state.
7. Account switching in the same session cleanly transitions state.
8. Database client is strictly per-session.
"""

import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any


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


class TestSessionIsolationSecurity(unittest.TestCase):
    """Complete multi-user security and session isolation tests."""

    def setUp(self):
        from auth import AuthManager, Role
        self.auth_mgr = AuthManager()

    # ============================================================
    # SCENARIO 1: Completely Separate Browsers / Sessions
    # ============================================================
    def test_browser_a_and_b_session_isolation(self):
        """User A logged in Browser A must NEVER leak into Browser B."""
        browser_a_session = MockSessionState({
            "auth_user": MagicMock(id="user-aaa-uuid", email="userA@example.com"),
            "auth_session": MagicMock(access_token="token-aaa"),
            "auth_user_id": "user-aaa-uuid",
            "auth_user_email": "userA@example.com",
            "auth_token": "token-aaa"
        })

        browser_b_session = MockSessionState({})  # Empty, fresh connection

        # Verify Browser A is authenticated as User A
        with patch("streamlit.session_state", browser_a_session):
            self.assertTrue(self.auth_mgr.is_authenticated())
            self.assertEqual(self.auth_mgr.get_user_id(), "user-aaa-uuid")
            self.assertEqual(self.auth_mgr.get_user_email(), "userA@example.com")

        # Verify Browser B is completely UNAUTHENTICATED
        with patch("streamlit.session_state", browser_b_session):
            self.assertFalse(self.auth_mgr.is_authenticated())
            self.assertIsNone(self.auth_mgr.get_user_id())
            self.assertIsNone(self.auth_mgr.get_user_email())
            self.assertIsNone(self.auth_mgr.get_session())
            self.assertIsNone(self.auth_mgr.get_user())

    # ============================================================
    # SCENARIO 2: Incognito Session Starts Unauthenticated
    # ============================================================
    def test_incognito_starts_unauthenticated(self):
        """Incognito session must have empty auth state and return False for is_authenticated."""
        incognito_session = MockSessionState({})

        with patch("streamlit.session_state", incognito_session):
            self.assertFalse(self.auth_mgr.is_authenticated())
            self.assertIsNone(self.auth_mgr.get_user_id())
            self.assertFalse(self.auth_mgr.is_admin())
            self.assertIsNone(self.auth_mgr.get_profile())

    # ============================================================
    # SCENARIO 3: Different Accounts / Data Isolation
    # ============================================================
    def test_cross_user_data_isolation(self):
        """User A and User B must only access their own user_id and data."""
        session_a = MockSessionState({
            "auth_user": MagicMock(id="user-111", email="alice@example.com"),
            "auth_session": MagicMock(access_token="token-alice"),
            "auth_user_id": "user-111",
            "auth_user_email": "alice@example.com",
            "auth_token": "token-alice"
        })

        session_b = MockSessionState({
            "auth_user": MagicMock(id="user-222", email="bob@example.com"),
            "auth_session": MagicMock(access_token="token-bob"),
            "auth_user_id": "user-222",
            "auth_user_email": "bob@example.com",
            "auth_token": "token-bob"
        })

        # Check Alice
        with patch("streamlit.session_state", session_a):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-111")
            self.assertEqual(self.auth_mgr.get_user_email(), "alice@example.com")

        # Check Bob
        with patch("streamlit.session_state", session_b):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-222")
            self.assertEqual(self.auth_mgr.get_user_email(), "bob@example.com")

        # Ensure Bob's state did NOT overwrite Alice's state
        with patch("streamlit.session_state", session_a):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-111")
            self.assertEqual(self.auth_mgr.get_user_email(), "alice@example.com")

    # ============================================================
    # SCENARIO 4: Logout Completely Clears Authentication State
    # ============================================================
    def test_logout_wipes_all_session_state(self):
        """Logout must remove all auth keys, clear profile cache, and mark unauthenticated."""
        user_session = MockSessionState({
            "auth_user": MagicMock(id="user-logout-test", email="logout@example.com"),
            "auth_session": MagicMock(access_token="token-logout"),
            "auth_user_id": "user-logout-test",
            "auth_user_email": "logout@example.com",
            "auth_token": "token-logout",
            "_profile_cache_user-logout-test": {"id": "user-logout-test", "display_name": "Test User"}
        })

        with patch("streamlit.session_state", user_session):
            self.assertTrue(self.auth_mgr.is_authenticated())

            # Perform logout
            ok = self.auth_mgr.logout()
            self.assertTrue(ok)

            # Assert all auth keys removed
            self.assertFalse(self.auth_mgr.is_authenticated())
            self.assertIsNone(self.auth_mgr.get_user_id())
            self.assertIsNone(self.auth_mgr.get_user_email())
            self.assertIsNone(self.auth_mgr.get_session())
            self.assertEqual(len(user_session), 0)

    # ============================================================
    # SCENARIO 5: Admin Privilege Isolation
    # ============================================================
    def test_admin_privilege_never_leaks_to_normal_user(self):
        """Admin status of User A must NEVER grant admin to User B or Unauthenticated."""
        admin_session = MockSessionState({
            "auth_user": MagicMock(id="admin-user-id", email="admin@example.com"),
            "auth_session": MagicMock(access_token="token-admin"),
            "auth_user_id": "admin-user-id",
            "auth_user_email": "admin@example.com",
            "auth_token": "token-admin",
            "_profile_cache_admin-user-id": {"id": "admin-user-id", "is_admin": True, "role": "admin"}
        })

        normal_user_session = MockSessionState({
            "auth_user": MagicMock(id="normal-user-id", email="normal@example.com"),
            "auth_session": MagicMock(access_token="token-normal"),
            "auth_user_id": "normal-user-id",
            "auth_user_email": "normal@example.com",
            "auth_token": "token-normal",
            "_profile_cache_normal-user-id": {"id": "normal-user-id", "is_admin": False, "role": "user"}
        })

        unauthenticated_session = MockSessionState({})

        # 1. Admin session has admin
        with patch("streamlit.session_state", admin_session):
            self.assertTrue(self.auth_mgr.is_admin())

        # 2. Normal user session does NOT have admin
        with patch("streamlit.session_state", normal_user_session):
            self.assertFalse(self.auth_mgr.is_admin())
            self.assertEqual(self.auth_mgr.get_user_role(), "user")

        # 3. Unauthenticated session does NOT have admin
        with patch("streamlit.session_state", unauthenticated_session):
            self.assertFalse(self.auth_mgr.is_admin())
            self.assertEqual(self.auth_mgr.get_user_role(), "user")

    # ============================================================
    # SCENARIO 6: Login Switching in Same Session
    # ============================================================
    def test_login_switching_in_same_session(self):
        """Logging out User A and logging in User B in same session must cleanly isolate state."""
        session = MockSessionState({
            "auth_user": MagicMock(id="user-first", email="first@example.com"),
            "auth_session": MagicMock(access_token="token-first"),
            "auth_user_id": "user-first",
            "auth_user_email": "first@example.com",
            "auth_token": "token-first"
        })

        with patch("streamlit.session_state", session):
            self.assertEqual(self.auth_mgr.get_user_id(), "user-first")

            # Logout User A
            self.auth_mgr.logout()
            self.assertFalse(self.auth_mgr.is_authenticated())

            # Now login User B
            session["auth_user"] = MagicMock(id="user-second", email="second@example.com")
            session["auth_session"] = MagicMock(access_token="token-second")
            session["auth_user_id"] = "user-second"
            session["auth_user_email"] = "second@example.com"
            session["auth_token"] = "token-second"

            self.assertTrue(self.auth_mgr.is_authenticated())
            self.assertEqual(self.auth_mgr.get_user_id(), "user-second")
            self.assertEqual(self.auth_mgr.get_user_email(), "second@example.com")

    # ============================================================
    # SCENARIO 7: Database Client Per-Session Isolation
    # ============================================================
    def test_database_client_per_session_isolation(self):
        """get_db() must return session-bound client without cross-contaminating other sessions."""
        from database import get_db

        session_1 = MockSessionState({"auth_token": "jwt-token-user-1"})
        session_2 = MockSessionState({"auth_token": "jwt-token-user-2"})

        with patch("streamlit.session_state", session_1):
            with patch("database.create_client") as mock_create:
                client_1 = MagicMock()
                mock_create.return_value = client_1
                res_1 = get_db()
                self.assertIn("_supabase_client", session_1)
                self.assertEqual(session_1["_supabase_client"], client_1)

        with patch("streamlit.session_state", session_2):
            with patch("database.create_client") as mock_create:
                client_2 = MagicMock()
                mock_create.return_value = client_2
                res_2 = get_db()
                self.assertIn("_supabase_client", session_2)
                self.assertEqual(session_2["_supabase_client"], client_2)
                # Clients must be completely independent instances
                self.assertIsNot(session_1["_supabase_client"], session_2["_supabase_client"])

    # ============================================================
    # SCENARIO 8: Cached Data Isolation Across Users
    # ============================================================
    def test_cached_user_data_isolation(self):
        """User A's cached metrics must never return for User B when called without arguments."""
        import utils
        utils.clear_user_caches()

        session_user_a = MockSessionState({
            "auth_user": MagicMock(id="user-aaa", email="a@test.com"),
            "auth_session": MagicMock(access_token="tok-a"),
            "auth_user_id": "user-aaa",
            "auth_user_email": "a@test.com",
            "auth_token": "tok-a"
        })

        session_user_b = MockSessionState({
            "auth_user": MagicMock(id="user-bbb", email="b@test.com"),
            "auth_session": MagicMock(access_token="tok-b"),
            "auth_user_id": "user-bbb",
            "auth_user_email": "b@test.com",
            "auth_token": "tok-b"
        })

        session_unauth = MockSessionState({})

        # Mock database response per user
        mock_db = MagicMock()

        def mock_table(table_name):
            query = MagicMock()
            if table_name == "habits":
                def mock_eq(field, val):
                    eq_mock = MagicMock()
                    if field == "user_id":
                        count_val = 5 if val == "user-aaa" else (2 if val == "user-bbb" else 0)
                        eq_mock.eq.return_value.execute.return_value = MagicMock(count=count_val, data=[])
                    return eq_mock
                query.select.return_value.eq.side_effect = mock_eq
            elif table_name == "profiles":
                def mock_eq(field, val):
                    eq_mock = MagicMock()
                    name = "Alice User" if val == "user-aaa" else ("Bob User" if val == "user-bbb" else "Unknown")
                    eq_mock.single.return_value.execute.return_value = MagicMock(data={"id": val, "display_name": name})
                    return eq_mock
                query.select.return_value.eq.side_effect = mock_eq
            return query

        mock_db.table.side_effect = mock_table

        with patch("database.get_db", return_value=mock_db), patch("utils.get_db", return_value=mock_db):
            # In session A:
            with patch("streamlit.session_state", session_user_a):
                count_a = utils.get_total_habits()
                name_a = utils.get_display_name()
                self.assertEqual(count_a, 5)
                self.assertEqual(name_a, "Alice User")

            # In session B:
            with patch("streamlit.session_state", session_user_b):
                count_b = utils.get_total_habits()
                name_b = utils.get_display_name()
                self.assertEqual(count_b, 2)
                self.assertEqual(name_b, "Bob User")

            # In unauthenticated session:
            with patch("streamlit.session_state", session_unauth):
                count_unauth = utils.get_total_habits()
                name_unauth = utils.get_display_name()
                self.assertEqual(count_unauth, 0)
                self.assertEqual(name_unauth, "User")

    # ============================================================
    # SCENARIO 9: License Check Caching Isolation
    # ============================================================
    def test_license_caching_isolation(self):
        """User A's license status must never be returned for User B."""
        from services.license_service import check_user_license, _fetch_user_license
        _fetch_user_license.clear()

        mock_db = MagicMock()

        def mock_table(table_name):
            query = MagicMock()
            if table_name == "licenses":
                def mock_or(cond):
                    chain = MagicMock()
                    if "user-licensed" in cond:
                        chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                            data=[{"id": "lic-1", "status": "active", "assigned_user_id": "user-licensed"}]
                        )
                    else:
                        chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                    return chain

                def mock_ilike(field, email):
                    chain = MagicMock()
                    chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                    return chain

                query.select.return_value.or_.side_effect = mock_or
                query.select.return_value.ilike.side_effect = mock_ilike
            return query

        mock_db.table.side_effect = mock_table

        with patch("services.license_service.get_db", return_value=mock_db):
            # User with license
            lic_a = check_user_license("user-licensed", "licensed@example.com")
            self.assertIsNotNone(lic_a)
            self.assertEqual(lic_a.get("id"), "lic-1")

            # User without license
            lic_b = check_user_license("user-unlicensed", "unlicensed@example.com")
            self.assertIsNone(lic_b)

            # Unauthenticated / empty user
            lic_none = check_user_license("", None)
            self.assertIsNone(lic_none)


if __name__ == "__main__":
    unittest.main()
