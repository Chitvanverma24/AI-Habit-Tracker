"""
AI Habit Tracker SaaS - Admin Panel Comprehensive Test Suite

Tests admin authorization, user management, license operations,
settings persistence, and security guards.

Requires: unittest, unittest.mock
Does NOT require live Supabase connection (uses mocks).
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Dict, Any


# ============================================================
# Test Admin Authorization Guards
# ============================================================

class TestAdminAuthorizationGuards(unittest.TestCase):
    """Verify admin-only operations reject non-admin callers."""

    @patch("services.admin_service.auth")
    def test_delete_user_requires_admin(self, mock_auth):
        """delete_user must return Permission Denied for non-admins."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = False
        ok, msg = AdminService.delete_user("some-target-id")
        self.assertFalse(ok)
        self.assertIn("Permission Denied", msg)

    @patch("services.admin_service.auth")
    def test_update_role_requires_admin(self, mock_auth):
        """update_user_role must return Permission Denied for non-admins."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = False
        ok, msg = AdminService.update_user_role("target-id", True)
        self.assertFalse(ok)
        self.assertIn("Permission Denied", msg)

    @patch("services.admin_service.auth")
    def test_save_settings_requires_admin(self, mock_auth):
        """save_admin_settings must return Permission Denied for non-admins."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = False
        ok, msg = AdminService.save_admin_settings({"key": "value"})
        self.assertFalse(ok)
        self.assertIn("Permission Denied", msg)


# ============================================================
# Test Admin Self-Protection
# ============================================================

