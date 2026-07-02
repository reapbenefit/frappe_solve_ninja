# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from solve_ninja.api.v1.automated_cohort import (
	_create_monthly_automated_collections_background,
	_monthly_cohort_job_name,
	_send_monthly_cohort_email,
	create_monthly_automated_collections,
	current_cohort_period,
)


class TestAutomatedCohort(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.period = current_cohort_period()
		self.month = self.period["cohort_month"]
		self.year = self.period["cohort_year"]
		self.buckets = ["Dormants"]

	@patch("solve_ninja.api.v1.automated_cohort._check_glific_group_permission")
	@patch("solve_ninja.api.v1.automated_cohort.classify_all_users")
	@patch("solve_ninja.api.v1.automated_cohort.frappe.enqueue")
	@patch("solve_ninja.api.v1.automated_cohort.get_automated_cohort_doc_name", return_value=None)
	@patch("solve_ninja.api.v1.automated_cohort._send_monthly_cohort_email")
	def test_api_returns_queued_without_classification(
		self, mock_send_email, mock_get_doc_name, mock_enqueue, mock_classify, _mock_perm
	):
		result = create_monthly_automated_collections(
			cohort_buckets=self.buckets,
			cohort_month=self.month,
			cohort_year=self.year,
			confirm_overwrite=0,
		)

		self.assertTrue(result["queued"])
		self.assertEqual(result["cohort_month"], self.month)
		self.assertEqual(result["cohort_year"], self.year)
		self.assertEqual(result["buckets"], self.buckets)
		mock_classify.assert_not_called()
		mock_enqueue.assert_called_once()
		enqueue_kwargs = mock_enqueue.call_args.kwargs
		self.assertEqual(enqueue_kwargs["queue"], "long")
		self.assertEqual(enqueue_kwargs["timeout"], 3600)
		self.assertEqual(
			enqueue_kwargs["job_name"],
			_monthly_cohort_job_name(self.month, self.year, self.buckets),
		)
		mock_send_email.assert_called_once()
		self.assertEqual(mock_send_email.call_args.args[1], "Queued")

	@patch("solve_ninja.api.v1.automated_cohort._check_glific_group_permission")
	@patch("solve_ninja.api.v1.automated_cohort.classify_all_users")
	@patch("solve_ninja.api.v1.automated_cohort.frappe.enqueue")
	@patch("solve_ninja.api.v1.automated_cohort.get_automated_cohort_doc_name")
	def test_api_returns_skipped_duplicates_without_enqueue(
		self, mock_get_doc_name, mock_enqueue, mock_classify, _mock_perm
	):
		mock_get_doc_name.return_value = "Dormants - June 2026"

		result = create_monthly_automated_collections(
			cohort_buckets=self.buckets,
			cohort_month=self.month,
			cohort_year=self.year,
			confirm_overwrite=0,
		)

		self.assertFalse(result["queued"])
		self.assertEqual(len(result["skipped_duplicates"]), 1)
		self.assertEqual(result["skipped_duplicates"][0]["existing_doc_name"], "Dormants - June 2026")
		mock_classify.assert_not_called()
		mock_enqueue.assert_not_called()

	@patch("solve_ninja.api.v1.automated_cohort.frappe.sendmail")
	def test_send_monthly_cohort_email_when_enabled(self, mock_sendmail):
		settings = frappe.get_single("Solve Ninja Settings")
		settings.enable_monthly_cohort_notifications = 1
		settings.monthly_cohort_notification_email = "cohort@test.com"
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Solve Ninja Settings")

		thread_id = "monthly-cohort.test@test-site"
		msg_id = _send_monthly_cohort_email(
			"2026-June-Dormants",
			"Queued",
			"<p>body</p>",
			self.month,
			self.year,
			self.buckets,
			thread_message_id=thread_id,
		)

		self.assertEqual(msg_id, thread_id)
		mock_sendmail.assert_called_once()
		kwargs = mock_sendmail.call_args.kwargs
		self.assertEqual(kwargs["recipients"], ["cohort@test.com"])
		self.assertIn(self.month, kwargs["subject"])
		self.assertEqual(kwargs["message_id"], thread_id)
		self.assertNotIn("in_reply_to", kwargs)

	@patch("solve_ninja.api.v1.automated_cohort.frappe.sendmail")
	def test_send_monthly_cohort_email_threads_replies(self, mock_sendmail):
		settings = frappe.get_single("Solve Ninja Settings")
		settings.enable_monthly_cohort_notifications = 1
		settings.monthly_cohort_notification_email = "cohort@test.com"
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Solve Ninja Settings")

		thread_id = "monthly-cohort.test@test-site"
		_send_monthly_cohort_email(
			"2026-June-Dormants",
			"Completed",
			"<p>done</p>",
			self.month,
			self.year,
			self.buckets,
			thread_message_id=thread_id,
			in_reply_to=thread_id,
		)

		kwargs = mock_sendmail.call_args.kwargs
		self.assertEqual(kwargs["message_id"], thread_id)
		self.assertEqual(kwargs["in_reply_to"], thread_id)

	@patch("solve_ninja.api.v1.automated_cohort.frappe.sendmail")
	def test_send_monthly_cohort_email_skipped_when_disabled(self, mock_sendmail):
		settings = frappe.get_single("Solve Ninja Settings")
		settings.enable_monthly_cohort_notifications = 0
		settings.monthly_cohort_notification_email = "cohort@test.com"
		settings.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Solve Ninja Settings")

		_send_monthly_cohort_email(
			"2026-June-Dormants",
			"Queued",
			"<p>body</p>",
			self.month,
			self.year,
			self.buckets,
		)

		mock_sendmail.assert_not_called()

	@patch("solve_ninja.api.v1.automated_cohort._send_monthly_cohort_email")
	@patch("solve_ninja.api.v1.automated_cohort._run_monthly_automated_collections")
	def test_background_worker_sends_completed_email(self, mock_run, mock_send_email):
		mock_run.return_value = {
			"created": [{"bucket": "Dormants"}],
			"updated": [],
			"glific_jobs_queued": 1,
			"total_users_processed": 10,
			"errors": [],
		}
		thread_id = "monthly-cohort.bg@test-site"

		_create_monthly_automated_collections_background(
			buckets=self.buckets,
			month=self.month,
			year=self.year,
			confirm=0,
			user="Administrator",
			job_key="2026-June-Dormants",
			thread_message_id=thread_id,
		)

		mock_send_email.assert_called_once()
		args = mock_send_email.call_args
		self.assertEqual(args.args[1], "Completed")
		self.assertEqual(args.kwargs["thread_message_id"], thread_id)
		self.assertEqual(args.kwargs["in_reply_to"], thread_id)

	@patch("solve_ninja.api.v1.automated_cohort._send_monthly_cohort_email")
	@patch("solve_ninja.api.v1.automated_cohort._run_monthly_automated_collections")
	def test_background_worker_sends_failed_email_and_reraises(self, mock_run, mock_send_email):
		mock_run.side_effect = RuntimeError("classification failed")
		thread_id = "monthly-cohort.fail@test-site"

		with self.assertRaises(RuntimeError):
			_create_monthly_automated_collections_background(
				buckets=self.buckets,
				month=self.month,
				year=self.year,
				confirm=0,
				user="Administrator",
				job_key="2026-June-Dormants",
				thread_message_id=thread_id,
			)

		mock_send_email.assert_called_once()
		args = mock_send_email.call_args
		self.assertEqual(args.args[1], "Failed")
		self.assertEqual(args.kwargs["in_reply_to"], thread_id)

	@patch("solve_ninja.api.v1.automated_cohort._check_glific_group_permission")
	@patch("solve_ninja.api.v1.automated_cohort.frappe.enqueue")
	@patch("solve_ninja.api.v1.automated_cohort.get_automated_cohort_doc_name", return_value=None)
	@patch("solve_ninja.api.v1.automated_cohort._send_monthly_cohort_email")
	def test_enqueue_uses_dedupe_job_name(
		self, _mock_send_email, _mock_get_doc_name, mock_enqueue, _mock_perm
	):
		buckets = ["Dormants", "Potentials"]
		create_monthly_automated_collections(
			cohort_buckets=buckets,
			cohort_month=self.month,
			cohort_year=self.year,
			confirm_overwrite=1,
		)

		job_name = mock_enqueue.call_args.kwargs["job_name"]
		self.assertEqual(job_name, _monthly_cohort_job_name(self.month, self.year, buckets))
		self.assertTrue(job_name.startswith("create_monthly_cohorts_"))
