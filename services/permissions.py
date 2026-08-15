"""

AI Habit Tracker SaaS - Role & Permission Management
Structures role-based authorization and system feature access control.

"""

from auth import auth, Role
from services.settings_service import get_setting


class PermissionManager:
    """Manages granular user access control and dynamic feature flags."""

    @staticmethod
    def get_user_role() -> str:
        """Return current user's role string."""
        return auth.get_user_role()

    @staticmethod
    def can_bypass_maintenance() -> bool:
        """Determine if current user can bypass Maintenance Mode (Admins only)."""
        return auth.is_admin()

    @staticmethod
    def can_register_users() -> bool:
        """Check if public user registration is currently enabled by Admin."""
        return bool(get_setting("registration_enabled", True))

    @staticmethod
    def can_access_admin_panel() -> bool:
        """Check if current user can access the Admin Panel."""
        if not get_setting("allow_admin_panel", True):
            return False
        return auth.is_admin()

    @staticmethod
    def can_use_ai_coach() -> bool:
        """Check if AI Coach is globally enabled and user has permissions."""
        if not get_setting("ai_enabled", True):
            return False
        return auth.has_permission("use_ai_coach")

    @staticmethod
    def can_use_journal() -> bool:
        """Check if Journal module is globally enabled and user has permissions."""
        if not get_setting("allow_journal", True):
            return False
        return auth.has_permission("write_journal")

    @staticmethod
    def can_use_habits() -> bool:
        """Check if Habits module is globally enabled."""
        if not get_setting("allow_habits", True):
            return False
        return auth.has_permission("manage_habits")

    @staticmethod
    def can_use_achievements() -> bool:
        """Check if Achievements module is globally enabled."""
        return bool(get_setting("allow_achievements", True))


can_bypass_maintenance = PermissionManager.can_bypass_maintenance
can_register_users = PermissionManager.can_register_users
can_access_admin_panel = PermissionManager.can_access_admin_panel
can_use_ai_coach = PermissionManager.can_use_ai_coach
can_use_journal = PermissionManager.can_use_journal
can_use_habits = PermissionManager.can_use_habits
can_use_achievements = PermissionManager.can_use_achievements
