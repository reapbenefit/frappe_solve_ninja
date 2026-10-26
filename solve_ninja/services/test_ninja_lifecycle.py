# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, get_datetime, get_first_day, now_datetime, today

from solve_ninja.services import ninja_lifecycle as lifecycle
from solve_ninja.services import ninja_mis as mis
from solve_ninja.services.ninja_lifecycle import (
	ACTIVE,
	ALUMNI,
	DORMANT,
	INACTIVE,
	decide_initial,
	decide_level_decay,
	decide_on_activity,
	decide_on_inactivity,
)


class TestLifecycleRules(IntegrationTestCase):
	def test_active_level_follows_12_month_hours(self):
		self.assertEqual(decide_on_activity(0, ACTIVE, 5, True, True), (1, ACTIVE))
		self.assertEqual(decide_on_activity(1, ACTIVE, 29.9, True, True), (1, ACTIVE))
		self.assertEqual(decide_on_activity(1, ACTIVE, 30, True, True), (2, ACTIVE))

	def test_inactive_reactivates_only_with_recent_action(self):
		self.assertEqual(decide_on_activity(1, INACTIVE, 40, True, True), (2, ACTIVE))
		self.assertEqual(decide_on_activity(1, INACTIVE, 40, False, True), (1, INACTIVE))

	def test_dormant_returns_at_level_1(self):
		self.assertEqual(decide_on_activity(2, DORMANT, 50, True, True), (1, ACTIVE))
		self.assertEqual(decide_on_activity(2, DORMANT, 50, False, True), (2, DORMANT))

	def test_level_3_and_alumni_are_never_changed_automatically(self):
		self.assertEqual(decide_on_activity(3, ACTIVE, 1, True, True), (3, ACTIVE))
		self.assertEqual(decide_on_activity(1, ALUMNI, 40, True, True), (2, ALUMNI))
		as_of = get_datetime("2026-10-31 23:59:59")
		long_ago = get_datetime("2024-01-01")
		self.assertEqual(decide_on_inactivity(3, ACTIVE, long_ago, as_of), (3, INACTIVE))
		self.assertEqual(decide_on_inactivity(1, ALUMNI, long_ago, as_of), (1, ALUMNI))
		self.assertEqual(decide_level_decay(3, 0), 3)

	def test_inactivity_boundaries(self):
		as_of = get_datetime("2026-10-31 23:59:59")
		self.assertEqual(decide_on_inactivity(1, ACTIVE, add_months(as_of, -6), as_of), (1, INACTIVE))
		self.assertEqual(
			decide_on_inactivity(1, ACTIVE, add_months(as_of, -6) + timedelta(seconds=1), as_of), (1, ACTIVE)
		)
		self.assertEqual(decide_on_inactivity(1, INACTIVE, add_months(as_of, -12), as_of), (1, DORMANT))

	def test_level_decay(self):
		self.assertEqual(decide_level_decay(2, 29.5), 1)
		self.assertEqual(decide_level_decay(2, 30), 2)
		self.assertEqual(decide_level_decay(1, 0), 1)

	def test_initial_state(self):
		as_of = get_datetime("2026-10-26 12:00:00")
		self.assertEqual(decide_initial(None, "2026-09-01", 0, as_of), (0, ACTIVE))
		self.assertEqual(decide_initial(None, "2024-01-01", 0, as_of), (0, DORMANT))
		self.assertEqual(decide_initial("2026-08-01", "2024-01-01", 31, as_of), (2, ACTIVE))
		self.assertEqual(decide_initial("2026-01-01", "2024-01-01", 2, as_of), (1, INACTIVE))
		self.assertEqual(decide_initial("2025-01-01", "2024-01-01", 0, as_of), (1, DORMANT))

	def test_initial_setup_assigns_level_3_from_50_hours(self):
		as_of = get_datetime("2026-10-26 12:00:00")
		self.assertEqual(decide_initial("2026-10-01", "2024-01-01", 49.9, as_of), (2, ACTIVE))
		self.assertEqual(decide_initial("2026-10-01", "2024-01-01", 50, as_of), (3, ACTIVE))
		# Active within 12 months but not within 6: Level 3, Inactive (never Dormant)
		self.assertEqual(decide_initial("2026-03-01", "2024-01-01", 80, as_of), (3, INACTIVE))

	def test_level_3_is_not_reached_automatically_after_setup(self):
		self.assertEqual(decide_on_activity(2, ACTIVE, 60, True, True), (2, ACTIVE))
		self.assertEqual(decide_on_activity(1, INACTIVE, 60, True, True), (2, ACTIVE))
		self.assertEqual(decide_level_decay(3, 10), 3)


