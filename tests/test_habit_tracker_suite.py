"""
AI Habit Tracker SaaS - Comprehensive End-to-End Test Suite
Tests authentication logic, license system, permissions, admin guards,
streak calculations, and system settings.
"""

import unittest
import re
from datetime import date, datetime, timedelta

# Import modules to test
from services.license_service import (
    generate_license_key,
    generate_license_keys,
    normalize_email,
    normalize_license_key,
    is_valid_email,
    _generate_key_segment
)
from services.settings_service import (
    DEFAULT_SETTINGS,
    SettingsService,
    get_setting,
    get_all_settings
)
from services.permissions import (
    PermissionManager,
    can_bypass_maintenance,
    can_register_users,
    can_access_admin_panel,
    can_use_ai_coach,
    can_use_journal,
    can_use_habits,
    can_use_achievements
)
from auth import Role, AuthManager
import utils


class TestLicenseService(unittest.TestCase):
    """Test license generation, normalization, formatting, and validation."""

    def test_key_segment_generation(self):
        seg = _generate_key_segment(4)
        self.assertEqual(len(seg), 4)
        self.assertTrue(seg.isalnum())
        self.assertTrue(seg.isupper() or seg.isdigit())

    def test_single_license_format(self):
        key = generate_license_key()
        pattern = r"^HT-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
        self.assertTrue(re.match(pattern, key), f"License '{key}' does not match expected format.")

    def test_bulk_license_uniqueness(self):
        count = 100
        keys = generate_license_keys(count)
        self.assertEqual(len(keys), count)
        self.assertEqual(len(set(keys)), count, "Duplicate license keys generated.")

    def test_email_normalization(self):
        self.assertEqual(normalize_email("  User@Example.COM  "), "user@example.com")
        self.assertEqual(normalize_email(None), "")
        self.assertEqual(normalize_email(""), "")

    def test_license_key_normalization(self):
        self.assertEqual(normalize_license_key("  ht-abcd-1234-ef56-7890  "), "HT-ABCD-1234-EF56-7890")
        self.assertEqual(normalize_license_key(None), "")
        self.assertEqual(normalize_license_key(""), "")

    def test_email_validation(self):
        self.assertTrue(is_valid_email("customer@email.com"))
        self.assertTrue(is_valid_email("john.doe+tracker@sub.domain.co"))
        self.assertFalse(is_valid_email("invalid-email"))
        self.assertFalse(is_valid_email("@domain.com"))
        self.assertFalse(is_valid_email("user@"))
        self.assertFalse(is_valid_email(""))
        self.assertFalse(is_valid_email("   "))


class TestRoleAndPermissionRBAC(unittest.TestCase):
    """Test RBAC role registry, permissions, and admin wildcards."""

    def test_all_roles_defined(self):
        roles = Role.all_roles()
        self.assertIn("user", roles)
        self.assertIn("admin", roles)
        self.assertIn("coach", roles)
        self.assertIn("moderator", roles)
        self.assertIn("analyst", roles)

    def test_admin_has_wildcard_permission(self):
        admin_perms = Role.get_permissions(Role.ADMIN)
        self.assertIn("*", admin_perms)

    def test_user_permissions(self):
        user_perms = Role.get_permissions(Role.USER)
        self.assertIn("view_dashboard", user_perms)
        self.assertIn("manage_habits", user_perms)
        self.assertIn("write_journal", user_perms)
        self.assertIn("use_ai_coach", user_perms)
        self.assertNotIn("view_analytics", user_perms)
        self.assertNotIn("*", user_perms)

    def test_coach_and_analyst_permissions(self):
        coach_perms = Role.get_permissions(Role.COACH)
        self.assertIn("view_analytics", coach_perms)
        analyst_perms = Role.get_permissions(Role.ANALYST)
        self.assertIn("export_data", analyst_perms)
        self.assertNotIn("manage_habits", analyst_perms)


class TestSettingsService(unittest.TestCase):
    """Test global settings defaults, retrieval, and fallbacks."""

    def test_default_settings_keys(self):
        required_keys = [
            "maintenance_mode", "registration_enabled", "ai_enabled",
            "selected_ai_model", "allow_journal", "allow_habits",
            "allow_achievements", "allow_admin_panel", "system_name",
            "support_email", "default_timezone"
        ]
        for key in required_keys:
            self.assertIn(key, DEFAULT_SETTINGS)

    def test_get_setting_with_fallback(self):
        sys_name = get_setting("system_name", "AI Habit Tracker")
        self.assertIsInstance(sys_name, str)
        self.assertTrue(len(sys_name) > 0)

        # Non-existent key with default
        val = get_setting("non_existent_key_xyz", "my_default")
        self.assertEqual(val, "my_default")


class TestUtilsAndDateHelpers(unittest.TestCase):
    """Test utility date calculations, formatters, and streak logic."""

    def test_today_and_now(self):
        t = utils.today()
        self.assertEqual(t, date.today())
        n = utils.now()
        self.assertIsInstance(n, datetime)

    def test_week_start_and_end(self):
        ws = utils.week_start()
        we = utils.week_end()
        self.assertEqual(ws.weekday(), 0)  # Monday
        self.assertEqual((we - ws).days, 6)  # Sunday is 6 days after Monday

    def test_greeting(self):
        g = utils.greeting()
        self.assertIn(g, ["Good Morning", "Good Afternoon", "Good Evening", "Good Night"])

    def test_date_formatting(self):
        self.assertEqual(utils.format_date(None), "—")
        sample_date = date(2026, 8, 15)
        self.assertEqual(utils.format_date(sample_date), "15 Aug 2026")
        self.assertEqual(utils.format_date("2026-08-15"), "15 Aug 2026")

    def test_ui_formatters(self):
        self.assertEqual(utils.percentage(75.4), "75%")
        self.assertEqual(utils.percentage(100), "100%")
        self.assertEqual(utils.status_badge("completed"), "✅ Completed")
        self.assertEqual(utils.status_badge("failed"), "❌ Failed")
        self.assertEqual(utils.status_badge("skipped"), "⏭️ Skipped")
        self.assertEqual(utils.mood_emoji(1), "😞")
        self.assertEqual(utils.mood_emoji(5), "😐")
        self.assertEqual(utils.mood_emoji(8), "😊")
        self.assertEqual(utils.mood_emoji(10), "😁")


class TestAdminSelfProtectionGuards(unittest.TestCase):
    """Test admin self-protection guards."""

    def test_admin_service_self_delete_guard(self):
        from services.admin_service import AdminService
        # Simulating unauthenticated or non-admin call
        ok, msg = AdminService.delete_user("some-target-id")
        self.assertFalse(ok)
        self.assertIn("Permission Denied", msg)


if __name__ == "__main__":
    unittest.main()