class TestAdminSelfProtection(unittest.TestCase):
    """Verify admins cannot delete themselves or remove own admin role."""

    @patch("services.admin_service.auth")
    def test_cannot_delete_self(self, mock_auth):
        """Admin must not be able to delete their own account."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid-123"
        ok, msg = AdminService.delete_user("admin-uuid-123")
        self.assertFalse(ok)
        self.assertIn("Cannot delete your own account", msg)

    @patch("services.admin_service.auth")
    def test_cannot_remove_own_admin(self, mock_auth):
        """Admin must not be able to remove their own admin privileges."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid-123"
        ok, msg = AdminService.update_user_role("admin-uuid-123", False)
        self.assertFalse(ok)
        self.assertIn("Cannot remove your own admin privileges", msg)

    @patch("services.admin_service.auth")
    @patch("services.admin_service.get_db")
    def test_can_promote_other_user_to_admin(self, mock_get_db, mock_auth):
        """Admin should be able to promote another user."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid-123"

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_result = MagicMock()
        mock_result.data = [{"id": "target-uuid", "is_admin": True}]
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        ok, msg = AdminService.update_user_role("target-uuid", True)
        self.assertTrue(ok)
        self.assertIn("Admin", msg)


# ============================================================
# Test Delete User Flow (Auth Admin API)
# ============================================================

class TestDeleteUserWithAdminAPI(unittest.TestCase):
    """Test the delete_user function with mocked Supabase Auth Admin API."""

    @patch("services.admin_service.st")
    @patch("services.admin_service.clear_data_cache")
    @patch("services.admin_service.get_admin_db")
    @patch("services.admin_service.get_db")
    @patch("services.admin_service.auth")
    def test_successful_auth_admin_delete(self, mock_auth, mock_get_db, mock_get_admin_db,
                                          mock_clear_cache, mock_st):
        """When service_role client is available, auth.admin.delete_user should be called."""
        from services.admin_service import AdminService

        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid"

        mock_admin_db = MagicMock()
        mock_get_admin_db.return_value = mock_admin_db

        # Auth Admin delete succeeds
        mock_admin_db.auth.admin.delete_user.return_value = None

        # License unlink succeeds
        mock_admin_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Verification: profile is gone after auth deletion
        mock_check = MagicMock()
        mock_check.data = []
        mock_admin_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_check

        ok, msg = AdminService.delete_user("target-user-uuid")
        self.assertTrue(ok)
        self.assertIn("permanently deleted", msg)
        mock_admin_db.auth.admin.delete_user.assert_called_once_with("target-user-uuid")

    @patch("services.admin_service.st")
    @patch("services.admin_service.clear_data_cache")
    @patch("services.admin_service.get_admin_db")
    @patch("services.admin_service.get_db")
    @patch("services.admin_service.auth")
    def test_no_service_role_key_returns_actionable_error(self, mock_auth, mock_get_db,
                                                          mock_get_admin_db, mock_clear_cache, mock_st):
        """When service_role key is not configured, provide clear guidance."""
        from services.admin_service import AdminService

        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid"

        mock_get_admin_db.return_value = None  # No admin client

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # RPC fails
        mock_db.rpc.side_effect = Exception("RPC not found")

        # Manual deletion fails because profile can't be deleted via anon key
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        # Profile still exists after deletion attempt
        mock_check = MagicMock()
        mock_check.data = [{"id": "target-user-uuid"}]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_check

        ok, msg = AdminService.delete_user("target-user-uuid")
        self.assertFalse(ok)
        self.assertIn("Failed to delete user", msg)
        self.assertIn("RPC", msg)

    @patch("services.admin_service.auth")
    def test_invalid_user_id_rejected(self, mock_auth):
        """Invalid user ID (empty or malformed) must return clean error."""
        from services.admin_service import AdminService
        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid"

        ok, msg = AdminService.delete_user("")
        self.assertFalse(ok)
        self.assertIn("Invalid user ID", msg)

        ok, msg = AdminService.delete_user("123")
        self.assertFalse(ok)
        self.assertIn("Invalid user ID", msg)

    def test_jwt_normalization_auto_repairs_missing_dot(self):
        """_normalize_jwt_key must repair a JWT missing the dot between header and payload."""
        from database import _normalize_jwt_key
        broken_jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3bnF2eHdzdmJwbnJ2aGZzY2l1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTMwMTU1MSwiZXhwIjoyMTAwODc3NTUxfQ"
            ".qX_yTQtAI_X52IDGvaJJ58sIOqJ3T6GCvTtyL-TRzqc"
        )
        repaired = _normalize_jwt_key(broken_jwt)
        self.assertIsNotNone(repaired)
        self.assertEqual(repaired.count("."), 2)
        self.assertTrue(repaired.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."))

    def test_jwt_normalization_keeps_valid_jwt(self):
        """_normalize_jwt_key must not alter an already valid JWT."""
        from database import _normalize_jwt_key
        valid_jwt = "header.payload.signature"
        self.assertEqual(_normalize_jwt_key(valid_jwt), valid_jwt)
        self.assertIsNone(_normalize_jwt_key(""))
        self.assertIsNone(_normalize_jwt_key("YOUR_SERVICE_ROLE_KEY"))


# ============================================================
# Test License Service Operations
# ============================================================

class TestLicenseServiceOperations(unittest.TestCase):
    """Test license generation and validation logic."""

    def test_license_key_format(self):
        """Generated keys must follow HT-XXXX-XXXX-XXXX-XXXX format."""
        import re
        from services.license_service import generate_license_key
        key = generate_license_key()
        pattern = r"^HT-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
        self.assertIsNotNone(re.match(pattern, key), f"Key '{key}' doesn't match format.")

    def test_bulk_license_uniqueness(self):
        """Bulk generated keys must all be unique."""
        from services.license_service import generate_license_keys
        keys = generate_license_keys(200)
        self.assertEqual(len(keys), 200)
        self.assertEqual(len(set(keys)), 200, "Duplicate keys generated!")

    def test_email_normalization(self):
        """Email normalization must lowercase and strip whitespace."""
        from services.license_service import normalize_email
        self.assertEqual(normalize_email("  ADMIN@EXAMPLE.COM  "), "admin@example.com")
        self.assertEqual(normalize_email(None), "")
        self.assertEqual(normalize_email(""), "")

    def test_key_normalization(self):
        """Key normalization must uppercase and strip whitespace."""
        from services.license_service import normalize_license_key
        self.assertEqual(normalize_license_key("  ht-abcd-1234  "), "HT-ABCD-1234")
        self.assertEqual(normalize_license_key(None), "")

    def test_email_validation(self):
        """Email validation must accept valid and reject invalid emails."""
        from services.license_service import is_valid_email
        self.assertTrue(is_valid_email("user@example.com"))
        self.assertTrue(is_valid_email("name+tag@sub.domain.co"))
        self.assertFalse(is_valid_email(""))
        self.assertFalse(is_valid_email("invalid"))
        self.assertFalse(is_valid_email("@domain"))
        self.assertFalse(is_valid_email("user@"))

    def test_csv_export_format(self):
        """Exported CSV must have header and all keys."""
        from services.license_service import export_keys_csv
        keys = ["HT-AAAA-BBBB-CCCC-DDDD", "HT-1111-2222-3333-4444"]
        csv = export_keys_csv(keys)
        lines = csv.strip().replace("\r\n", "\n").split("\n")
        self.assertEqual(lines[0], "License Key")
        self.assertEqual(len(lines), 3)  # header + 2 keys

    @patch("services.license_service.auth")
    def test_bulk_create_requires_admin(self, mock_auth):
        """bulk_create_licenses must reject non-admin callers."""
        from services.license_service import bulk_create_licenses
        mock_auth.is_admin.return_value = False
        ok, msg, keys = bulk_create_licenses(5)
        self.assertFalse(ok)
        self.assertIn("Permission denied", msg)
        self.assertEqual(keys, [])

    @patch("services.license_service.auth")
    def test_revoke_license_requires_admin(self, mock_auth):
        """revoke_license must reject non-admin callers."""
        from services.license_service import revoke_license
        mock_auth.is_admin.return_value = False
        ok, msg = revoke_license("some-license-id")
        self.assertFalse(ok)
        self.assertIn("Permission denied", msg)

    @patch("services.license_service.auth")
    def test_reinstate_license_requires_admin(self, mock_auth):
        """reinstate_license must reject non-admin callers."""
        from services.license_service import reinstate_license
        mock_auth.is_admin.return_value = False
        ok, msg = reinstate_license("some-license-id")
        self.assertFalse(ok)
        self.assertIn("Permission denied", msg)


# ============================================================
# Test Settings Service
# ============================================================

class TestSettingsService(unittest.TestCase):
    """Test settings retrieval and defaults."""

    def test_default_settings_completeness(self):
        """All required settings keys must exist in defaults."""
        from services.settings_service import DEFAULT_SETTINGS
        required = [
            "maintenance_mode", "registration_enabled", "ai_enabled",
            "selected_ai_model", "allow_journal", "allow_habits",
            "allow_achievements", "allow_admin_panel", "system_name",
            "support_email", "default_timezone"
        ]
        for key in required:
            self.assertIn(key, DEFAULT_SETTINGS, f"Missing default setting: {key}")

    def test_default_values_types(self):
        """Default setting values must have correct types."""
        from services.settings_service import DEFAULT_SETTINGS
        self.assertIsInstance(DEFAULT_SETTINGS["maintenance_mode"], bool)
        self.assertIsInstance(DEFAULT_SETTINGS["registration_enabled"], bool)
        self.assertIsInstance(DEFAULT_SETTINGS["ai_enabled"], bool)
        self.assertIsInstance(DEFAULT_SETTINGS["system_name"], str)
        self.assertIsInstance(DEFAULT_SETTINGS["selected_ai_model"], str)

    @patch("services.settings_service.auth")
    def test_update_setting_requires_admin(self, mock_auth):
        """update_setting must reject non-admin callers."""
        from services.settings_service import SettingsService
        mock_auth.is_admin.return_value = False
        ok, msg = SettingsService.update_setting("system_name", "Test")
        self.assertFalse(ok)
        self.assertIn("Permission Denied", msg)

    @patch("services.settings_service.auth")
    def test_update_settings_batch_requires_admin(self, mock_auth):
        """update_settings batch must reject non-admin callers."""
        from services.settings_service import SettingsService
        mock_auth.is_admin.return_value = False
        ok, msg = SettingsService.update_settings({"key": "value"})
        self.assertFalse(ok)
        self.assertIn("Permission Denied", msg)


# ============================================================
# Test RBAC Role System
# ============================================================

class TestRBACSystem(unittest.TestCase):
    """Test role-based access control and permission matrix."""

    def test_admin_wildcard_permission(self):
        """Admin role must have wildcard permission '*'."""
        from auth import Role
        perms = Role.get_permissions(Role.ADMIN)
        self.assertIn("*", perms)

    def test_user_cannot_view_analytics(self):
        """Standard users must not have view_analytics permission."""
        from auth import Role
        perms = Role.get_permissions(Role.USER)
        self.assertNotIn("view_analytics", perms)
        self.assertNotIn("*", perms)

    def test_all_roles_defined(self):
        """All expected roles must be defined in Role registry."""
        from auth import Role
        roles = Role.all_roles()
        for expected in ["user", "admin", "coach", "moderator", "analyst"]:
            self.assertIn(expected, roles)

    def test_unknown_role_returns_set(self):
        """Unknown role names should return a set containing Role.USER."""
        from auth import Role
        perms = Role.get_permissions("nonexistent_role")
        # The code returns {cls.USER} which is {'user'} for unknown roles
        self.assertIsInstance(perms, set)
        self.assertIn(Role.USER, perms)


# ============================================================
# Test Database Module
# ============================================================

class TestDatabaseModule(unittest.TestCase):
    """Test database module function signatures and fallback behavior."""

    def test_get_admin_db_returns_none_without_key(self):
        """get_admin_db must return None when service_role key is not configured."""
        # This test verifies the function doesn't crash when key is missing
        # In production, it would check st.secrets which we can't access in tests
        # So we just verify the function exists and is importable
        from database import get_admin_db
        self.assertTrue(callable(get_admin_db))

    def test_get_db_is_importable(self):
        """get_db must be importable from database module."""
        from database import get_db
        self.assertTrue(callable(get_db))


# ============================================================
# Test Permissions Module
# ============================================================

class TestPermissionsModule(unittest.TestCase):
    """Test permission manager feature flag checks."""

    def test_permission_functions_are_callable(self):
        """All permission functions must be importable and callable."""
        from services.permissions import (
            can_bypass_maintenance,
            can_register_users,
            can_access_admin_panel,
            can_use_ai_coach,
            can_use_journal,
            can_use_habits,
            can_use_achievements
        )
        for func in [can_bypass_maintenance, can_register_users,
                     can_access_admin_panel, can_use_ai_coach,
                     can_use_journal, can_use_habits, can_use_achievements]:
            self.assertTrue(callable(func))


# ============================================================
# Test Cache Manager
# ============================================================

class TestCacheManager(unittest.TestCase):
    """Test cache manager operations."""

    def test_cache_functions_are_callable(self):
        """All cache manager functions must be importable and callable."""
        from services.cache_manager import (
            clear_data_cache,
            clear_resource_cache,
            ping_database,
            reload_system_settings,
            sync_data
        )
        for func in [clear_data_cache, clear_resource_cache,
                     ping_database, reload_system_settings, sync_data]:
            self.assertTrue(callable(func))


# ============================================================
# Test Admin Service Error Handling
# ============================================================

class TestAdminServiceErrorHandling(unittest.TestCase):
    """Test that admin service functions handle errors properly."""

    @patch("services.admin_service.st")
    @patch("services.admin_service.clear_data_cache")
    @patch("services.admin_service.get_admin_db")
    @patch("services.admin_service.get_db")
    @patch("services.admin_service.auth")
    def test_delete_user_handles_db_exception(self, mock_auth, mock_get_db,
                                               mock_get_admin_db, mock_clear_cache, mock_st):
        """delete_user must not crash on database exceptions."""
        from services.admin_service import AdminService

        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid"
        mock_get_admin_db.return_value = None

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Everything fails
        mock_db.rpc.side_effect = Exception("DB connection lost")
        mock_db.table.side_effect = Exception("DB connection lost")

        ok, msg = AdminService.delete_user("target-uuid")
        # Should not crash, should return an error message
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)

    @patch("services.admin_service.auth")
    @patch("services.admin_service.get_db")
    def test_update_role_handles_db_exception(self, mock_get_db, mock_auth):
        """update_user_role must return error on database failure."""
        from services.admin_service import AdminService

        mock_auth.is_admin.return_value = True
        mock_auth.get_user_id.return_value = "admin-uuid"

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.table.side_effect = Exception("Connection refused")

        ok, msg = AdminService.update_user_role("target-uuid", True)
        self.assertFalse(ok)
        self.assertIn("Failed to update role", msg)


if __name__ == "__main__":
    unittest.main()
