import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from solve_ninja.api import single_message_action as sma

MODULE = "solve_ninja.api.single_message_action"
ASSESSMENT_ERROR_TITLE = "Single message action: assessment failed"


def make_assessment(is_action, missing_details):
	return sma.Assessment(
		reasoning="test",
		is_action=is_action,
		has_what="what" not in missing_details,
		has_impact="impact" not in missing_details,
		has_how="how" not in missing_details,
		has_with_whom="with_whom" not in missing_details,
		missing_details=missing_details,
	)


def users_with_username(count):
	# Existing users avoid the User after_insert hooks, which call external services.
	return frappe.get_all(
		"User",
		filters=[
			["enabled", "=", 1],
			["username", "is", "set"],
			["name", "not in", ["Administrator", "Guest"]],
		],
		order_by="creation asc",
		limit=count,
		pluck="name",
	)


def insert_submission(user, text, status="Not an Action", creation=None, **fields):
	doc = frappe.get_doc(
		{
			"doctype": "Action Submission",
			"user": user,
			"raw_text": text,
			"hours_value": 1,
			"hours_unit": "hours",
			"status": status,
			"last_completed_step": 0,
			**fields,
		}
	).insert(ignore_permissions=True)
	if creation:
		frappe.db.set_value("Action Submission", doc.name, "creation", creation, update_modified=False)
	return doc.name


class SingleMessageActionTestCase(IntegrationTestCase):
	SAVEPOINT = "single_message_action_test"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.users = users_with_username(2)
		if len(cls.users) < 2:
			raise unittest.SkipTest("Needs two enabled users with a username on this site")

	def setUp(self):
		# IntegrationTestCase only rolls back per class; isolate each test.
		frappe.db.savepoint(self.SAVEPOINT)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=self.SAVEPOINT)


class TestRecordAction(SingleMessageActionTestCase):
	def record(self, text, assessment=None, error=None, user=None, hours_value=1, hours_unit="hours"):
		frappe.set_user(user or self.users[0])
		assess = patch(f"{MODULE}.assess_message", side_effect=error, return_value=assessment)
		enqueue = patch(f"{MODULE}._enqueue_processing")
		with assess as assess_mock, enqueue as enqueue_mock:
			result = sma.record_action(text=text, hours_value=hours_value, hours_unit=hours_unit)
		frappe.set_user("Administrator")
		return result, assess_mock, enqueue_mock

	def submission(self, name):
		return frappe.db.get_value(
			"Action Submission",
			name,
			["status", "action_completeness", "missing_details", "assessment"],
			as_dict=True,
		)

	def test_not_an_action_is_still_recorded_as_incomplete(self):
		result, _, enqueue = self.record(
			"Good experience", make_assessment(False, ["what", "impact", "how", "with_whom"])
		)

		self.assertTrue(result["recorded"])
		self.assertEqual(result["action_completeness"], "Incomplete")
		doc = self.submission(result["submission"])
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.action_completeness, "Incomplete")
		self.assertEqual(frappe.parse_json(doc.missing_details), ["what", "impact", "how", "with_whom"])
		self.assertTrue(doc.assessment)
		enqueue.assert_called_once_with(result["submission"], enqueue_after_commit=True)

	def test_action_missing_only_impact_is_complete(self):
		result, _, enqueue = self.record(
			"Cleaned the drain near my school with friends", make_assessment(True, ["impact"])
		)

		self.assertTrue(result["recorded"])
		doc = self.submission(result["submission"])
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.action_completeness, "Complete")
		enqueue.assert_called_once()

	def test_action_missing_what_is_incomplete(self):
		result, _, enqueue = self.record("Did some community work", make_assessment(True, ["what"]))

		self.assertTrue(result["recorded"])
		self.assertEqual(self.submission(result["submission"]).action_completeness, "Incomplete")
		enqueue.assert_called_once()

	def test_assessment_failure_still_records(self):
		errors_before = frappe.db.count("Error Log", {"method": ASSESSMENT_ERROR_TITLE})

		result, _, enqueue = self.record("Held a session on waste segregation", error=Exception("OpenAI down"))

		self.assertTrue(result["recorded"])
		doc = self.submission(result["submission"])
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.action_completeness, "Incomplete")
		self.assertEqual(frappe.parse_json(doc.missing_details), [])
		self.assertFalse(doc.assessment)
		enqueue.assert_called_once()
		self.assertEqual(frappe.db.count("Error Log", {"method": ASSESSMENT_ERROR_TITLE}), errors_before + 1)

	def test_same_text_twice_within_window_is_one_submission(self):
		first, _, first_enqueue = self.record("Planted 10 trees in my lane", make_assessment(True, []))
		second, second_assess, second_enqueue = self.record(
			"  planted 10   TREES in my lane ", make_assessment(True, [])
		)

		self.assertEqual(first["submission"], second["submission"])
		self.assertTrue(second["recorded"])
		self.assertEqual(second["action_completeness"], first["action_completeness"])
		first_enqueue.assert_called_once()
		second_enqueue.assert_not_called()
		second_assess.assert_not_called()
		self.assertEqual(
			frappe.db.count("Action Submission", {"user": self.users[0], "raw_text": "Planted 10 trees in my lane"}),
			1,
		)

	def test_same_text_from_two_users_is_two_submissions(self):
		first, _, _ = self.record("Painted the bus stop", make_assessment(True, []), user=self.users[0])
		second, _, enqueue = self.record("Painted the bus stop", make_assessment(True, []), user=self.users[1])

		self.assertNotEqual(first["submission"], second["submission"])
		enqueue.assert_called_once()

	def test_same_text_after_window_is_a_new_submission(self):
		first, _, _ = self.record("Fixed the school tap", make_assessment(True, []))
		frappe.db.set_value(
			"Action Submission",
			first["submission"],
			"creation",
			add_to_date(now_datetime(), minutes=-(sma.DUPLICATE_WINDOW_MINUTES + 1)),
			update_modified=False,
		)

		second, _, enqueue = self.record("Fixed the school tap", make_assessment(True, []))

		self.assertNotEqual(first["submission"], second["submission"])
		enqueue.assert_called_once()

	def test_recent_not_an_action_record_is_not_a_duplicate(self):
		old = insert_submission(self.users[0], "Framed the problem using 5W1H", status="Not an Action")

		result, _, enqueue = self.record("Framed the problem using 5W1H", make_assessment(True, []))

		self.assertNotEqual(result["submission"], old)
		enqueue.assert_called_once()

	def test_empty_text_still_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.record("   ", make_assessment(True, []))

	def test_invalid_hours_still_rejected(self):
		for hours_value, hours_unit in ((0, "hours"), (1.5, "minutes"), (sma.MAX_HOURS + 1, "hours"), (1, "days")):
			with self.subTest(hours_value=hours_value, hours_unit=hours_unit):
				with self.assertRaises(frappe.ValidationError):
					self.record(
						"Taught a neighbour to read",
						make_assessment(True, []),
						hours_value=hours_value,
						hours_unit=hours_unit,
					)
