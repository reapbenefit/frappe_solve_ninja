from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from solve_ninja.api.test.test_single_message_action import users_with_username
from solve_ninja.doc_events import energy_point_log as epl


class TestBadgeHoursWait(IntegrationTestCase):
	SAVEPOINT = "badge_hours_wait_test"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.users = users_with_username(1)
		if not cls.users:
			raise Exception("Needs an enabled user with a username on this site")

	def setUp(self):
		frappe.db.savepoint(self.SAVEPOINT)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=self.SAVEPOINT)

	def _insert_event(self, hours_invested=None, source="ConversationalBot"):
		event = frappe.get_doc(
			{
				"doctype": "Events",
				"title": "Badge hours wait test",
				"description": "test",
				"user": self.users[0],
				"hours_invested": hours_invested,
				"source": source,
			}
		)
		event.flags.ignore_permissions = True
		event.flags.ignore_mandatory = True
		event.flags.ignore_links = True
		event.insert()
		return event

	def _insert_submission(self, event_id=None, hours_value=4, step=2, status="Processing"):
		doc = frappe.get_doc(
			{
				"doctype": "Action Submission",
				"user": self.users[0],
				"raw_text": f"Badge wait {frappe.generate_hash(length=6)} cleaned a drain",
				"hours_value": hours_value,
				"hours_unit": "hours",
				"status": status,
				"last_completed_step": step,
				"event_id": event_id,
			}
		).insert(ignore_permissions=True)
		return doc

	def _patch_refresh(self):
		# Avoid frappe.db.rollback() wiping the test savepoint.
		return patch.object(epl, "_refresh_event", side_effect=lambda name: frappe.get_doc("Events", name))

	def test_await_skips_when_hours_already_set(self):
		event = self._insert_event(hours_invested=3)
		with patch.object(epl, "sleep") as sleep_mock:
			result = epl._await_hours_if_needed(event)
		sleep_mock.assert_not_called()
		self.assertEqual(float(result.hours_invested), 3.0)

	def test_await_skips_when_no_action_submission(self):
		event = self._insert_event(hours_invested=0)
		with patch.object(epl, "sleep") as sleep_mock:
			result = epl._await_hours_if_needed(event)
		sleep_mock.assert_not_called()
		self.assertEqual(float(result.hours_invested or 0), 0.0)

	def test_await_polls_until_hours_arrive(self):
		event = self._insert_event(hours_invested=0)
		self._insert_submission(event_id=event.name, hours_value=4, step=2)

		polls = {"n": 0}

		def fake_sleep(_seconds):
			polls["n"] += 1
			if polls["n"] >= 2:
				frappe.db.set_value("Events", event.name, "hours_invested", 4)

		with self._patch_refresh(), patch.object(epl, "sleep", side_effect=fake_sleep), patch.object(
			epl, "_log_badge_ir"
		):
			result = epl._await_hours_if_needed(event)

		self.assertGreaterEqual(polls["n"], 2)
		self.assertEqual(float(result.hours_invested), 4.0)

	def test_await_keeps_waiting_after_hours_step_until_hours_land(self):
		"""Step 4 alone must not end the wait — that caused the duplicate 0-hour HSM."""
		event = self._insert_event(hours_invested=0)
		submission = self._insert_submission(event_id=event.name, hours_value=4, step=2)

		polls = {"n": 0}

		def fake_sleep(_seconds):
			polls["n"] += 1
			if polls["n"] == 1:
				frappe.db.set_value("Action Submission", submission.name, "last_completed_step", 4)
			if polls["n"] == 3:
				frappe.db.set_value("Events", event.name, "hours_invested", 5)

		with self._patch_refresh(), patch.object(epl, "sleep", side_effect=fake_sleep), patch.object(
			epl, "_log_badge_ir"
		):
			result = epl._await_hours_if_needed(event)

		self.assertEqual(polls["n"], 3)
		self.assertEqual(float(result.hours_invested), 5.0)

	def test_enqueue_badge_skips_when_hours_zero(self):
		event = self._insert_event(hours_invested=0)
		with patch.object(frappe, "enqueue") as enqueue_mock:
			self.assertFalse(epl.enqueue_badge_notification(event.name, enqueue_after_commit=False))
		enqueue_mock.assert_not_called()

	def test_enqueue_badge_runs_when_hours_positive(self):
		event = self._insert_event(hours_invested=2)
		with patch.object(epl, "_try_acquire_badge_notify_lock", return_value=True), patch.object(
			epl, "_badge_already_sent", return_value=False
		), patch.object(frappe, "enqueue") as enqueue_mock:
			self.assertTrue(epl.enqueue_badge_notification(event.name, enqueue_after_commit=False))
		enqueue_mock.assert_called_once()
		kwargs = enqueue_mock.call_args.kwargs
		self.assertEqual(kwargs.get("job_id"), f"badge_hsm::{event.name}")
		self.assertTrue(kwargs.get("deduplicate"))

	def test_enqueue_badge_skips_when_lock_held(self):
		event = self._insert_event(hours_invested=2)
		with patch.object(epl, "_try_acquire_badge_notify_lock", return_value=False), patch.object(
			epl, "_badge_already_sent", return_value=False
		), patch.object(frappe, "enqueue") as enqueue_mock:
			self.assertFalse(epl.enqueue_badge_notification(event.name, enqueue_after_commit=False))
		enqueue_mock.assert_not_called()

	def test_after_insert_skips_when_hours_zero(self):
		event = self._insert_event(hours_invested=0)
		with patch.object(epl, "_try_acquire_badge_notify_lock") as lock_mock, patch.object(
			frappe, "enqueue"
		) as enqueue_mock:
			epl.send_badge_notification_after_insert(event)
		lock_mock.assert_not_called()
		enqueue_mock.assert_not_called()

	def test_on_update_enqueues_when_hours_become_positive(self):
		event = self._insert_event(hours_invested=0)
		frappe.db.set_value("Events", event.name, "hours_invested", 2)
		event.hours_invested = 2
		# Simulate has_value_changed for hours_invested
		with patch.object(event, "has_value_changed", return_value=True), patch.object(
			epl, "_try_acquire_badge_notify_lock", return_value=True
		) as lock_mock, patch.object(frappe, "enqueue") as enqueue_mock, patch.object(
			epl, "_badge_already_sent", return_value=False
		):
			epl.send_badge_notification_on_update(event)

		lock_mock.assert_called_once_with(event.name)
		enqueue_mock.assert_called_once()
		self.assertEqual(enqueue_mock.call_args.kwargs.get("job_id"), f"badge_hsm::{event.name}")

	def test_on_update_skips_when_hours_still_zero(self):
		event = self._insert_event(hours_invested=0)
		with patch.object(event, "has_value_changed", return_value=True), patch.object(
			frappe, "enqueue"
		) as enqueue_mock:
			epl.send_badge_notification_on_update(event)
		enqueue_mock.assert_not_called()

	def test_pending_submission_found_before_event_id_saved(self):
		event = self._insert_event(hours_invested=0)
		self._insert_submission(event_id=None, hours_value=2, step=1, status="Processing")

		pending = epl._pending_action_submission_for_hours(event)
		self.assertIsNotNone(pending)
		self.assertEqual(float(pending.hours_value), 2.0)
