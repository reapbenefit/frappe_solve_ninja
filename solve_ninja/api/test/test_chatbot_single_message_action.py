import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils.file_manager import save_file

from solve_ninja.api import chatbot_single_message_action as chatbot_sma
from solve_ninja.api import single_message_action as sma
from solve_ninja.api.test.test_single_message_action import (
	SingleMessageActionTestCase,
	make_assessment,
)

MODULE = "solve_ninja.api.chatbot_single_message_action"
SMA_MODULE = "solve_ninja.api.single_message_action"


def save_test_photo(fname="chatbot-sma-photo.bin"):
	# Non-image extension skips EXIF stripping in File.before_insert.
	return save_file(fname=fname, content=b"chatbot-sma-test-bytes", dt=None, dn=None, is_private=0)


class TestChatbotRecordAction(SingleMessageActionTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.mobile = "919876543210"
		# Pin a known mobile on the first fixture user for find_user_by_mobile.
		frappe.db.set_value("User", cls.users[0], "mobile_no", cls.mobile)
		cls.username = frappe.db.get_value("User", cls.users[0], "username")

	def record(
		self,
		*,
		mobile=None,
		text="Cleaned the drain near my school",
		hours_value=1,
		hours_unit="hours",
		photo_url=None,
		contact_id=None,
		flow_id=None,
	):
		assess = patch(f"{SMA_MODULE}.assess_message")
		enqueue = patch(f"{SMA_MODULE}._enqueue_assess_and_process")
		with assess as assess_mock, enqueue as enqueue_mock:
			result = chatbot_sma.record_action(
				mobile=mobile if mobile is not None else self.mobile,
				text=text,
				hours_value=hours_value,
				hours_unit=hours_unit,
				photo_url=photo_url,
				contact_id=contact_id,
				flow_id=flow_id,
			)
		return result, assess_mock, enqueue_mock

	def test_unknown_mobile_asks_to_register(self):
		result, assess, enqueue = self.record(mobile="911111111111")

		self.assertFalse(result["recorded"])
		self.assertTrue(result["needs_registration"])
		self.assertIn("sign up", result["message"].lower())
		assess.assert_not_called()
		enqueue.assert_not_called()

	def test_disabled_user_is_rejected(self):
		frappe.db.set_value("User", self.users[0], "enabled", 0)
		try:
			result, assess, enqueue = self.record()
		finally:
			frappe.db.set_value("User", self.users[0], "enabled", 1)

		self.assertFalse(result["recorded"])
		self.assertFalse(result["needs_registration"])
		self.assertIn("disabled", result["message"].lower())
		assess.assert_not_called()
		enqueue.assert_not_called()

	def test_existing_user_fast_acks_with_profile_link(self):
		result, assess, enqueue = self.record()

		self.assertTrue(result["recorded"])
		self.assertTrue(result["accepted"])
		self.assertIn("/user-profile/", result["profile_url"])
		self.assertIn(self.username, result["profile_url"])
		self.assertIn("saved!", result["message"].lower())
		self.assertIn("about a minute", result["message"].lower())
		self.assertNotIn(result["profile_url"], result["message"])
		# OpenAI is deferred — webhook must stay fast.
		assess.assert_not_called()

		doc = frappe.db.get_value(
			"Action Submission",
			result["submission"],
			["user", "raw_text", "hours_value", "hours_unit", "status", "photo_url", "action_completeness"],
			as_dict=True,
		)
		self.assertEqual(doc.user, self.users[0])
		self.assertEqual(doc.raw_text, "Cleaned the drain near my school")
		self.assertEqual(float(doc.hours_value), 1.0)
		self.assertEqual(doc.hours_unit, "hours")
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.action_completeness, "Incomplete")
		self.assertFalse(doc.photo_url)
		enqueue.assert_called_once_with(result["submission"], enqueue_after_commit=True)

	def test_user_msg_alias_is_accepted(self):
		enqueue = patch(f"{SMA_MODULE}._enqueue_assess_and_process")
		with patch(f"{SMA_MODULE}.assess_message") as assess, enqueue as enqueue_mock:
			result = chatbot_sma.record_action(
				mobile=self.mobile,
				user_msg="Planted 5 trees in my lane",
				hours_value=2,
				hours_unit="hours",
			)

		self.assertTrue(result["accepted"])
		assess.assert_not_called()
		self.assertEqual(
			frappe.db.get_value("Action Submission", result["submission"], "raw_text"),
			"Planted 5 trees in my lane",
		)
		enqueue_mock.assert_called_once()

	def test_existing_file_path_is_stored_on_submission(self):
		file_doc = save_test_photo("chatbot-sma-photo.bin")
		result, _, _ = self.record(
			photo_url=file_doc.file_url,
			text="Reported a broken streetlight near the park",
		)

		self.assertTrue(result["accepted"])
		self.assertEqual(
			frappe.db.get_value("Action Submission", result["submission"], "photo_url"),
			file_doc.file_url,
		)

	def test_remote_photo_url_is_deferred_not_downloaded_in_request(self):
		download = patch(f"{MODULE}.EventsManager._save_file_from_url")
		with download as download_mock:
			result, assess, enqueue = self.record(
				text="Held a waste segregation session for 20 students",
				photo_url="https://media.example.com/wa/photo.jpg",
			)

		download_mock.assert_not_called()
		assess.assert_not_called()
		enqueue.assert_called_once()
		self.assertEqual(
			frappe.db.get_value("Action Submission", result["submission"], "photo_url"),
			"https://media.example.com/wa/photo.jpg",
		)

	def test_assess_and_process_downloads_photo_then_assesses(self):
		submission = frappe.get_doc(
			{
				"doctype": "Action Submission",
				"user": self.users[0],
				"raw_text": f"Chatbot-bg-assess {frappe.generate_hash(length=6)} cleaned a drain with friends",
				"hours_value": 1,
				"hours_unit": "hours",
				"photo_url": "https://media.example.com/wa/photo.jpg",
				"status": "Pending",
				"last_completed_step": 0,
				"missing_details": "[]",
				"action_completeness": "Incomplete",
			}
		).insert(ignore_permissions=True)

		fake_file = MagicMock()
		fake_file.file_url = "/files/whatsapp-media.jpg"
		# Avoid frappe.db.commit inside _save (would drop the test savepoint).
		saved = {}

		def fake_save(doc, **fields):
			saved.update(fields)
			for key, value in fields.items():
				setattr(doc, key, value)

		download_svc = patch(
			"solve_ninja.services.events_manager.EventsManager._save_file_from_url",
			return_value=fake_file,
		)
		assess = patch(
			f"{SMA_MODULE}.assess_message",
			return_value=make_assessment(True, ["impact"]),
		)
		process = patch(f"{SMA_MODULE}.process_submission")
		save = patch(f"{SMA_MODULE}._save", side_effect=fake_save)

		with download_svc as download_mock, assess as assess_mock, process as process_mock, save:
			sma.assess_and_process_submission(submission.name)

		download_mock.assert_called_once_with("https://media.example.com/wa/photo.jpg", None)
		assess_mock.assert_called_once()
		process_mock.assert_called_once_with(submission.name)
		self.assertEqual(saved.get("photo_url"), "/files/whatsapp-media.jpg")
		self.assertEqual(saved.get("action_completeness"), "Complete")

	def test_missing_mobile_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			chatbot_sma.record_action(mobile="", text="Cleaned a drain", hours_value=1)

	def test_glific_ids_are_stored_on_submission(self):
		result, _, _ = self.record(contact_id="90123", flow_id="456")

		self.assertTrue(result["accepted"])
		doc = frappe.db.get_value(
			"Action Submission",
			result["submission"],
			["glific_contact_id", "glific_flow_id"],
			as_dict=True,
		)
		self.assertEqual(doc.glific_contact_id, "90123")
		self.assertEqual(doc.glific_flow_id, "456")

	def test_process_submission_resumes_glific_on_done(self):
		# Start at step 5 so process_submission only finishes step 6 (no CMP calls).
		submission = frappe.get_doc(
			{
				"doctype": "Action Submission",
				"user": self.users[0],
				"raw_text": f"Glific-resume {frappe.generate_hash(length=6)} cleaned a drain near school",
				"hours_value": 2,
				"hours_unit": "hours",
				"status": "Pending",
				"last_completed_step": 5,
				"event_id": frappe.generate_hash(length=12),
				"action_title": "Drain Cleanup Drive",
				"skills": json.dumps([{"label": "Applied Empathy", "response": "listened"}]),
				"missing_details": "[]",
				"action_completeness": "Complete",
				"glific_contact_id": "90123",
				"glific_flow_id": "456",
			}
		).insert(ignore_permissions=True)

		def fake_save(doc, **fields):
			for key, value in fields.items():
				setattr(doc, key, value)
			# Persist without commit so the test savepoint still rolls back.
			frappe.db.set_value("Action Submission", doc.name, fields, update_modified=False)

		with (
			patch(f"{SMA_MODULE}._save", side_effect=fake_save),
			patch(f"{SMA_MODULE}.resume_glific_for_submission") as resume_mock,
		):
			sma.process_submission(submission.name)

		resume_mock.assert_called_once_with(submission.name)
		self.assertEqual(frappe.db.get_value("Action Submission", submission.name, "status"), "Done")

	def test_sma_event_skips_badge_enqueue_without_glific_ids(self):
		"""Web Quick Add (no Glific IDs) must skip Momentum HSM like chatbot SMA."""
		from solve_ninja.doc_events import energy_point_log as epl

		event = frappe.get_doc(
			{
				"doctype": "Events",
				"title": "Skip HSM",
				"description": "x",
				"user": self.users[0],
				"hours_invested": 2,
				"source": "ConversationalBot",
			}
		)
		event.flags.ignore_permissions = True
		event.flags.ignore_mandatory = True
		event.flags.ignore_links = True
		event.insert()

		frappe.get_doc(
			{
				"doctype": "Action Submission",
				"user": self.users[0],
				"raw_text": f"Skip-hsm {frappe.generate_hash(length=6)} cleaned a drain",
				"hours_value": 1,
				"hours_unit": "hours",
				"status": "Processing",
				"last_completed_step": 4,
				"event_id": event.name,
				"missing_details": "[]",
				"action_completeness": "Complete",
			}
		).insert(ignore_permissions=True)

		self.assertTrue(sma.is_single_message_action_event(event_name=event.name))
		with patch.object(epl, "_badge_already_sent", return_value=False):
			self.assertFalse(epl.enqueue_badge_notification(event.name, enqueue_after_commit=False))

	def test_resume_payload_includes_web_cta_fields(self):
		submission = frappe.get_doc(
			{
				"doctype": "Action Submission",
				"user": self.users[0],
				"raw_text": f"Payload {frappe.generate_hash(length=6)} cleaned a drain",
				"hours_value": 90,
				"hours_unit": "minutes",
				"status": "Done",
				"last_completed_step": 6,
				"event_id": "evt-payload",
				"action_title": "Lane Cleanup",
				"skills": json.dumps(
					[
						{"label": "Communication", "response": "Clear updates"},
						{"label": "Applied Empathy", "response": "Listened well"},
					]
				),
				"missing_details": "[]",
				"action_completeness": "Complete",
				"glific_contact_id": "90123",
				"glific_flow_id": "456",
			}
		).insert(ignore_permissions=True)

		payload = sma._glific_resume_payload(submission)
		self.assertEqual(payload["status"], "Done")
		self.assertEqual(payload["action_title"], "Lane Cleanup")
		self.assertEqual(payload["hours"], 1.5)
		self.assertIn("Communication", payload["skills"])
		self.assertIn("/user-profile/", payload["profile_url"])
		self.assertTrue(payload["events_url"])
		self.assertIn("logged", payload["message"].lower())
		self.assertIn("What this built", payload["message"])
		self.assertIn("Communication — Clear updates", payload["message"])
		self.assertIn("Applied Empathy — Listened well", payload["message"])
		self.assertIn("See it anytime:", payload["message"])
		self.assertEqual(
			payload["skills_detail"],
			[
				{"label": "Communication", "response": "Clear updates"},
				{"label": "Applied Empathy", "response": "Listened well"},
			],
		)

		settings = MagicMock()
		doc = frappe.get_doc("Action Submission", submission.name)

		def _get_doc(doctype, name=None):
			if doctype == "Action Submission":
				return doc
			if doctype == "Glific Settings":
				return settings
			raise AssertionError(doctype)

		with patch(f"{SMA_MODULE}.frappe.get_doc", side_effect=_get_doc):
			ok = sma.resume_glific_for_submission(submission.name)

		self.assertTrue(ok)
		settings.resume_glific_flow.assert_called_once()
		kwargs = settings.resume_glific_flow.call_args.kwargs
		self.assertEqual(kwargs["flow_id"], "456")
		self.assertEqual(kwargs["contact_id"], "90123")
		self.assertEqual(kwargs["result"]["action_title"], "Lane Cleanup")

	def test_process_submission_still_attaches_photo(self):
		"""Chatbot photo_url follows the same Events.attachment1 path as web."""
		file_doc = save_test_photo("chatbot-sma-attach.bin")
		event = frappe.get_doc(
			{
				"doctype": "Events",
				"title": "Chatbot SMA attach test",
				"description": "Photo attach path",
				"user": self.users[0],
			}
		)
		event.flags.ignore_permissions = True
		event.flags.ignore_mandatory = True
		event.insert()

		sma._attach_photo(event.name, file_doc.file_url)

		self.assertEqual(frappe.db.get_value("Events", event.name, "attachment1"), file_doc.file_url)
		attached = frappe.db.get_value(
			"File",
			{"file_url": file_doc.file_url},
			["attached_to_doctype", "attached_to_name", "attached_to_field"],
			as_dict=True,
		)
		self.assertEqual(attached.attached_to_doctype, "Events")
		self.assertEqual(attached.attached_to_name, event.name)
		self.assertEqual(attached.attached_to_field, "attachment1")
