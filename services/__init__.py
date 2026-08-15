"""

AI Habit Tracker SaaS - Services Package Initialization

"""

from services.settings_service import (get_setting, get_all_settings, update_setting,
                                      update_settings, reload_settings)
from services.permissions import (can_bypass_maintenance, can_register_users,
                                  can_access_admin_panel, can_use_ai_coach,
                                  can_use_journal, can_use_habits, can_use_achievements)
from services.cache_manager import (clear_data_cache, clear_resource_cache,
                                    ping_database, reload_system_settings, sync_data)
from services.admin_service import update_user_role, delete_user, save_admin_settings
from services.license_service import (activate_license, activate_purchase_key, check_user_license,
                                       check_email_has_active_license, bulk_create_licenses,
                                       export_keys_csv, get_license_counts,
                                       get_licenses_paginated, revoke_license,
                                       reinstate_license, generate_license_keys)
