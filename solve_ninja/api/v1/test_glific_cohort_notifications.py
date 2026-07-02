# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from solve_ninja.api.v1.glific_cohort_notifications import (
	format_glific_job_stats,
	glific_job_thread_message_id,
	send_glific_job_email,
)


class TestGlificCohortNotifications(FrappeTestCase):
	def test_thread_message_id_is_stable_per_job_key(self):
		msg_id = glific_job_thread_message_id("sync_Test Group")
		self.assertIn("glific-job.sync_Test Group@", msg_id)

	@patch("solve_ninja.api.v1.glific_cohort_notifications.frappe.sendmail")
	def test_send_glific_job_email_when_enabled(self, mock_sendmail):
		settings = frappe.get_single("Solve Ninja Settings")
		settings.enable_monthly_cohort_notifications = 1
		settings.monthly_cohort_notification_email = "cohort@test.com"
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Solve Ninja Settings")

		thread_id = "glific-job.sync@test-site"
		result = send_glific_job_email(
			"member_sync",
			"Started",
			"Test Group",
			"admin@test.com",
			"sync_Test Group",
			thread_message_id=thread_id,
		)

		self.assertEqual(result, thread_id)
		mock_sendmail.assert_called_once()
		kwargs = mock_sendmail.call_args.kwargs
		self.assertEqual(kwargs["message_id"], thread_id)
		self.assertIn("Test Group", kwargs["subject"])

	@patch("solve_ninja.api.v1.glific_cohort_notifications.frappe.sendmail")
	def test_send_glific_job_email_threads_replies(self, mock_sendmail):
		settings = frappe.get_single("Solve Ninja Settings")
		settings.enable_monthly_cohort_notifications = 1
		settings.monthly_cohort_notification_email = "cohort@test.com"
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Solve Ninja Settings")

		thread_id = "glific-job.delete@test-site"
		send_glific_job_email(
			"delete",
			"Completed",
			"Test Group",
			"admin@test.com",
			"delete_Test Group",
			thread_message_id=thread_id,
			in_reply_to=thread_id,
		)

		kwargs = mock_sendmail.call_args.kwargs
		self.assertEqual(kwargs["in_reply_to"], thread_id)

	@patch("solve_ninja.api.v1.glific_cohort_notifications.get_glific_group_member_stats")
	def test_format_glific_job_stats_includes_counts(self, mock_stats):
		mock_stats.return_value = {
			"total": 100,
			"synced": 80,
			"failed": 10,
			"pending": 10,
		}
		with patch.object(
			frappe.db,
			"get_value",
			return_value={
				"group_name": "Test Group",
				"glific_group_id": "123",
				"cohort_type": "Monthly Cohort",
			},
		):
			html = format_glific_job_stats("Test Group", "admin@test.com")

		self.assertIn("100", html)
		self.assertIn("80", html)
		self.assertIn("admin@test.com", html)
