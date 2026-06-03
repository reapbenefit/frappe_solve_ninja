# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

"""Pull Glific WhatsApp groups into ``Glific WA Group`` with member rows."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from solve_ninja.utils import validate_and_normalize_mobile

MEMBER_PAGE_SIZE = 100
GROUP_PAGE_SIZE = 100


def _parse_glific_datetime(val) -> Optional[datetime]:
	if val is None or val == "":
		return None
	if isinstance(val, datetime):
		return val
	try:
		return frappe.utils.get_datetime(val)
	except Exception:
		return None


def _glific_branch_errors(branch) -> Optional[str]:
	if not branch or not isinstance(branch, dict):
		return None
	errors = branch.get("errors")
	if not errors:
		return None
	parts = []
	for err in errors:
		if isinstance(err, dict):
			parts.append(err.get("message") or err.get("key") or json.dumps(err))
		else:
			parts.append(str(err))
	return "; ".join(parts) if parts else None


def unwrap_wa_group_from_get_response(response: Optional[dict]) -> Optional[Dict[str, Any]]:
	"""Resolve ``WaGroup`` dict from Glific ``waGroup(id)`` / WaGroupResult response."""
	if not response or response.get("error"):
		return None
	data = response.get("data") or {}
	node = data.get("waGroup")
	if not isinstance(node, dict):
		return None
	err_msg = _glific_branch_errors(node)
	if err_msg:
		return None
	inner = node.get("waGroup")
	if isinstance(inner, dict) and inner.get("id") is not None:
		return inner
	if node.get("id") is not None:
		return node
	return None


def apply_wa_group_api_dict_to_doc(doc: Document, g: Dict[str, Any]) -> None:
	"""Map Glific ``WaGroup`` JSON fields onto ``Glific WA Group``."""
	doc.group_label = (g.get("label") or "").strip() or doc.group_label
	bsp = g.get("bspId") or g.get("bsp_id")
	if bsp is not None:
		doc.bsp_id = str(bsp).strip() or doc.bsp_id
	doc.last_communication_at = _parse_glific_datetime(
		g.get("lastCommunicationAt") or g.get("last_communication_at")
	)


def _resolve_user_for_contact(glific_contact_id: str, phone: str) -> Optional[str]:
	"""Resolve ERP User via Ninja Profile.wa_id, then mobile_no fallback."""
	cid = str(glific_contact_id or "").strip()
	if cid:
		user = frappe.db.get_value("Ninja Profile", {"wa_id": cid}, "user")
		if user:
			return user
	if phone:
		try:
			mobile_disp = validate_and_normalize_mobile(phone)
			return frappe.db.get_value("User", {"mobile_no": mobile_disp}, "name")
		except Exception:
			pass
	return None


def contact_to_member_row(contact: Dict[str, Any]) -> Dict[str, Any]:
	phone = (contact.get("phone") or "").strip()
	cid = str(contact.get("id") or "").strip()
	name = (contact.get("name") or "").strip()
	mobile_disp = phone
	if phone:
		try:
			mobile_disp = validate_and_normalize_mobile(phone)
		except Exception:
			pass
	user = _resolve_user_for_contact(cid, phone)
	return {
		"user": user,
		"mobile_no": mobile_disp or None,
		"contact_name": name,
		"glific_contact_id": cid,
		"status": "Synced",
		"error_message": None,
	}


def contact_wa_group_row_to_contact(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	contact = row.get("contact")
	if isinstance(contact, dict) and contact.get("id") is not None:
		return contact
	return None


def fetch_all_contacts_in_wa_group(
	settings, wa_group_id: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
	"""Paginate ``listContactWaGroup``; returns (contacts, error_message)."""
	wa_group_id = str(wa_group_id or "").strip()
	if not wa_group_id:
		return [], _("Invalid Glific WA Group ID")

	all_rows: List[Dict[str, Any]] = []
	offset = 0
	while True:
		resp = settings.list_contact_wa_group(
			wa_group_id,
			limit=MEMBER_PAGE_SIZE,
			offset=offset,
		)
		if not resp or resp.get("error"):
			return [], (resp or {}).get("error") or _("Glific request failed")
		if resp.get("errors"):
			return [], json.dumps(resp.get("errors"))[:2000]
		rows = (resp.get("data") or {}).get("listContactWaGroup") or []
		if not rows:
			break
		for row in rows:
			contact = contact_wa_group_row_to_contact(row)
			if contact:
				all_rows.append(contact)
		offset += len(rows)

	return all_rows, None


def fetch_all_contacts_in_wa_group_from_bigquery(
	wa_group_id: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
	"""Load members from BigQuery ``contacts_wa_groups`` + ``contacts``."""
	wa_group_id = str(wa_group_id or "").strip()
	if not wa_group_id:
		return [], _("Invalid Glific WA Group ID")

	try:
		gid_int = int(wa_group_id)
	except Exception:
		return [], _("Invalid Glific WA Group ID")

	from solve_ninja.api.glific_sync import (
		bigquery_client_available,
		fetch_wa_group_members_from_bigquery,
	)

	if not bigquery_client_available():
		return [], _(
			"BigQuery unavailable (check google_credentials_path and google-cloud-bigquery)"
		)

	try:
		contacts = fetch_wa_group_members_from_bigquery(gid_int)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "fetch_all_contacts_in_wa_group_from_bigquery")
		return [], str(e)

	return contacts, None


def fetch_wa_group_members(
	settings,
	wa_group_id: str,
	source: str = "bigquery",
) -> Tuple[List[Dict[str, Any]], Optional[str], str]:
	"""Fetch members from BigQuery (default) with GraphQL fallback on failure."""
	source = (source or "bigquery").strip().lower()
	if source == "api":
		contacts, err = fetch_all_contacts_in_wa_group(settings, wa_group_id)
		return contacts, err, "api"

	from solve_ninja.api.glific_sync import bigquery_client_available

	if bigquery_client_available():
		contacts, err = fetch_all_contacts_in_wa_group_from_bigquery(wa_group_id)
		if not err:
			return contacts, None, "bigquery"
		frappe.log_error(
			title="BigQuery WA group member fetch failed; falling back to Glific API",
			message=err,
		)
	else:
		frappe.log_error(
			title="BigQuery WA group member fetch skipped; falling back to Glific API",
			message=_(
				"BigQuery unavailable (check google_credentials_path and google-cloud-bigquery)"
			),
		)

	contacts, err = fetch_all_contacts_in_wa_group(settings, wa_group_id)
	return contacts, err, "api"


def fetch_wa_group_member_count(settings, wa_group_id: str) -> Tuple[Optional[int], Optional[str]]:
	wa_group_id = str(wa_group_id or "").strip()
	if not wa_group_id:
		return None, _("Invalid Glific WA Group ID")

	resp = settings.count_contact_wa_group(wa_group_id)
	if not resp or resp.get("error"):
		return None, (resp or {}).get("error") or _("Glific request failed")
	if resp.get("errors"):
		return None, json.dumps(resp.get("errors"))[:2000]
	count = (resp.get("data") or {}).get("countContactWaGroup")
	if count is None:
		return None, None
	return cint(count), None


def _maybe_sync_wa_group_contacts_from_maytapi(settings) -> Optional[str]:
	"""Ask Glific to refresh WA group membership from Maytapi; returns error message or None."""
	resp = settings.sync_wa_group_contacts()
	if not resp or resp.get("error"):
		return (resp or {}).get("error") or _("Glific request failed")
	if resp.get("errors"):
		return json.dumps(resp.get("errors"))[:2000]
	branch = (resp.get("data") or {}).get("syncWaGroupContacts") or {}
	api_err = _glific_branch_errors(branch)
	if api_err:
		return api_err
	return None


class GlificWAGroup(Document):
	def apply_members_from_contacts(self, contacts: List[Dict[str, Any]]) -> None:
		self.members = []
		for c in contacts:
			self.append("members", contact_to_member_row(c))
		self.contacts_count = len(contacts)

	def sync_members_from_glific(
		self, refresh_from_maytapi: bool = False, source: str = "bigquery"
	) -> Dict[str, Any]:
		if not self.glific_group_id:
			frappe.throw(_("Glific WA Group ID is required"))

		settings = frappe.get_doc("Glific Settings")
		if refresh_from_maytapi:
			sync_err = _maybe_sync_wa_group_contacts_from_maytapi(settings)
			if sync_err:
				return {"ok": False, "error": sync_err, "members": 0}

		contacts, err, used_source = fetch_wa_group_members(
			settings, self.glific_group_id, source=source
		)
		if err:
			return {"ok": False, "error": err, "members": 0, "source": used_source}

		self.apply_members_from_contacts(contacts)
		return {
			"ok": True,
			"error": None,
			"members": len(contacts),
			"source": used_source,
		}

	def pull_metadata_from_glific(self) -> Tuple[bool, Optional[str]]:
		if not self.glific_group_id:
			return False, _("Glific WA Group ID is required")

		settings = frappe.get_doc("Glific Settings")
		resp = settings.get_wa_group(self.glific_group_id)
		g = unwrap_wa_group_from_get_response(resp)
		if not g:
			if resp and resp.get("error"):
				return False, str(resp.get("error"))
			if resp and resp.get("errors"):
				return False, json.dumps(resp.get("errors"))[:2000]
			api_err = _glific_branch_errors((resp.get("data") or {}).get("waGroup") or {})
			if api_err:
				return False, api_err
			return False, _("Glific did not return WhatsApp group details")

		apply_wa_group_api_dict_to_doc(self, g)
		count, count_err = fetch_wa_group_member_count(settings, self.glific_group_id)
		if count_err:
			return False, count_err
		if count is not None:
			self.contacts_count = count
		return True, None

	def pull_from_glific(
		self, include_members: bool = True, refresh_from_maytapi: bool = False
	) -> Dict[str, Any]:
		"""Refresh metadata and optionally members from Glific WhatsApp groups."""
		self.sync_error = None
		meta_ok, meta_err = self.pull_metadata_from_glific()
		if not meta_ok:
			self.sync_status = "Failed"
			self.sync_error = meta_err
			self.last_synced_on = frappe.utils.now()
			self.save()
			return {"ok": False, "error": meta_err, "members": 0}

		member_count = 0
		member_err = None
		if include_members:
			mres = self.sync_members_from_glific(refresh_from_maytapi=refresh_from_maytapi)
			member_count = mres.get("members") or 0
			if not mres.get("ok"):
				member_err = mres.get("error")
				self.sync_status = "Partial"
				self.sync_error = member_err
			else:
				self.sync_status = "Success"
				self.sync_error = None
		else:
			self.sync_status = "Success"

		self.last_synced_on = frappe.utils.now()
		self.save()
		return {
			"ok": member_err is None or not include_members,
			"error": meta_err or member_err,
			"members": member_count,
			"sync_status": self.sync_status,
		}


def sync_all_glific_wa_groups_metadata() -> Dict[str, Any]:
	"""Paginated ``waGroups`` query; upsert metadata only (no member table refresh)."""
	settings = frappe.get_doc("Glific Settings")
	offset = 0
	seen = 0
	errors: List[str] = []

	while True:
		resp = settings.list_wa_groups(
			{},
			limit=GROUP_PAGE_SIZE,
			offset=offset,
		)
		if not resp or resp.get("error"):
			errors.append((resp or {}).get("error") or "unknown")
			break
		if resp.get("errors"):
			errors.append(json.dumps(resp.get("errors"))[:500])
			break

		groups = (resp.get("data") or {}).get("waGroups") or []
		if not groups:
			break

		for g in groups:
			gid = str(g.get("id") or "").strip()
			if not gid:
				continue
			if frappe.db.exists("Glific WA Group", gid):
				doc = frappe.get_doc("Glific WA Group", gid)
			else:
				doc = frappe.get_doc(
					{"doctype": "Glific WA Group", "glific_group_id": gid}
				)
			doc.flags.ignore_permissions = True
			apply_wa_group_api_dict_to_doc(doc, g)
			count, count_err = fetch_wa_group_member_count(settings, gid)
			if count_err:
				errors.append(f"{gid}: {count_err}")
			elif count is not None:
				doc.contacts_count = count
			doc.sync_status = "Success"
			doc.sync_error = None
			doc.last_synced_on = frappe.utils.now()
			try:
				doc.save()
				seen += 1
			except Exception as e:
				errors.append(f"{gid}: {e!s}")

		if len(groups) < GROUP_PAGE_SIZE:
			break
		offset += GROUP_PAGE_SIZE

	return {
		"upserted": seen,
		"errors": errors,
	}


@frappe.whitelist()
def pull_glific_wa_group_from_glific(
	doc_name: str, include_members: int = 1, refresh_from_maytapi: int = 0
):
	doc = frappe.get_doc("Glific WA Group", doc_name)
	doc.check_permission("write")
	return doc.pull_from_glific(
		include_members=bool(cint(include_members)),
		refresh_from_maytapi=bool(cint(refresh_from_maytapi)),
	)


@frappe.whitelist()
def sync_glific_wa_group_members(
	doc_name: str, refresh_from_maytapi: int = 0, source: str = "bigquery"
):
	doc = frappe.get_doc("Glific WA Group", doc_name)
	doc.check_permission("write")
	doc.sync_error = None
	res = doc.sync_members_from_glific(
		refresh_from_maytapi=bool(cint(refresh_from_maytapi)),
		source=source or "bigquery",
	)
	if res.get("ok"):
		doc.sync_status = "Success"
		doc.sync_error = None
	else:
		doc.sync_status = "Partial"
		doc.sync_error = res.get("error")
	doc.last_synced_on = frappe.utils.now()
	doc.save()
	return res


@frappe.whitelist()
def sync_glific_wa_group_members_from_bigquery(doc_name: str):
	return sync_glific_wa_group_members(doc_name, source="bigquery")


@frappe.whitelist()
def sync_glific_wa_group_members_from_api(doc_name: str, refresh_from_maytapi: int = 0):
	return sync_glific_wa_group_members(
		doc_name, refresh_from_maytapi=refresh_from_maytapi, source="api"
	)


@frappe.whitelist()
def run_glific_wa_groups_metadata_sync():
	frappe.only_for("System Manager")
	return sync_all_glific_wa_groups_metadata()


def scheduled_sync_glific_wa_groups_metadata():
	"""Called from hooks ``scheduler_events``; metadata only."""
	try:
		sync_all_glific_wa_groups_metadata()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "scheduled_sync_glific_wa_groups_metadata")