class LifecycleTestCase(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_ninja(self, level="0", status=ACTIVE, created=None, logged_on=None):
		name = f"lifecycle-{frappe.generate_hash(length=8)}@solveninja.org"
		doc = frappe.get_doc(
			{"doctype": "Ninja Profile", "user": name, "ninja_level": level, "ninja_status": status}
		)
		doc.name = name
		doc.creation = doc.modified = get_datetime(created) if created else now_datetime()
		doc.db_insert()
		if logged_on:
			lifecycle.insert_log_rows(
				[
					lifecycle.make_log_row(
						name, None, None, level, status, lifecycle.REASON_INITIAL_SETUP, logged_on
					)
				]
			)
		return name

	def add_event(self, user, hours, when, created=None):
		doc = frappe.get_doc(
			{
				"doctype": "Events",
				"title": "Lifecycle test",
				"user": user,
				"hours_invested": hours,
				"date_of_action": get_datetime(when),
			}
		)
		doc.name = frappe.generate_hash(length=10)
		doc.creation = doc.modified = get_datetime(created) if created else now_datetime()
		doc.db_insert()
		return doc.name

	def profile(self, name):
		return frappe.db.get_value(
			"Ninja Profile", name, ["ninja_level", "ninja_status", "hours_last_12_months"], as_dict=True
		)

	def calculated_on(self, name):
		value = frappe.db.get_value("Ninja Profile", name, "hours_calculated_on")
		return get_datetime(value) if value else None

	def logs(self, name):
		return frappe.get_all(
			"Ninja Lifecycle Log",
			filters={"ninja": name},
			fields=["reason", "from_level", "to_level", "from_status", "to_status", "changed_on"],
			order_by="changed_on asc, creation asc",
		)


class TestActionRules(LifecycleTestCase):
	def test_active_ninja_promoted_to_level_2(self):
		ninja = self.make_ninja("1", ACTIVE)
		self.add_event(ninja, 20, add_months(now_datetime(), -8))
		self.add_event(ninja, 10, add_days(now_datetime(), -2))

		result = lifecycle.evaluate_ninja(ninja)

		self.assertTrue(result["changed"])
		self.assertEqual(self.profile(ninja), {"ninja_level": "2", "ninja_status": ACTIVE, "hours_last_12_months": 30})
		(log,) = self.logs(ninja)
		self.assertEqual((log.reason, log.from_level, log.to_level), ("Action", "1", "2"))
		self.assertLessEqual(abs((now_datetime() - self.calculated_on(ninja)).total_seconds()), 60)

	def test_hours_calculated_on_set_even_without_a_change(self):
		ninja = self.make_ninja("1", ACTIVE)
		self.add_event(ninja, 2, now_datetime())

		result = lifecycle.evaluate_ninja(ninja)

		self.assertFalse(result["changed"])
		self.assertIsNotNone(self.calculated_on(ninja))

	def test_inactive_ninja_reactivated(self):
		ninja = self.make_ninja("1", INACTIVE)
		self.add_event(ninja, 5, add_days(now_datetime(), -1))

		lifecycle.evaluate_ninja(ninja)

		self.assertEqual(self.profile(ninja).ninja_status, ACTIVE)
		self.assertEqual(self.profile(ninja).ninja_level, "1")

	def test_dormant_returns_at_level_1_until_next_action(self):
		ninja = self.make_ninja("2", DORMANT)
		self.add_event(ninja, 35, add_days(now_datetime(), -1), created=add_days(now_datetime(), -1))

		lifecycle.evaluate_ninja(ninja)
		self.assertEqual(self.profile(ninja).ninja_level, "1")
		self.assertEqual(self.profile(ninja).ninja_status, ACTIVE)

		# Re-evaluating the same action (e.g. daily re-save) must not jump to Level 2
		lifecycle.evaluate_ninja(ninja)
		self.assertEqual(self.profile(ninja).ninja_level, "1")

		# A genuinely new action follows the Active rules
		self.add_event(ninja, 1, now_datetime(), created=now_datetime() + timedelta(seconds=5))
		lifecycle.evaluate_ninja(ninja)
		self.assertEqual(self.profile(ninja).ninja_level, "2")

	def test_backdated_event_does_not_reactivate(self):
		ninja = self.make_ninja("1", DORMANT)
		self.add_event(ninja, 40, add_months(now_datetime(), -8))

		result = lifecycle.evaluate_ninja(ninja)

		self.assertFalse(result["changed"])
		self.assertEqual(self.profile(ninja).ninja_status, DORMANT)

	def test_level_3_and_alumni_kept(self):
		level_3 = self.make_ninja("3", ACTIVE)
		self.add_event(level_3, 1, now_datetime())
		alumni = self.make_ninja("1", ALUMNI)
		self.add_event(alumni, 31, now_datetime())

		lifecycle.evaluate_ninja(level_3)
		lifecycle.evaluate_ninja(alumni)

		self.assertEqual(self.profile(level_3).ninja_level, "3")
		self.assertEqual((self.profile(alumni).ninja_level, self.profile(alumni).ninja_status), ("2", ALUMNI))

	def test_recalculation_applies_inactivity(self):
		ninja = self.make_ninja("2", ACTIVE, created=add_months(now_datetime(), -24))
		self.add_event(ninja, 40, add_months(now_datetime(), -7))

		frappe.set_user("Administrator")
		result = lifecycle.recalculate_ninja(ninja)

		self.assertEqual((result["level"], result["status"]), (2, INACTIVE))
		self.assertEqual(self.logs(ninja)[-1].reason, "Manual Recalculation")

	def test_manual_edit_is_logged(self):
		ninja = self.make_ninja("1", ACTIVE)
		doc = frappe.get_doc("Ninja Profile", ninja)
		doc.ninja_level = "3"
		doc.flags.ignore_links = True
		doc.save(ignore_permissions=True)

		(log,) = self.logs(ninja)
		self.assertEqual((log.reason, log.from_level, log.to_level), ("Manual", "1", "3"))

	def test_concurrent_update_is_retried_in_a_fresh_job(self):
		ninja = self.make_ninja("1", INACTIVE)
		self.add_event(ninja, 5, now_datetime())

		class SerializationFailure(Exception):
			pgcode = lifecycle.SERIALIZATION_FAILURE

		with (
			patch.object(lifecycle, "evaluate_ninja", side_effect=SerializationFailure()),
			patch("frappe.enqueue") as mock_enqueue,
		):
			lifecycle.evaluate_ninja_after_events_change(ninja)

		mock_enqueue.assert_called_once()
		self.assertEqual(mock_enqueue.call_args.kwargs["user"], ninja)
		# Transaction is still usable after rolling back to the savepoint
		self.assertEqual(self.profile(ninja).ninja_status, INACTIVE)

	def test_history_never_blocks_deleting_events_or_profiles(self):
		ninja = self.make_ninja("1", INACTIVE)
		event = self.add_event(ninja, 5, now_datetime())
		lifecycle.evaluate_ninja_after_events_change(ninja)
		self.assertEqual(self.logs(ninja)[-1].reason, "Action")
		mis.build_snapshot(get_first_day(today()), users=[ninja], commit=False)

		frappe.delete_doc("Events", event, force=True, ignore_permissions=True)
		frappe.delete_doc("Ninja Profile", ninja, force=True, ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Ninja Lifecycle Log", {"ninja": ninja}))
		self.assertFalse(frappe.db.exists("Ninja Monthly Snapshot", {"ninja": ninja}))

	def test_buttons_require_system_manager(self):
		ninja = self.make_ninja()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			lifecycle.recalculate_ninja(ninja)
		with self.assertRaises(frappe.PermissionError):
			mis.trigger_monthly_mis(steps="snapshot")


class TestMonthlyJob(LifecycleTestCase):
	def setUp(self):
		self.month_start = get_first_day(add_months(today(), -1))
		self.start = get_datetime(f"{self.month_start} 00:00:00")
		self.month_end = mis.month_end_of(self.month_start)
		self.before = self.start - timedelta(days=1)
		self.long_ago = add_months(self.month_end, -30)

	def test_month_end_rules_and_snapshot(self):
		e = self.month_end
		went_inactive = self.make_ninja("1", ACTIVE, created=self.long_ago, logged_on=self.before)
		self.add_event(went_inactive, 3, add_months(e, -7))

		went_dormant = self.make_ninja("2", ACTIVE, created=self.long_ago, logged_on=self.before)
		self.add_event(went_dormant, 40, add_months(e, -13))

		level_3 = self.make_ninja("3", ACTIVE, created=self.long_ago, logged_on=self.before)
		self.add_event(level_3, 1, add_months(e, -13))

		alumni = self.make_ninja("1", ALUMNI, created=self.long_ago, logged_on=self.before)

		never_acted = self.make_ninja("0", ACTIVE, created=add_months(e, -7), logged_on=self.before)

		decayed = self.make_ninja("2", ACTIVE, created=self.long_ago, logged_on=self.before)
		self.add_event(decayed, 5, self.start + timedelta(days=3))
		self.add_event(decayed, 4, self.start + timedelta(days=10))

		acted_since = self.make_ninja("1", ACTIVE, created=self.long_ago, logged_on=self.before)
		self.add_event(acted_since, 1, add_months(e, -8))
		self.add_event(acted_since, 1, now_datetime())

		dormant_all_month = self.make_ninja("1", DORMANT, created=self.long_ago, logged_on=self.before)

		joined = self.make_ninja("0", ACTIVE, created=self.start + timedelta(days=5))

		users = [
			went_inactive,
			went_dormant,
			level_3,
			alumni,
			never_acted,
			decayed,
			acted_since,
			dormant_all_month,
			joined,
		]
		mis.run_for_month(self.month_start, steps=mis.STEPS_ALL, users=users, commit=False)

		self.assertEqual(self.profile(went_inactive).ninja_status, INACTIVE)
		self.assertEqual(
			(self.profile(went_dormant).ninja_status, self.profile(went_dormant).ninja_level), (DORMANT, "1")
		)
		self.assertCountEqual(
			[log.reason for log in self.logs(went_dormant) if log.reason != "Initial Setup"],
			["Dormant 12 Months", "Hours Below 30"],
		)
		self.assertEqual((self.profile(level_3).ninja_status, self.profile(level_3).ninja_level), (INACTIVE, "3"))
		self.assertEqual(self.profile(alumni).ninja_status, ALUMNI)
		self.assertEqual(self.profile(never_acted).ninja_status, INACTIVE)
		self.assertEqual((self.profile(decayed).ninja_status, self.profile(decayed).ninja_level), (ACTIVE, "1"))
		self.assertEqual(self.profile(acted_since).ninja_status, ACTIVE)
		self.assertEqual(get_datetime(self.logs(went_inactive)[-1].changed_on), e)
		self.assertEqual(self.calculated_on(went_inactive), e)
		self.assertEqual(self.calculated_on(alumni), e)
		self.assertIsNone(self.calculated_on(acted_since))

		snapshots = {
			row.ninja: row
			for row in frappe.get_all(
				"Ninja Monthly Snapshot",
				filters={"month": self.month_start, "ninja": ["in", users]},
				fields=["*"],
			)
		}
		self.assertNotIn(dormant_all_month, snapshots)
		self.assertIn(went_dormant, snapshots)

		row = snapshots[went_inactive]
		self.assertEqual((row.status_start, row.status_end, row.status_changed), (ACTIVE, INACTIVE, 1))

		row = snapshots[decayed]
		self.assertEqual((row.level_start, row.level_end, row.level_changed), ("2", "1", 1))
		self.assertEqual((row.actions_count, row.hours_invested), (2, 9))
		self.assertEqual(row.quarter, f"{self.month_start.year} Q{(self.month_start.month - 1) // 3 + 1}")

		row = snapshots[joined]
		self.assertEqual((row.new_this_month, row.level_start, row.level_end, row.status_end), (1, None, "0", ACTIVE))

		# Rebuilding the month replaces rows instead of duplicating them
		count = mis.build_snapshot(self.month_start, users=users, commit=False)
		self.assertEqual(count, len(snapshots))
		self.assertEqual(
			frappe.db.count("Ninja Monthly Snapshot", {"month": self.month_start, "ninja": ["in", users]}),
			len(snapshots),
		)

	def test_month_end_rereads_actions_under_lock(self):
		ninja = self.make_ninja("1", ACTIVE, created=self.long_ago, logged_on=self.before)
		self.add_event(ninja, 1, add_months(self.month_end, -8))
		stale_activity = mis.load_activity(self.month_end, users=[ninja])
		# Action lands after the job loaded its aggregates
		self.add_event(ninja, 1, now_datetime())

		mis._apply_month_end_chunk([ninja], stale_activity, self.month_end)

		self.assertEqual(self.profile(ninja).ninja_status, ACTIVE)

	def test_initialise_lifecycle(self):
		now = now_datetime()
		busy = self.make_ninja(created=add_months(now, -24))
		self.add_event(busy, 40, add_months(now, -3))
		quiet = self.make_ninja(created=add_months(now, -24))
		lapsed = self.make_ninja(created=add_months(now, -24))
		self.add_event(lapsed, 2, add_months(now, -9))
		veteran = self.make_ninja(created=add_months(now, -24))
		self.add_event(veteran, 30, add_months(now, -10))
		self.add_event(veteran, 25, add_months(now, -7))

		count = mis.initialise_lifecycle(users=[busy, quiet, lapsed, veteran], commit=False)

		self.assertEqual(count, 4)
		self.assertIsNotNone(self.calculated_on(quiet))
		self.assertEqual((self.profile(veteran).ninja_level, self.profile(veteran).ninja_status), ("3", INACTIVE))
		self.add_event(veteran, 1, now)
		lifecycle.evaluate_ninja(veteran)
		self.assertEqual((self.profile(veteran).ninja_level, self.profile(veteran).ninja_status), ("3", ACTIVE))
		self.assertEqual((self.profile(busy).ninja_level, self.profile(busy).ninja_status), ("2", ACTIVE))
		self.assertEqual((self.profile(quiet).ninja_level, self.profile(quiet).ninja_status), ("0", DORMANT))
		self.assertEqual((self.profile(lapsed).ninja_level, self.profile(lapsed).ninja_status), ("1", INACTIVE))
		self.assertEqual(self.logs(busy)[0].reason, "Initial Setup")
		self.assertEqual(mis.initialise_lifecycle(users=[busy, quiet, lapsed, veteran], commit=False), 0)

	def test_run_validation(self):
		next_month = get_first_day(add_months(today(), 1))
		with self.assertRaises(frappe.ValidationError):
			mis.validate_run(next_month, mis.STEPS_SNAPSHOT)
		with self.assertRaises(frappe.ValidationError):
			mis.validate_run(get_first_day(add_months(today(), -3)), mis.STEPS_ALL)
		with self.assertRaises(frappe.ValidationError):
			mis.validate_run(self.month_start, "everything")
