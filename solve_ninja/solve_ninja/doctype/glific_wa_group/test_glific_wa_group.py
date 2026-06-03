# Copyright (c) 2026, ReapBenefit and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group import (
	_maybe_sync_wa_group_contacts_from_maytapi,
	apply_wa_group_api_dict_to_doc,
	contact_to_member_row,
	fetch_all_contacts_in_wa_group,
	fetch_wa_group_members,
	sync_all_glific_wa_groups_metadata,
	unwrap_wa_group_from_get_response,
)
from solve_ninja.api.glific_sync import bq_row_to_contact_dict


class TestGlificWAGroup(FrappeTestCase):
	def test_unwrap_wa_group_nested(self):
		resp = {
			"data": {
				"waGroup": {
					"waGroup": {
						"id": "5",
						"label": "My WA Group",
						"bspId": "120363123456789012@g.us",
						"lastCommunicationAt": "2024-01-01T00:00:00Z",
					},
					"errors": None,
				}
			}
		}
		g = unwrap_wa_group_from_get_response(resp)
		self.assertIsNotNone(g)
		self.assertEqual(g["id"], "5")
		self.assertEqual(g["label"], "My WA Group")

	def test_unwrap_wa_group_flat_node(self):
		resp = {
			"data": {
				"waGroup": {
					"id": "7",
					"label": "Flat",
					"bspId": "bsp-7",
				}
			}
		}
		g = unwrap_wa_group_from_get_response(resp)
		self.assertIsNotNone(g)
		self.assertEqual(g["id"], "7")

	def test_unwrap_returns_none_on_graphql_error(self):
		self.assertIsNone(unwrap_wa_group_from_get_response({"error": "network"}))

	def test_apply_wa_group_api_dict_to_doc(self):
		doc = self._new_wa_group_doc("100")
		apply_wa_group_api_dict_to_doc(
			doc,
			{
				"label": "Label A",
				"bspId": "120363001@g.us",
				"lastCommunicationAt": None,
			},
		)
		self.assertEqual(doc.group_label, "Label A")
		self.assertEqual(doc.bsp_id, "120363001@g.us")

	@patch("solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.frappe.db.get_value")
	def test_contact_to_member_row_links_user_via_wa_id(self, mock_get_value):
		def get_value_side_effect(doctype, filters=None, fieldname=None, **kwargs):
			if doctype == "Ninja Profile" and filters == {"wa_id": "42"}:
				return "user@test.com"
			return None

		mock_get_value.side_effect = get_value_side_effect
		row = contact_to_member_row({"id": "42", "name": "Alice", "phone": "+911234567890"})
		self.assertEqual(row["glific_contact_id"], "42")
		self.assertEqual(row["contact_name"], "Alice")
		self.assertEqual(row["user"], "user@test.com")
		self.assertEqual(row["status"], "Synced")

	@patch("solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.frappe.db.get_value")
	def test_contact_to_member_row_phone_fallback_when_no_wa_id_match(self, mock_get_value):
		def get_value_side_effect(doctype, filters=None, fieldname=None, **kwargs):
			if doctype == "Ninja Profile":
				return None
			if doctype == "User":
				return "phone-user@test.com"
			return None

		mock_get_value.side_effect = get_value_side_effect
		with patch(
			"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.validate_and_normalize_mobile",
			return_value="+911234567890",
		):
			row = contact_to_member_row(
				{"id": "99", "name": "Bob", "phone": "+91 12345 67890"}
			)
		self.assertEqual(row["user"], "phone-user@test.com")

	def test_bq_row_to_contact_dict(self):
		contact = bq_row_to_contact_dict(
			{
				"glific_contact_id": 927601,
				"contact_name": "Alice",
				"phone": "919876543210",
			}
		)
		self.assertEqual(contact["id"], "927601")
		self.assertEqual(contact["name"], "Alice")
		self.assertEqual(contact["phone"], "919876543210")

	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.fetch_all_contacts_in_wa_group"
	)
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.fetch_all_contacts_in_wa_group_from_bigquery"
	)
	@patch(
		"solve_ninja.api.glific_sync.bigquery_client_available",
		return_value=True,
	)
	def test_fetch_wa_group_members_uses_bigquery(self, _mock_cfg, mock_bq, mock_api):
		mock_bq.return_value = ([{"id": "1", "name": "A", "phone": "1"}], None)
		settings = MagicMock()
		contacts, err, source = fetch_wa_group_members(settings, "9276", source="bigquery")
		self.assertIsNone(err)
		self.assertEqual(source, "bigquery")
		self.assertEqual(len(contacts), 1)
		mock_api.assert_not_called()

	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.fetch_all_contacts_in_wa_group"
	)
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.fetch_all_contacts_in_wa_group_from_bigquery"
	)
	@patch(
		"solve_ninja.api.glific_sync.bigquery_client_available",
		return_value=True,
	)
	def test_fetch_wa_group_members_falls_back_to_api_on_bq_error(
		self, _mock_cfg, mock_bq, mock_api
	):
		mock_bq.return_value = ([], "bq failed")
		mock_api.return_value = ([{"id": "2", "name": "B", "phone": "2"}], None)
		settings = MagicMock()
		contacts, err, source = fetch_wa_group_members(settings, "9276", source="bigquery")
		self.assertIsNone(err)
		self.assertEqual(source, "api")
		self.assertEqual(len(contacts), 1)
		mock_api.assert_called_once()

	def test_fetch_all_contacts_in_wa_group_pagination(self):
		settings = MagicMock()
		settings.list_contact_wa_group.side_effect = [
			{
				"data": {
					"listContactWaGroup": [
						{"contact": {"id": "1", "name": "A", "phone": "1"}},
						{"contact": {"id": "2", "name": "B", "phone": "2"}},
					]
				}
			},
			{
				"data": {
					"listContactWaGroup": [
						{"contact": {"id": "3", "name": "C", "phone": "3"}},
					]
				}
			},
			{"data": {"listContactWaGroup": []}},
		]
		rows, err = fetch_all_contacts_in_wa_group(settings, "99")
		self.assertIsNone(err)
		self.assertEqual(len(rows), 3)
		self.assertEqual(settings.list_contact_wa_group.call_count, 3)

	def test_fetch_all_contacts_in_wa_group_error_returns_empty(self):
		settings = MagicMock()
		settings.list_contact_wa_group.return_value = {"error": "unauthorized"}
		rows, err = fetch_all_contacts_in_wa_group(settings, "99")
		self.assertEqual(rows, [])
		self.assertIsNotNone(err)

	@patch("frappe.utils.now", return_value="2026-01-01 00:00:00.000000")
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.frappe.get_doc"
	)
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.frappe.db.exists"
	)
	@patch(
		"solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.fetch_wa_group_member_count"
	)
	def test_sync_all_metadata_upserts(self, mock_member_count, mock_exists, mock_get_doc, mock_now):
		mock_exists.return_value = False
		mock_member_count.return_value = (2, None)

		wa_doc = MagicMock()
		wa_doc.flags = MagicMock()

		settings_inst = MagicMock()
		settings_inst.list_wa_groups.return_value = {
			"data": {
				"waGroups": [
					{
						"id": "1",
						"label": "G1",
						"bspId": "120363001@g.us",
						"lastCommunicationAt": None,
					}
				]
			}
		}

		def get_doc_side_effect(arg, *args, **kwargs):
			if arg == "Glific Settings":
				return settings_inst
			if isinstance(arg, dict):
				return wa_doc
			return wa_doc

		mock_get_doc.side_effect = get_doc_side_effect

		result = sync_all_glific_wa_groups_metadata()
		self.assertEqual(result.get("upserted"), 1)
		wa_doc.save.assert_called()

	def test_maybe_sync_wa_returns_error_when_glific_timed_out(self):
		settings = MagicMock()
		settings.sync_wa_group_contacts.return_value = {
			"error": (
				"Glific API timed out after 180s. "
				"For WhatsApp group refresh, try again or use Refresh from WhatsApp when Glific/Maytapi is responsive."
			)
		}
		err = _maybe_sync_wa_group_contacts_from_maytapi(settings)
		self.assertIsNotNone(err)
		self.assertIn("timed out", err.lower())

	def test_maybe_sync_wa_returns_none_on_success(self):
		settings = MagicMock()
		settings.sync_wa_group_contacts.return_value = {
			"data": {"syncWaGroupContacts": {"message": "successfully synced", "errors": None}}
		}
		err = _maybe_sync_wa_group_contacts_from_maytapi(settings)
		self.assertIsNone(err)

	def _new_wa_group_doc(self, gid: str):
		doc = frappe.new_doc("Glific WA Group")
		doc.glific_group_id = gid
		return doc
