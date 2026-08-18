# Copyright (c) 2025, ReapBenefit and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

from solve_ninja.api.v1.solve_event import get_event_checkin_window, get_event_checkin_window_status


class TestEventCheckinWindow(FrappeTestCase):
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
