# Copyright (c) 2025, ReapBenefit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime

from solve_ninja.api.v1.solve_event import (
	find_or_create_registration,
	get_event_checkin_window,
	get_event_checkin_window_status,
)

REGISTRATION_HSM_METHOD = (
	"solve_ninja.solve_ninja.doctype.solve_event_registration.solve_event_registration.send_event_registration_hsm"
)


class TestEventCheckinWindow(IntegrationTestCase):
	def test_same_day_opens_one_hour_before_start(self):
		start = "2026-08-13 18:00:00"
		end = "2026-08-13 19:00:00"
		window_open, window_close = get_event_checkin_window(start, end)
		self.assertEqual(window_open, get_datetime("2026-08-13 17:00:00"))
		self.assertEqual(window_close, get_datetime("2026-08-13 23:59:59"))

	def test_same_day_allows_before_scheduled_end_rest_of_day(self):
		start = "2026-08-13 18:00:00"
		end = "2026-08-13 19:00:00"
		self.assertIsNone(
			get_event_checkin_window_status(get_datetime("2026-08-13 17:30:00"), start, end)
		)
		self.assertIsNone(
			get_event_checkin_window_status(get_datetime("2026-08-13 19:30:00"), start, end)
		)
		self.assertIsNone(
			get_event_checkin_window_status(get_datetime("2026-08-13 23:00:00"), start, end)
		)

	def test_same_day_rejects_too_early_and_next_day(self):
		start = "2026-08-13 18:00:00"
		end = "2026-08-13 19:00:00"
		self.assertEqual(
			get_event_checkin_window_status(get_datetime("2026-08-13 16:59:59"), start, end),
			"not_started",
		)
		self.assertEqual(
			get_event_checkin_window_status(get_datetime("2026-08-14 00:00:00"), start, end),
			"ended",
		)

	def test_multiday_closes_end_of_last_calendar_day(self):
		start = "2026-08-13 22:00:00"
		end = "2026-08-14 02:00:00"
		window_open, window_close = get_event_checkin_window(start, end)
		self.assertEqual(window_open, get_datetime("2026-08-13 21:00:00"))
		self.assertEqual(window_close, get_datetime("2026-08-14 23:59:59"))

	def test_multiday_allows_middle_and_late_last_day(self):
		start = "2026-08-13 10:00:00"
		end = "2026-08-15 18:00:00"
		self.assertIsNone(
			get_event_checkin_window_status(get_datetime("2026-08-14 08:00:00"), start, end)
		)
		self.assertIsNone(
			get_event_checkin_window_status(get_datetime("2026-08-15 22:00:00"), start, end)
		)
		self.assertEqual(
			get_event_checkin_window_status(get_datetime("2026-08-16 00:00:00"), start, end),
			"ended",
		)


class TestEventCheckinRegistrationHsm(IntegrationTestCase):
	def setUp(self):
		self.user = f"checkin-hsm-{frappe.generate_hash(length=8)}@solveninja.org"
		self.solve_event = f"CHECKIN-HSM-TEST-{frappe.generate_hash(length=8)}"

	def tearDown(self):
		frappe.db.rollback()

	def _queued_hsm_calls(self, mock_enqueue):
		return [c for c in mock_enqueue.call_args_list if c.args and c.args[0] == REGISTRATION_HSM_METHOD]

	@patch("frappe.enqueue")
	def test_checkin_registration_skips_whatsapp_confirmation(self, mock_enqueue):
		registration = find_or_create_registration(self.user, self.solve_event)

		self.assertTrue(registration)
		self.assertEqual(
			frappe.db.get_value("Solve Event Registration", registration, ["user", "solve_event", "source"]),
			(self.user, self.solve_event, "snbot"),
		)
		self.assertEqual(self._queued_hsm_calls(mock_enqueue), [])

	@patch("frappe.enqueue")
	def test_checkin_returns_existing_registration(self, mock_enqueue):
		first = find_or_create_registration(self.user, self.solve_event)
		second = find_or_create_registration(self.user, self.solve_event)

		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count("Solve Event Registration", {"user": self.user, "solve_event": self.solve_event}),
			1,
		)
		self.assertEqual(self._queued_hsm_calls(mock_enqueue), [])

	@patch("frappe.enqueue")
	def test_regular_registration_still_sends_whatsapp_confirmation(self, mock_enqueue):
		frappe.get_doc(
			{
				"doctype": "Solve Event Registration",
				"user": self.user,
				"solve_event": self.solve_event,
				"source": "Web Form",
			}
		).insert(ignore_permissions=True, ignore_links=True)

		self.assertEqual(len(self._queued_hsm_calls(mock_enqueue)), 1)
