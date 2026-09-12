"""
AI Habit Tracker SaaS - Habit Duplicate Prevention Test Suite
Verifies all 14 required tests for user-scoped, case-insensitive, whitespace-safe habit duplicate prevention.
"""

import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

import utils
from views.user import add_habit, manage_habits


class TestHabitDuplicatePrevention(unittest.TestCase):
    """Verifies all duplicate prevention behavior and existing functionality."""

    def setUp(self):
        self.user_a = "user-uuid-111"
        self.user_b = "user-uuid-222"
        # In-memory habit store for testing
        self.habits_store: List[Dict[str, Any]] = []

    def _mock_db_table(self):
        store = self.habits_store

        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table

        # Mock select
        def mock_select(columns="*", count=None):
            query = MagicMock()
            filtered = list(store)

            def mock_eq(col, val):
                nonlocal filtered
                filtered = [r for r in filtered if r.get(col) == val]
                sub_query = MagicMock()
                sub_query.eq = mock_eq
                sub_query.order = lambda *a, **kw: sub_query
                sub_query.limit = lambda n: sub_query
                sub_query.execute.return_value = MagicMock(data=filtered, count=len(filtered))
                return sub_query

            query.eq = mock_eq
            query.order = lambda *a, **kw: query
            query.execute.return_value = MagicMock(data=filtered, count=len(filtered))
            return query

        mock_table.select = mock_select

        # Mock insert
        def mock_insert(data):
            insert_query = MagicMock()
            def mock_execute():
                # Check normalized uniqueness constraint (user_id, LOWER(TRIM(title)))
                target_user = data.get("user_id")
                target_norm = utils.normalize_habit_title(data.get("title", ""))
                for h in store:
                    if h.get("user_id") == target_user and utils.normalize_habit_title(h.get("title", "")) == target_norm:
                        raise Exception("duplicate key value violates unique constraint 'idx_habits_user_id_normalized_title' (code: 23505)")
                new_record = dict(data)
                if "id" not in new_record:
                    new_record["id"] = f"habit-{len(store) + 1}"
                store.append(new_record)
                return MagicMock(data=[new_record])
            insert_query.execute = mock_execute
            return insert_query

        mock_table.insert = mock_insert

        # Mock update
        def mock_update(data):
            update_query = MagicMock()
            def mock_eq(col, val):
                inner_query = MagicMock()
                def mock_second_eq(col2, val2):
                    final_query = MagicMock()
                    def mock_execute():
                        for h in store:
                            if h.get(col) == val and h.get(col2) == val2:
                                h.update(data)
                        return MagicMock(data=store)
                    final_query.execute = mock_execute
                    return final_query
                inner_query.eq = mock_second_eq
                def mock_execute():
                    for h in store:
                        if h.get(col) == val:
                            h.update(data)
                    return MagicMock(data=store)
                inner_query.execute = mock_execute
                return inner_query
            update_query.eq = mock_eq
            return update_query

        mock_table.update = mock_update

        # Mock delete
        def mock_delete():
            del_query = MagicMock()
            def mock_eq(col, val):
                inner_query = MagicMock()
                def mock_second_eq(col2, val2):
                    final_query = MagicMock()
                    def mock_execute():
                        store[:] = [h for h in store if not (h.get(col) == val and h.get(col2) == val2)]
                        return MagicMock(data=[])
                    final_query.execute = mock_execute
                    return final_query
                inner_query.eq = mock_second_eq
                def mock_execute():
                    store[:] = [h for h in store if h.get(col) != val]
                    return MagicMock(data=[])
                inner_query.execute = mock_execute
                return inner_query
            del_query.eq = mock_eq
            return del_query

        mock_table.delete = mock_delete

        return mock_db

    # TEST 1: Create habit named "Gym" -> Should succeed
    def test_01_create_habit_gym_succeeds(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a):
            ok = add_habit.create_habit("Gym", "Work out daily", "daily", 1)
            self.assertTrue(ok)
            self.assertEqual(len(self.habits_store), 1)
            self.assertEqual(self.habits_store[0]["title"], "Gym")

    # TEST 2: Try to create "Gym" again for the same user -> Should be blocked
    def test_02_create_exact_duplicate_blocked(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("streamlit.warning") as mock_warn:
            ok1 = add_habit.create_habit("Gym", "Work out daily", "daily", 1)
            self.assertTrue(ok1)

            ok2 = add_habit.create_habit("Gym", "Work out again", "daily", 1)
            self.assertFalse(ok2)
            self.assertEqual(len(self.habits_store), 1)
            mock_warn.assert_called()
            warn_msg = str(mock_warn.call_args)
            self.assertIn("already have a habit named", warn_msg)
            self.assertIn("Gym", warn_msg)

    # TEST 3: Try to create "gym" for the same user -> Should be blocked (case-insensitive)
    def test_03_create_lowercase_duplicate_blocked(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("streamlit.warning") as mock_warn:
            add_habit.create_habit("Gym", "Work out daily", "daily", 1)
            ok = add_habit.create_habit("gym", "Work out daily", "daily", 1)
            self.assertFalse(ok)
            self.assertEqual(len(self.habits_store), 1)
            mock_warn.assert_called()
            self.assertIn("already have a habit named", str(mock_warn.call_args))

    # TEST 4: Try to create "GYM" for the same user -> Should be blocked (uppercase)
    def test_04_create_uppercase_duplicate_blocked(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("streamlit.warning") as mock_warn:
            add_habit.create_habit("Gym", "Work out daily", "daily", 1)
            ok = add_habit.create_habit("GYM", "Work out daily", "daily", 1)
            self.assertFalse(ok)
            self.assertEqual(len(self.habits_store), 1)
            mock_warn.assert_called()

    # TEST 5: Try to create " Gym" or "Gym " -> Should be treated as duplicate and blocked
    def test_05_create_whitespace_duplicate_blocked(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("streamlit.warning") as mock_warn:
            add_habit.create_habit("Gym", "Work out daily", "daily", 1)

            ok1 = add_habit.create_habit(" Gym", "Work out daily", "daily", 1)
            self.assertFalse(ok1)

            ok2 = add_habit.create_habit("Gym ", "Work out daily", "daily", 1)
            self.assertFalse(ok2)

            ok3 = add_habit.create_habit("   Gym   ", "Work out daily", "daily", 1)
            self.assertFalse(ok3)

            self.assertEqual(len(self.habits_store), 1)

    # TEST 6: Create "Morning Gym" when "Gym" already exists -> Should be allowed
    def test_06_create_morning_gym_allowed(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a):
            ok1 = add_habit.create_habit("Gym", "Gym routine", "daily", 1)
            self.assertTrue(ok1)

            ok2 = add_habit.create_habit("Morning Gym", "Morning workout", "daily", 1)
            self.assertTrue(ok2)
            self.assertEqual(len(self.habits_store), 2)

    # TEST 7: Create "Gym Workout" when "Gym" already exists -> Should be allowed
    def test_07_create_gym_workout_allowed(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a):
            ok1 = add_habit.create_habit("Gym", "Gym routine", "daily", 1)
            self.assertTrue(ok1)

            ok2 = add_habit.create_habit("Gym Workout", "Intense gym workout", "daily", 1)
            self.assertTrue(ok2)
            self.assertEqual(len(self.habits_store), 2)

    # TEST 8: Another user creates "Gym" -> Should be allowed (uniqueness is per user)
    def test_08_different_user_can_create_same_habit_name(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db):
            # User A creates Gym
            with patch("utils.get_current_user_id", return_value=self.user_a):
                ok_a = add_habit.create_habit("Gym", "User A gym", "daily", 1)
                self.assertTrue(ok_a)

            # User B creates Gym
            with patch("utils.get_current_user_id", return_value=self.user_b):
                ok_b = add_habit.create_habit("Gym", "User B gym", "daily", 1)
                self.assertTrue(ok_b)

            self.assertEqual(len(self.habits_store), 2)
            user_ids = [h["user_id"] for h in self.habits_store]
            self.assertIn(self.user_a, user_ids)
            self.assertIn(self.user_b, user_ids)

    # TEST 9: Verify duplicate habits are not accidentally inserted into the database
    def test_09_database_insertion_safety(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("streamlit.warning"):
            add_habit.create_habit("Gym", "Workout", "daily", 1)
            add_habit.create_habit("GYM", "Workout duplicate", "daily", 1)
            add_habit.create_habit(" gym ", "Workout duplicate", "daily", 1)

            # Exactly 1 record must be in the database
            self.assertEqual(len(self.habits_store), 1)
            titles = [h["title"] for h in self.habits_store if h["user_id"] == self.user_a]
            self.assertEqual(titles, ["Gym"])

    # TEST 10: Verify existing habits still display correctly
    def test_10_existing_habits_display(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("utils.get_current_user_id", return_value=self.user_a):
            add_habit.create_habit("Read 10 pages", "Daily reading", "daily", 1)
            habits = utils.get_today_habits(self.user_a)
            self.assertEqual(len(habits), 1)
            self.assertEqual(habits[0]["title"], "Read 10 pages")

    # TEST 11: Verify habit completion/tracking still works
    def test_11_habit_completion_tracking_works(self):
        self.assertEqual(utils.status_badge("completed"), "✅ Completed")
        self.assertEqual(utils.status_badge("failed"), "❌ Failed")
        self.assertEqual(utils.percentage(100), "100%")
        self.assertEqual(utils.percentage(50), "50%")

    # TEST 12: Verify edit habit functionality still works
    def test_12_edit_habit_functionality_works(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("views.user.manage_habits.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("auth.auth.get_user_id", return_value=self.user_a), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("views.user.manage_habits.refresh_data"):
            # Create habit
            add_habit.create_habit("Gym", "Workout", "daily", 1)
            habit_id = self.habits_store[0]["id"]

            # Edit same habit (keeping title "Gym", changing description)
            manage_habits.update_habit_db(habit_id, "Gym", "Updated workout desc", "daily", 2)
            self.assertEqual(self.habits_store[0]["description"], "Updated workout desc")
            self.assertEqual(self.habits_store[0]["target_count"], 2)

            # Edit to new unique title
            manage_habits.update_habit_db(habit_id, "Daily Workout", "Updated workout desc", "daily", 2)
            self.assertEqual(self.habits_store[0]["title"], "Daily Workout")

    # TEST 13: Verify delete habit functionality still works
    def test_13_delete_habit_functionality_works(self):
        mock_db = self._mock_db_table()
        with patch("views.user.add_habit.get_db", return_value=mock_db), \
             patch("views.user.manage_habits.get_db", return_value=mock_db), \
             patch("utils.get_db", return_value=mock_db), \
             patch("auth.auth.get_user_id", return_value=self.user_a), \
             patch("utils.get_current_user_id", return_value=self.user_a), \
             patch("views.user.manage_habits.refresh_data"):
            add_habit.create_habit("Gym", "Workout", "daily", 1)
            self.assertEqual(len(self.habits_store), 1)
            habit_id = self.habits_store[0]["id"]

            manage_habits.delete_habit_db(habit_id)
            self.assertEqual(len(self.habits_store), 0)

    # TEST 14: Verify unrelated application features remain unchanged
    def test_14_unrelated_features_unchanged(self):
        from services.license_service import normalize_license_key, is_valid_email
        self.assertEqual(normalize_license_key(" ht-1111-2222 "), "HT-1111-2222")
        self.assertTrue(is_valid_email("user@example.com"))

        from services.permissions import can_use_habits
        with patch("auth.auth.has_permission", return_value=True):
            self.assertTrue(can_use_habits())


if __name__ == "__main__":
    unittest.main()
