# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import cint

from solve_ninja.services.glific_manager import GlificManager
from solve_ninja.utils import validate_and_normalize_mobile

MONTHLY_COHORT_TYPES = frozenset(("Monthly Cohort", "Automated Cohort"))

_COHORT_MONTHS = frozenset(
	(
		"January",
		"February",
		"March",
		"April",
		"May",
		"June",
		"July",
		"August",
		"September",
		"October",
		"November",
		"December",
	)
)


def _glific_branch_errors(branch):
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


class GlificGroup(Document):
	def validate(self):
		name = (self.group_name or "").strip()
		if not name:
			frappe.throw(_("Group Name is required."))
		self.group_name = name

		dup_filters = {"group_name": self.group_name}
		if self.name:
			dup_filters["name"] = ("!=", self.name)
		if frappe.db.exists("Glific Group", dup_filters):
			frappe.throw(_("A Glific Group with this Group Name already exists."))

		if not self.get("cohort_type"):
			self.cohort_type = "Custom Cohort"

		if self.get("cohort_type") == "Custom Cohort":
			self._validate_cohort_period(_("Custom Cohort"))
		elif self.get("cohort_type") in MONTHLY_COHORT_TYPES and self.get("automated_cohort_bucket"):
			self._validate_cohort_period(_("Monthly Cohort"))

	def _validate_cohort_period(self, label):
		if not self.get("cohort_month"):
			frappe.throw(_("Cohort month is required for {0}.").format(label))
		if self.get("cohort_month") not in _COHORT_MONTHS:
			frappe.throw(_("Invalid cohort month."))
		year = self.get("cohort_year")
		if year is None or year == "":
			frappe.throw(_("Cohort year is required for {0}.").format(label))
		try:
			y = int(year)
		except Exception:
			frappe.throw(_("Cohort year must be a whole number."))
		if y < 2000 or y > 2100:
			frappe.throw(_("Cohort year must be between 2000 and 2100."))

	def before_insert(self):
		if self.glific_group_id:
			return
		if self.get("audience_mode") == "Filtered":
			return
		if self.get("cohort_type") in MONTHLY_COHORT_TYPES:
			return
		settings = frappe.get_doc("Glific Settings")
		desc = (self.description or "").strip() or None
		response = settings.create_group(
			label=self.group_name,
			description=desc,
			is_restricted=bool(self.is_restricted),
		)
		if not response or response.get("error"):
			frappe.throw(
				_("Failed to reach Glific while creating group: {0}").format(
					(response or {}).get("error") or _("Unknown error")
				)
			)
		api_errors = _glific_branch_errors((response.get("data") or {}).get("createGroup") or {})
		if api_errors:
			frappe.throw(_("Failed to create group in Glific: {0}").format(api_errors))
		cg = (response.get("data") or {}).get("createGroup") or {}
		group = cg.get("group")
		if not group or not group.get("id"):
			frappe.throw(
				_("Glific did not return a group id. Response: {0}").format(
					json.dumps(response)[:2000]
				)
			)
		self.glific_group_id = str(group["id"])

	def sync_members_to_glific(self):
		"""Resolve Glific contacts for member rows and add them to this group in Glific."""
		if not self.glific_group_id:
			frappe.throw(_("Save the group first so Glific Group ID is set."))

		settings = frappe.get_doc("Glific Settings")
		add_contact_ids = []
		rows_prepared = []

		for row in self.members:
			row.error_message = None

			if row.status == "Synced" and row.glific_contact_id:
				continue

			mobile = (row.mobile_no or "").strip()
			if not mobile and row.get("user"):
				mobile = (frappe.db.get_value("User", row.user, "mobile_no") or "").strip()
			if not mobile:
				row.status = "Failed"
				row.error_message = _("Mobile No or User is required")
				continue

			if not (row.contact_name or "").strip() and row.get("user"):
				row.contact_name = frappe.db.get_value("User", row.user, "full_name") or ""

			try:
				phone = validate_and_normalize_mobile(mobile)
			except Exception as e:
				row.status = "Failed"
				row.error_message = str(e)
				continue

			contact_id = GlificManager.get_contact_id_by_phone(phone)
			if not contact_id:
				name = (row.contact_name or "").strip() or f"User {phone}"
				result = GlificManager.create_contact({"mobile_no": phone, "name": name})
				if result.is_internal_server_error or not result.data:
					row.status = "Failed"
					row.error_message = result.message or _("Could not create Glific contact")
					continue
				contact_id = str(result.data)

			row.glific_contact_id = str(contact_id)
			cid_int = int(contact_id)
			if cid_int not in add_contact_ids:
				add_contact_ids.append(cid_int)
			rows_prepared.append(row)

		if not add_contact_ids:
			self.save()
			return {"message": _("No new members to sync"), "added": 0}

		response = settings.update_group_contacts(
			self.glific_group_id,
			add_contact_ids=add_contact_ids,
			delete_contact_ids=[],
		)

		if not response or response.get("error"):
			frappe.throw(
				_("Glific request failed: {0}").format(
					(response or {}).get("error") or _("Unknown error")
				)
			)
		if response.get("errors"):
			frappe.throw(
				_("Glific GraphQL error: {0}").format(json.dumps(response.get("errors"))[:2000])
			)

		api_errors = _glific_branch_errors(
			(response.get("data") or {}).get("updateGroupContacts") or {}
		)
		if api_errors:
			frappe.throw(_("Failed to add contacts to group: {0}").format(api_errors))

		for row in rows_prepared:
			row.status = "Synced"
			row.error_message = None

		self.save()
		return {"message": _("Members synced"), "added": len(add_contact_ids)}


