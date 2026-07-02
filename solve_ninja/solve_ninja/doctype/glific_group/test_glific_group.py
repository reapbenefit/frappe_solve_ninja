# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from solve_ninja.api.v1.automated_cohort import _member_rows_from_users
from solve_ninja.models.result import Result
from solve_ninja.solve_ninja.doctype.glific_group.glific_group import (
	ADD_CONTACTS_CHUNK,
	DELETE_CONTACTS_BATCH_LIMIT,
	SYNC_ENQUEUE_THRESHOLD,
	SYNC_MEMBER_BATCH_LIMIT,
	_bulk_mark_members_synced,
	_chunked_add_contacts_to_group,
	_chunked_remove_contacts_from_group,
	_delete_glific_group_background,
	_fetch_pending_members,
	_parse_glific_contact_id,
	_prefetch_wa_id_map,
	_resolve_contact_id_for_member,
	_should_enqueue_sync,
	_sync_glific_members_batch_background,
	_sync_member_batch,
	delete_glific_group_manage,
	sync_members_to_glific,
)


class TestGlificGroup(FrappeTestCase):
	def test_member_rows_from_users_sets_glific_contact_id_from_wa_id(self):
		rows = _member_rows_from_users(
			[
				{
					"user": "user1@test.com",
					"mobile_no": "919876543210",
					"full_name": "Alice",
					"wa_id": "12345",
				},
				{
					"user": "user2@test.com",
					"mobile_no": "919876543211",
					"full_name": "Bob",
					"wa_id": None,
				},
			]
		)
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[0]["glific_contact_id"], "12345")
		self.assertIsNone(rows[1]["glific_contact_id"])

	def test_parse_glific_contact_id(self):
		self.assertEqual(_parse_glific_contact_id("42"), "42")
		self.assertEqual(_parse_glific_contact_id(99), "99")
		self.assertIsNone(_parse_glific_contact_id(""))
		self.assertIsNone(_parse_glific_contact_id("not-a-number"))

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_all")
	def test_prefetch_wa_id_map(self, mock_get_all):
		mock_get_all.return_value = [
			{"user": "a@test.com", "wa_id": "100"},
			{"user": "b@test.com", "wa_id": "200"},
			{"user": "c@test.com", "wa_id": ""},
		]
		result = _prefetch_wa_id_map(["a@test.com", "b@test.com", "c@test.com"])
		self.assertEqual(result, {"a@test.com": "100", "b@test.com": "200"})
		mock_get_all.assert_called_once()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.get_contact_id_by_phone")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._wa_id_for_user")
	def test_resolve_contact_id_uses_existing_glific_contact_id(
		self, mock_wa_id, mock_get_by_phone
	):
		row = frappe._dict({"glific_contact_id": "1001", "user": "user@test.com"})
		contact_id, err = _resolve_contact_id_for_member(row)
		self.assertEqual(contact_id, "1001")
		self.assertIsNone(err)
		mock_wa_id.assert_not_called()
		mock_get_by_phone.assert_not_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.get_contact_id_by_phone")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._wa_id_for_user")
	def test_resolve_contact_id_uses_wa_id_map_without_db_lookup(
		self, mock_wa_id, mock_get_by_phone
	):
		row = frappe._dict({"glific_contact_id": None, "user": "user@test.com", "mobile_no": None})
		contact_id, err = _resolve_contact_id_for_member(row, wa_id_map={"user@test.com": "2002"})
		self.assertEqual(contact_id, "2002")
		self.assertIsNone(err)
		mock_wa_id.assert_not_called()
		mock_get_by_phone.assert_not_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.get_contact_id_by_phone")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._wa_id_for_user", return_value="2002")
	def test_resolve_contact_id_uses_wa_id_without_phone_lookup(
		self, _mock_wa_id, mock_get_by_phone
	):
		row = frappe._dict({"glific_contact_id": None, "user": "user@test.com", "mobile_no": None})
		contact_id, err = _resolve_contact_id_for_member(row)
		self.assertEqual(contact_id, "2002")
		self.assertIsNone(err)
		mock_get_by_phone.assert_not_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.create_contact")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.get_contact_id_by_phone")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._wa_id_for_user", return_value=None)
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_group.glific_group.validate_and_normalize_mobile",
		return_value="919876543210",
	)
	def test_resolve_contact_id_phone_fallback(
		self, _mock_normalize, _mock_wa_id, mock_get_by_phone, mock_create_contact
	):
		mock_get_by_phone.return_value = "3003"
		row = frappe._dict(
			{
				"glific_contact_id": None,
				"user": "user@test.com",
				"mobile_no": "9876543210",
				"contact_name": "Alice",
			}
		)
		contact_id, err = _resolve_contact_id_for_member(row)
		self.assertEqual(contact_id, "3003")
		self.assertIsNone(err)
		mock_get_by_phone.assert_called_once_with("919876543210")
		mock_create_contact.assert_not_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.create_contact")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.get_contact_id_by_phone")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._wa_id_for_user", return_value=None)
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_group.glific_group.validate_and_normalize_mobile",
		return_value="919876543210",
	)
	def test_resolve_contact_id_creates_contact_when_missing(
		self, _mock_normalize, _mock_wa_id, mock_get_by_phone, mock_create_contact
	):
		mock_get_by_phone.return_value = None
		mock_create_contact.return_value = Result.success(message="ok", data="4004")
		row = frappe._dict(
			{
				"glific_contact_id": None,
				"user": "user@test.com",
				"mobile_no": "9876543210",
				"contact_name": "Alice",
			}
		)
		contact_id, err = _resolve_contact_id_for_member(row)
		self.assertEqual(contact_id, "4004")
		self.assertIsNone(err)
		mock_create_contact.assert_called_once()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._bulk_mark_members_synced")
	def test_chunked_add_contacts_to_group_batches_at_chunk_size(self, mock_bulk_synced):
		settings = MagicMock()
		settings.update_group_contacts.return_value = {
			"data": {"updateGroupContacts": {"errors": None}}
		}
		row_count = ADD_CONTACTS_CHUNK + 50
		rows = [(frappe._dict({"name": f"row-{i}"}), i + 1) for i in range(row_count)]
		total = _chunked_add_contacts_to_group(settings, "999", rows)
		self.assertEqual(total, row_count)
		self.assertEqual(settings.update_group_contacts.call_count, 2)
		self.assertEqual(mock_bulk_synced.call_count, 2)
		first_call_ids = settings.update_group_contacts.call_args_list[0].kwargs["add_contact_ids"]
		second_call_ids = settings.update_group_contacts.call_args_list[1].kwargs["add_contact_ids"]
		self.assertEqual(len(first_call_ids), ADD_CONTACTS_CHUNK)
		self.assertEqual(len(second_call_ids), 50)

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.sql")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.commit")
	def test_bulk_mark_members_synced_uses_single_sql_update(self, mock_commit, mock_sql):
		_bulk_mark_members_synced(["row-1", "row-2"])
		mock_sql.assert_called_once()
		self.assertIn("UPDATE", mock_sql.call_args.args[0])
		self.assertIn("IN", mock_sql.call_args.args[0])
		mock_commit.assert_called_once()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.GlificManager.get_contact_id_by_phone")
	def test_resolve_contact_id_skips_phone_lookup_when_requested(self, mock_get_by_phone):
		row = frappe._dict(
			{
				"glific_contact_id": None,
				"user": "user@test.com",
				"mobile_no": "9876543210",
			}
		)
		contact_id, err = _resolve_contact_id_for_member(
			row, wa_id_map={}, skip_phone_lookup=True
		)
		self.assertIsNone(contact_id)
		self.assertIsNotNone(err)
		mock_get_by_phone.assert_not_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.sql")
	def test_fetch_pending_members_excludes_synced(self, mock_sql):
		mock_sql.return_value = [{"name": "row-1", "status": "Pending"}]
		rows = _fetch_pending_members("Test Group", limit=10)
		self.assertEqual(len(rows), 1)
		query = mock_sql.call_args.args[0]
		self.assertIn("= 'Pending'", query)
		self.assertEqual(mock_sql.call_args.args[1]["limit"], 10)

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_pending_members")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._chunked_add_contacts_to_group")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._bulk_update_member_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._prefetch_wa_id_map", return_value={})
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._fetch_pending_members")
	def test_sync_member_batch_reports_has_more(
		self,
		mock_fetch,
		_mock_prefetch,
		_mock_bulk_update,
		mock_chunked,
		mock_pending_count,
	):
		mock_fetch.return_value = [
			frappe._dict(
				{
					"name": "row-1",
					"user": "user@test.com",
					"glific_contact_id": "42",
					"status": "Pending",
				}
			)
		]
		mock_chunked.return_value = 1
		mock_pending_count.return_value = 5

		result = _sync_member_batch("Test Group", "999", batch_limit=SYNC_MEMBER_BATCH_LIMIT)

		self.assertEqual(result["processed"], 1)
		self.assertEqual(result["added"], 1)
		self.assertTrue(result["has_more"])

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.commit")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._enqueue_glific_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._sync_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_members", return_value=100)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_all_members", return_value=500)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.set_value")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.get_value")
	def test_batch_background_re_enqueues_when_more_pending(
		self,
		mock_get_value,
		_mock_set_value,
		_mock_count_all,
		_mock_count_synced,
		mock_batch,
		mock_enqueue_batch,
		_mock_commit,
		mock_send_email,
	):
		mock_get_value.side_effect = lambda dt, name, field, *args, **kwargs: (
			"12345"
			if field == "glific_group_id"
			else "Pending"
			if field == "glific_sync_status"
			else None
		)
		mock_batch.return_value = {
			"processed": SYNC_MEMBER_BATCH_LIMIT,
			"added": SYNC_MEMBER_BATCH_LIMIT,
			"failed": 0,
			"has_more": True,
		}

		_sync_glific_members_batch_background(
			"Test Group",
			user="Administrator",
			job_key="sync_Test Group",
			thread_message_id="glific-job.sync@test-site",
			initiated_by="Administrator",
		)

		mock_send_email.assert_called_once()
		self.assertEqual(mock_send_email.call_args.args[1], "Started")
		mock_enqueue_batch.assert_called_once()
		self.assertTrue(mock_enqueue_batch.call_args.kwargs.get("continuation"))

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.commit")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._enqueue_glific_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._sync_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_members", return_value=100)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_all_members", return_value=500)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.set_value")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.get_value")
	def test_batch_continuation_does_not_send_started_email(
		self,
		mock_get_value,
		_mock_set_value,
		_mock_count_all,
		_mock_count_synced,
		mock_batch,
		mock_enqueue_batch,
		_mock_commit,
		mock_send_email,
	):
		mock_get_value.side_effect = lambda dt, name, field, *args, **kwargs: (
			"12345"
			if field == "glific_group_id"
			else "In Progress"
			if field == "glific_sync_status"
			else None
		)
		mock_batch.return_value = {
			"processed": SYNC_MEMBER_BATCH_LIMIT,
			"added": SYNC_MEMBER_BATCH_LIMIT,
			"failed": 0,
			"has_more": True,
		}

		_sync_glific_members_batch_background(
			"Test Group",
			user="Administrator",
			job_key="sync_Test Group",
			thread_message_id="glific-job.sync@test-site",
			initiated_by="Administrator",
		)

		mock_send_email.assert_not_called()
		mock_enqueue_batch.assert_called_once()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.commit")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._enqueue_glific_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._sync_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_members", return_value=500)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_all_members", return_value=500)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.set_value")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.get_value")
	def test_batch_background_marks_completed_when_no_more_pending(
		self,
		mock_get_value,
		mock_set_value,
		_mock_count_all,
		_mock_count_synced,
		mock_batch,
		mock_enqueue_batch,
		_mock_commit,
		mock_send_email,
	):
		mock_get_value.side_effect = lambda dt, name, field, *args, **kwargs: (
			"12345"
			if field == "glific_group_id"
			else "In Progress"
			if field == "glific_sync_status"
			else None
		)
		mock_batch.return_value = {
			"processed": 10,
			"added": 10,
			"failed": 0,
			"has_more": False,
		}

		_sync_glific_members_batch_background(
			"Test Group",
			user="Administrator",
			job_key="sync_Test Group",
			thread_message_id="glific-job.sync@test-site",
			initiated_by="Administrator",
		)

		mock_enqueue_batch.assert_not_called()
		completed_email = [
			c for c in mock_send_email.call_args_list if c.args[1] == "Completed"
		]
		self.assertTrue(completed_email)
		completed_call = [
			c
			for c in mock_set_value.call_args_list
			if len(c.args) >= 3 and isinstance(c.args[2], dict) and c.args[2].get("glific_sync_status") == "Completed"
		]
		self.assertTrue(completed_call)

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.enqueue")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	def test_delete_always_queues_background(self, mock_send_email, mock_enqueue):
		doc = MagicMock()
		doc.name = "Small Cohort"
		with patch(
			"solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc",
			return_value=doc,
		):
			result = delete_glific_group_manage("Small Cohort")

		self.assertTrue(result["queued"])
		mock_send_email.assert_called_once()
		self.assertEqual(mock_send_email.call_args.args[1], "Queued")
		mock_enqueue.assert_called_once()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.delete_doc")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_contact_ids", return_value=0)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc")
	def test_delete_background_sends_completed_email(
		self, mock_get_doc, _mock_count_synced, mock_delete_doc, mock_send_email
	):
		settings = MagicMock()
		settings.delete_group.return_value = {
			"data": {"deleteGroup": {"errors": None}}
		}
		mock_get_doc.return_value = settings

		_delete_glific_group_background(
			"Test Group",
			"Administrator",
			"delete_Test Group",
			"glific-job.delete@test-site",
		)

		mock_delete_doc.assert_called_once_with("Glific Group", "Test Group", ignore_permissions=True)
		mock_send_email.assert_called_once()
		self.assertEqual(mock_send_email.call_args.args[1], "Completed")
		self.assertEqual(mock_send_email.call_args.kwargs["in_reply_to"], "glific-job.delete@test-site")

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.delete_doc")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._bulk_clear_removed_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._chunked_remove_contacts_from_group")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._fetch_synced_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc")
	def test_delete_clears_contacts_before_delete_group(
		self,
		mock_get_doc,
		mock_count_synced,
		mock_fetch_synced,
		mock_chunked_remove,
		_mock_clear,
		mock_delete_doc,
		mock_send_email,
	):
		settings = MagicMock()
		settings.delete_group.return_value = {
			"data": {"deleteGroup": {"errors": None}}
		}
		mock_get_doc.return_value = settings
		mock_count_synced.side_effect = [2, 0]
		mock_fetch_synced.return_value = [101, 102]

		with patch(
			"solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.get_value",
			return_value="20806",
		):
			_delete_glific_group_background(
				"Test Group",
				"Administrator",
				"delete_Test Group",
				"glific-job.delete@test-site",
			)

		mock_chunked_remove.assert_called_once_with(settings, "20806", [101, 102])
		settings.delete_group.assert_called_once()
		mock_delete_doc.assert_called_once()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._enqueue_glific_delete_continuation")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._bulk_clear_removed_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._chunked_remove_contacts_from_group")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._fetch_synced_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc")
	def test_delete_re_enqueues_when_many_contacts(
		self,
		mock_get_doc,
		mock_count_synced,
		mock_fetch_synced,
		mock_chunked_remove,
		_mock_clear,
		mock_enqueue_continuation,
	):
		settings = MagicMock()
		mock_get_doc.return_value = settings
		mock_count_synced.side_effect = [DELETE_CONTACTS_BATCH_LIMIT + 1, 5000]
		mock_fetch_synced.return_value = list(range(1, DELETE_CONTACTS_BATCH_LIMIT + 1))

		with patch(
			"solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.get_value",
			return_value="20806",
		):
			_delete_glific_group_background(
				"Test Group",
				"Administrator",
				"delete_Test Group",
				"glific-job.delete@test-site",
			)

		mock_chunked_remove.assert_called_once()
		mock_enqueue_continuation.assert_called_once()
		settings.delete_group.assert_not_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.send_glific_job_email")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.delete_doc")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._chunked_remove_contacts_from_group")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._count_synced_contact_ids", return_value=0)
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc")
	def test_delete_skips_clear_when_no_synced_ids(
		self,
		mock_get_doc,
		_mock_count_synced,
		mock_chunked_remove,
		mock_delete_doc,
		_mock_send_email,
	):
		settings = MagicMock()
		settings.delete_group.return_value = {
			"data": {"deleteGroup": {"errors": None}}
		}
		mock_get_doc.return_value = settings

		with patch(
			"solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.get_value",
			return_value="20806",
		):
			_delete_glific_group_background(
				"Test Group",
				"Administrator",
				"delete_Test Group",
				"glific-job.delete@test-site",
			)

		mock_chunked_remove.assert_not_called()
		settings.delete_group.assert_called_once()
		mock_delete_doc.assert_called_once()

	def test_chunked_remove_contacts_calls_update_in_chunks(self):
		settings = MagicMock()
		settings.update_group_contacts.return_value = {
			"data": {"updateGroupContacts": {"errors": None}}
		}
		contact_ids = list(range(ADD_CONTACTS_CHUNK + 50))

		removed = _chunked_remove_contacts_from_group(settings, "999", contact_ids)

		self.assertEqual(removed, len(contact_ids))
		self.assertEqual(settings.update_group_contacts.call_count, 2)
		first_call = settings.update_group_contacts.call_args_list[0]
		self.assertEqual(first_call.kwargs["delete_contact_ids"], contact_ids[:ADD_CONTACTS_CHUNK])
		self.assertEqual(first_call.kwargs["add_contact_ids"], [])

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._bulk_mark_members_synced")
	def test_chunked_add_marks_rows_synced_only_after_success(self, mock_bulk_synced):
		settings = MagicMock()
		settings.update_group_contacts.return_value = {
			"data": {"updateGroupContacts": {"errors": None}}
		}
		row = frappe._dict({"name": "row-1", "status": "Pending", "error_message": "old"})
		total = _chunked_add_contacts_to_group(settings, "999", [(row, 1)])
		self.assertEqual(total, 1)
		self.assertEqual(row.status, "Synced")
		self.assertIsNone(row.error_message)
		mock_bulk_synced.assert_called_once_with(["row-1"])

	def test_chunked_add_does_not_mark_synced_on_failure(self):
		settings = MagicMock()
		settings.update_group_contacts.return_value = {"error": "boom"}
		row = frappe._dict({"name": "row-1", "status": "Pending", "glific_contact_id": "1"})
		with self.assertRaises(frappe.ValidationError):
			_chunked_add_contacts_to_group(settings, "999", [(row, 1)])
		self.assertEqual(row.status, "Pending")

	def test_should_enqueue_sync_for_monthly_cohort(self):
		doc = frappe._dict({"cohort_type": "Monthly Cohort", "members": []})
		self.assertTrue(_should_enqueue_sync(doc))

	def test_should_enqueue_sync_when_above_threshold(self):
		members = [
			frappe._dict({"status": "Pending", "glific_contact_id": None})
			for _ in range(SYNC_ENQUEUE_THRESHOLD + 1)
		]
		doc = frappe._dict({"cohort_type": "Custom Cohort", "members": members})
		self.assertTrue(_should_enqueue_sync(doc))

	def test_should_not_enqueue_sync_for_small_custom_cohort(self):
		doc = frappe._dict(
			{
				"cohort_type": "Custom Cohort",
				"members": [frappe._dict({"status": "Pending", "glific_contact_id": None})],
			}
		)
		self.assertFalse(_should_enqueue_sync(doc))

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._enqueue_glific_member_batch")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.db.set_value")
	def test_api_enqueues_large_monthly_cohort(self, mock_set_value, mock_enqueue_batch):
		doc = MagicMock()
		doc.name = "Potentials - June 2026"
		doc.get.side_effect = lambda key, default=None: (
			"Monthly Cohort" if key == "cohort_type" else default
		)
		doc.members = [MagicMock(status="Pending", glific_contact_id=None) for _ in range(10)]

		with patch(
			"solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc",
			return_value=doc,
		):
			result = sync_members_to_glific("Potentials - June 2026")

		self.assertTrue(result["queued"])
		mock_enqueue_batch.assert_called_once()
		mock_set_value.assert_called()

	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._chunked_add_contacts_to_group")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._bulk_update_member_contact_ids")
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._prefetch_wa_id_map", return_value={})
	@patch("solve_ninja.solve_ninja.doctype.glific_group.glific_group._resolve_contact_id_for_member")
	def test_sync_members_to_glific_persists_resolved_ids_via_bulk_update(
		self, mock_resolve, _mock_prefetch, mock_bulk_update, mock_chunked_add
	):
		mock_resolve.return_value = ("5555", None)
		mock_chunked_add.return_value = 1

		doc = frappe.get_doc(
			{
				"doctype": "Glific Group",
				"group_name": "Test Sync Group Bulk",
				"cohort_type": "Monthly Cohort",
				"cohort_month": "June",
				"cohort_year": 2026,
				"glific_group_id": "123",
				"members": [
					{
						"user": "sync-user@test.com",
						"mobile_no": "919876543210",
						"contact_name": "Sync User",
						"status": "Pending",
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)

		with patch(
			"solve_ninja.solve_ninja.doctype.glific_group.glific_group.frappe.get_doc",
			return_value=MagicMock(),
		):
			result = doc.sync_members_to_glific()

		self.assertEqual(result["added"], 1)
		self.assertEqual(doc.members[0].glific_contact_id, "5555")
		mock_bulk_update.assert_called_once()
		bulk_args = mock_bulk_update.call_args.args[0]
		self.assertEqual(bulk_args[0][1], "5555")
		mock_chunked_add.assert_called_once()

		doc.delete(ignore_permissions=True)