def _parse_whitelist_json_list(raw):
	if raw is None:
		return []
	if isinstance(raw, (list, tuple)):
		return [x for x in raw if x is not None and str(x).strip()]
	if isinstance(raw, str):
		parsed = frappe.parse_json(raw)
		return [x for x in (parsed or []) if x is not None and str(x).strip()]
	frappe.throw(_("Invalid list parameter"))


def _member_match_sets(member_row_names, member_keys):
	names_set = set(str(n).strip() for n in (member_row_names or []) if n is not None and str(n).strip())
	key_set = set()
	for k in member_keys or []:
		if not k:
			continue
		ks = str(k).strip()
		if ks.startswith("n:"):
			names_set.add(ks[2:].strip())
		elif ks.startswith("k:"):
			key_set.add(ks)
	return names_set, key_set


def _row_marked_for_removal(row, names_set, key_set):
	if row.name and str(row.name).strip() in names_set:
		return True
	u = (row.user or "").strip()
	rk = f"k:{row.idx or ''}:{u}"
	return rk in key_set


@frappe.whitelist()
def remove_members_from_glific_group(doc_name, member_row_names=None, member_keys=None):
	"""Remove members from Glific via updateGroupContacts, then strip child rows."""
	member_row_names = _parse_whitelist_json_list(member_row_names)
	member_keys = _parse_whitelist_json_list(member_keys)
	if not member_row_names and not member_keys:
		frappe.throw(_("Select at least one member"))

	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("write")

	names_set, key_set = _member_match_sets(member_row_names, member_keys)
	to_remove = [r for r in doc.members if _row_marked_for_removal(r, names_set, key_set)]
	if not to_remove:
		frappe.throw(_("No matching member rows"))

	delete_contact_ids = []
	seen_cid = set()
	for row in to_remove:
		cid = (row.glific_contact_id or "").strip()
		if not cid:
			continue
		try:
			cidi = int(cid)
		except ValueError:
			continue
		if cidi not in seen_cid:
			seen_cid.add(cidi)
			delete_contact_ids.append(cidi)

	gid = (doc.glific_group_id or "").strip()
	settings = frappe.get_doc("Glific Settings")

	if delete_contact_ids:
		if not gid:
			frappe.throw(
				_("Save the cohort with a Glific Group ID before removing synced contacts.")
			)
		response = settings.update_group_contacts(
			gid,
			add_contact_ids=[],
			delete_contact_ids=delete_contact_ids,
		)
		if not response or response.get("error"):
			frappe.throw(
				_("Glific request failed: {0}").format(
					(response or {}).get("error") or _("Unknown error")
				)
			)
		if response.get("errors"):
			frappe.throw(
				_("Glific GraphQL error: {0}").format(json.dumps(response.get("errors"))[:2000])
			)
		api_errors = _glific_branch_errors(
			(response.get("data") or {}).get("updateGroupContacts") or {}
		)
		if api_errors:
			frappe.throw(_("Failed to remove contacts from Glific: {0}").format(api_errors))

	for row in list(doc.members):
		if _row_marked_for_removal(row, names_set, key_set):
			doc.remove(row)

	for i, row in enumerate(doc.members, start=1):
		row.idx = i

	doc.save()
	return {
		"removed_local": len(to_remove),
		"removed_glific": len(delete_contact_ids),
	}


@frappe.whitelist()
def delete_glific_group_manage(doc_name):
	"""Delete the group in Glific, then delete the Glific Group document."""
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("delete")

	gid = (doc.glific_group_id or "").strip()
	settings = frappe.get_doc("Glific Settings")

	if gid:
		response = settings.delete_group(gid)
		if not response or response.get("error"):
			frappe.throw(
				_("Glific request failed: {0}").format(
					(response or {}).get("error") or _("Unknown error")
				)
			)
		if response.get("errors"):
			frappe.throw(
				_("Glific GraphQL error: {0}").format(json.dumps(response.get("errors"))[:2000])
			)
		api_errors = _glific_branch_errors((response.get("data") or {}).get("deleteGroup") or {})
		if api_errors:
			frappe.throw(_("Failed to delete group in Glific: {0}").format(api_errors))

	doc.delete()
	return {"message": _("Glific Group deleted")}


@frappe.whitelist()
def sync_members_to_glific(doc_name):
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("write")
	return doc.sync_members_to_glific()


@frappe.whitelist()
def get_manage_cohort_summaries(limit=500):
	"""List cohorts with member counts — permission-safe via frappe.get_list."""
	limit_i = max(1, min(cint(limit) or 500, 2000))
	meta_list = frappe.get_list(
		"Glific Group",
		fields=[
			"name",
			"group_name",
			"cohort_type",
			"automated_cohort_bucket",
			"cohort_month",
			"cohort_year",
			"glific_sync_status",
			"creation",
		],
		order_by="modified desc",
		limit_page_length=limit_i,
	)
	if not meta_list:
		return []
	parents = [row["name"] for row in meta_list]
	cnt_rows = frappe.db.sql(
		"""
		SELECT parent, COUNT(*) AS member_count
		FROM `tabGlific Group Contact`
		WHERE parenttype = 'Glific Group' AND parent IN %(parents)s
		GROUP BY parent
		""",
		{"parents": parents},
		as_dict=True,
	)
	cnt_map = {r.parent: int(r.member_count) for r in cnt_rows}
	for row in meta_list:
		row["member_count"] = cnt_map.get(row["name"], 0)
	return meta_list
