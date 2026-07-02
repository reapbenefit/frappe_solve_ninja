# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.data import cint

from solve_ninja.api.v1.glific_cohort_notifications import (
	glific_job_thread_message_id,
	send_glific_job_email,
)
from solve_ninja.services.glific_manager import GlificManager
from solve_ninja.solve_ninja.doctype.glific_settings.glific_settings import DELETE_GROUP_TIMEOUT
from solve_ninja.utils import validate_and_normalize_mobile

MONTHLY_COHORT_TYPES = frozenset(("Monthly Cohort", "Automated Cohort"))
ADD_CONTACTS_CHUNK = 500
SYNC_MEMBER_BATCH_LIMIT = 20000
DELETE_CONTACTS_BATCH_LIMIT = 20000
SYNC_ENQUEUE_THRESHOLD = 500

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


def _parse_glific_contact_id(raw):
	if raw is None or str(raw).strip() == "":
		return None
	try:
		return str(int(str(raw).strip()))
	except (ValueError, TypeError):
		return None


def _wa_id_for_user(user):
	if not user:
		return None
	return _parse_glific_contact_id(frappe.db.get_value("Ninja Profile", user, "wa_id"))


def _prefetch_wa_id_map(users):
	users = list({u for u in users if u})
	if not users:
		return {}
	rows = frappe.get_all(
		"Ninja Profile",
		filters={"user": ["in", users]},
		fields=["user", "wa_id"],
	)
	out = {}
	for row in rows:
		cid = _parse_glific_contact_id(row.get("wa_id"))
		if cid and row.get("user"):
			out[row.get("user")] = cid
	return out


def _resolve_contact_id_for_member(row, wa_id_map=None, skip_phone_lookup=False):
	"""Resolve Glific contact id: row id, Ninja Profile wa_id, then phone lookup/create."""
	contact_id = _parse_glific_contact_id(row.glific_contact_id)
	if not contact_id and row.get("user"):
		if wa_id_map is not None:
			contact_id = wa_id_map.get(row.user)
		else:
			contact_id = _wa_id_for_user(row.user)
	if contact_id:
		return contact_id, None

	if skip_phone_lookup:
		return None, _("Glific contact id or Ninja Profile wa_id is required")

	mobile = (row.mobile_no or "").strip()
	if not mobile and row.get("user"):
		mobile = (frappe.db.get_value("User", row.user, "mobile_no") or "").strip()
	if not mobile:
		return None, _("Mobile No or User is required")

	if not (row.contact_name or "").strip() and row.get("user"):
		row.contact_name = frappe.db.get_value("User", row.user, "full_name") or ""

	try:
		phone = validate_and_normalize_mobile(mobile)
	except Exception as e:
		return None, str(e)

	contact_id = GlificManager.get_contact_id_by_phone(phone)
	if not contact_id:
		name = (row.contact_name or "").strip() or f"User {phone}"
		result = GlificManager.create_contact({"mobile_no": phone, "name": name})
		if result.is_internal_server_error or not result.data:
			return None, result.message or _("Could not create Glific contact")
		contact_id = str(result.data)

	return str(contact_id), None


def _bulk_update_member_contact_ids(updates):
	"""Persist resolved Glific contact ids on child rows (status stays Pending)."""
	if not updates:
		return
	for i in range(0, len(updates), 500):
		chunk = updates[i : i + 500]
		case_parts = []
		params = {}
		names = []
		for j, (name, contact_id) in enumerate(chunk):
			case_parts.append(f"WHEN %(n{j})s THEN %(c{j})s")
			params[f"n{j}"] = name
			params[f"c{j}"] = contact_id
			names.append(name)
		params["names"] = tuple(names)
		frappe.db.sql(
			f"""
			UPDATE `tabGlific Group Contact`
			SET glific_contact_id = CASE name {' '.join(case_parts)} END
			WHERE name IN %(names)s
			""",
			params,
		)
	frappe.db.commit()


def _bulk_mark_members_failed(failed_updates):
	if not failed_updates:
		return
	for i in range(0, len(failed_updates), 500):
		chunk = failed_updates[i : i + 500]
		case_status = []
		case_err = []
		params = {}
		names = []
		for j, (name, err) in enumerate(chunk):
			case_status.append(f"WHEN %(n{j})s THEN 'Failed'")
			case_err.append(f"WHEN %(n{j})s THEN %(e{j})s")
			params[f"n{j}"] = name
			params[f"e{j}"] = (err or "")[:140]
			names.append(name)
		params["names"] = tuple(names)
		frappe.db.sql(
			f"""
			UPDATE `tabGlific Group Contact`
			SET status = CASE name {' '.join(case_status)} END,
			    error_message = CASE name {' '.join(case_err)} END
			WHERE name IN %(names)s
			""",
			params,
		)
	frappe.db.commit()


def _bulk_mark_members_synced(row_names):
	if not row_names:
		return
	frappe.db.sql(
		"""
		UPDATE `tabGlific Group Contact`
		SET status = 'Synced', error_message = NULL
		WHERE name IN %(names)s
		""",
		{"names": tuple(row_names)},
	)
	frappe.db.commit()


def _validate_update_group_contacts_response(response, action="add"):
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
	api_errors = _glific_branch_errors((response.get("data") or {}).get("updateGroupContacts") or {})
	if api_errors:
		label = (
			_("add contacts to group")
			if action == "add"
			else _("remove contacts from group")
		)
		frappe.throw(_("Failed to {0}: {1}").format(label, api_errors))


def _chunked_add_contacts_to_group(settings, group_id, rows_prepared):
	"""Add contacts in chunks; bulk-update child rows to Synced after each successful chunk."""
	total_added = 0
	for i in range(0, len(rows_prepared), ADD_CONTACTS_CHUNK):
		chunk = rows_prepared[i : i + ADD_CONTACTS_CHUNK]
		chunk_ids = []
		seen = set()
		for _row, cid_int in chunk:
			if cid_int not in seen:
				seen.add(cid_int)
				chunk_ids.append(cid_int)

		response = settings.update_group_contacts(
			group_id,
			add_contact_ids=chunk_ids,
			delete_contact_ids=[],
		)
		_validate_update_group_contacts_response(response)

		synced_names = []
		for row, _cid_int in chunk:
			row.status = "Synced"
			row.error_message = None
			if row.name:
				synced_names.append(row.name)

		_bulk_mark_members_synced(synced_names)
		total_added += len(chunk_ids)

	return total_added


def _chunked_remove_contacts_from_group(settings, group_id, contact_ids):
	"""Remove contacts from a Glific group in ADD_CONTACTS_CHUNK batches."""
	if not contact_ids:
		return 0

	total_removed = 0
	for i in range(0, len(contact_ids), ADD_CONTACTS_CHUNK):
		chunk = contact_ids[i : i + ADD_CONTACTS_CHUNK]
		response = settings.update_group_contacts(
			group_id,
			add_contact_ids=[],
			delete_contact_ids=chunk,
		)
		_validate_update_group_contacts_response(response, action="remove")
		total_removed += len(chunk)

	return total_removed


def _count_synced_contact_ids(doc_name):
	result = frappe.db.sql(
		"""
		SELECT COUNT(DISTINCT glific_contact_id) FROM `tabGlific Group Contact`
		WHERE parent = %(parent)s
		  AND parenttype = 'Glific Group'
		  AND status = 'Synced'
		  AND glific_contact_id IS NOT NULL
		  AND glific_contact_id != ''
		""",
		{"parent": doc_name},
	)
	return cint(result[0][0] if result else 0)


def _fetch_synced_contact_ids(doc_name, limit=DELETE_CONTACTS_BATCH_LIMIT):
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT glific_contact_id
		FROM `tabGlific Group Contact`
		WHERE parent = %(parent)s
		  AND parenttype = 'Glific Group'
		  AND status = 'Synced'
		  AND glific_contact_id IS NOT NULL
		  AND glific_contact_id != ''
		ORDER BY glific_contact_id
		LIMIT %(limit)s
		""",
		{"parent": doc_name, "limit": cint(limit)},
		as_dict=True,
	)
	contact_ids = []
	seen = set()
	for row in rows:
		cid = _parse_glific_contact_id(row.glific_contact_id)
		if not cid:
			continue
		cidi = int(cid)
		if cidi in seen:
			continue
		seen.add(cidi)
		contact_ids.append(cidi)
	return contact_ids


def _bulk_clear_removed_contact_ids(doc_name, contact_ids):
	"""Clear local glific_contact_id after successful Glific removal (delete continuation)."""
	if not contact_ids:
		return
	id_strings = tuple(str(x) for x in contact_ids)
	frappe.db.sql(
		"""
		UPDATE `tabGlific Group Contact`
		SET glific_contact_id = NULL
		WHERE parent = %(parent)s
		  AND parenttype = 'Glific Group'
		  AND status = 'Synced'
		  AND glific_contact_id IN %(ids)s
		""",
		{"parent": doc_name, "ids": id_strings},
	)
	frappe.db.commit()


def _count_all_members(doc_name):
	return cint(
		frappe.db.count(
			"Glific Group Contact",
			{"parent": doc_name, "parenttype": "Glific Group"},
		)
	)


def _count_synced_members(doc_name):
	return cint(
		frappe.db.count(
			"Glific Group Contact",
			{
				"parent": doc_name,
				"parenttype": "Glific Group",
				"status": "Synced",
			},
		)
	)


def _count_pending_members(doc_name):
	result = frappe.db.sql(
		"""
		SELECT COUNT(*) FROM `tabGlific Group Contact`
		WHERE parent = %(parent)s
		  AND parenttype = 'Glific Group'
		  AND COALESCE(status, 'Pending') = 'Pending'
		""",
		{"parent": doc_name},
	)
	return cint(result[0][0] if result else 0)


def _fetch_pending_members(doc_name, limit=SYNC_MEMBER_BATCH_LIMIT):
	return frappe.db.sql(
		"""
		SELECT name, user, mobile_no, contact_name, glific_contact_id, status
		FROM `tabGlific Group Contact`
		WHERE parent = %(parent)s
		  AND parenttype = 'Glific Group'
		  AND COALESCE(status, 'Pending') = 'Pending'
		ORDER BY
			CASE
				WHEN glific_contact_id IS NOT NULL AND glific_contact_id != '' THEN 0
				ELSE 1
			END,
			name
		LIMIT %(limit)s
		""",
		{"parent": doc_name, "limit": cint(limit)},
		as_dict=True,
	)


def _is_monthly_cohort_doc(doc_name):
	cohort_type = frappe.db.get_value("Glific Group", doc_name, "cohort_type")
	return cohort_type in MONTHLY_COHORT_TYPES


def _sync_member_batch(doc_name, group_id, batch_limit=SYNC_MEMBER_BATCH_LIMIT, skip_phone_lookup=False):
	"""Process up to batch_limit pending members; returns stats and whether more remain."""
	pending_rows = _fetch_pending_members(doc_name, limit=batch_limit)
	if not pending_rows:
		return {"processed": 0, "added": 0, "failed": 0, "has_more": False}

	settings = frappe.get_doc("Glific Settings")
	rows = [frappe._dict(r) for r in pending_rows]
	users = [row.user for row in rows if row.get("user")]
	wa_id_map = _prefetch_wa_id_map(users)

	rows_prepared = []
	failed_updates = []
	resolved_updates = []
	failed_count = 0

	for row in rows:
		contact_id, err = _resolve_contact_id_for_member(
			row, wa_id_map=wa_id_map, skip_phone_lookup=skip_phone_lookup
		)
		if err:
			failed_count += 1
			if row.name:
				failed_updates.append((row.name, err))
			continue

		row.glific_contact_id = contact_id
		if row.name:
			resolved_updates.append((row.name, contact_id))
		rows_prepared.append((row, int(contact_id)))

	if failed_updates:
		_bulk_mark_members_failed(failed_updates)
	if resolved_updates:
		_bulk_update_member_contact_ids(resolved_updates)

	added = 0
	if rows_prepared:
		added = _chunked_add_contacts_to_group(settings, group_id, rows_prepared)

	has_more = _count_pending_members(doc_name) > 0
	return {
		"processed": len(pending_rows),
		"added": added,
		"failed": failed_count,
		"has_more": has_more,
	}


def _glific_sync_job_id(doc_name, continuation=False):
	"""Stable id for new runs; unique id per chain link so RQ accepts re-enqueue."""
	base = f"sync_glific_group_{doc_name}"
	if continuation:
		return f"{base}_continue_{now_datetime().strftime('%Y%m%d%H%M%S%f')}"
	return base


def _enqueue_glific_member_batch(
	doc_name,
	user=None,
	job_name=None,
	continuation=False,
	job_key=None,
	thread_message_id=None,
	initiated_by=None,
):
	job_name = job_name or f"sync_glific_group_{doc_name}"
	frappe.enqueue(
		"solve_ninja.solve_ninja.doctype.glific_group.glific_group._sync_glific_members_batch_background",
		queue="long",
		timeout=3600,
		doc_name=doc_name,
		user=user,
		job_name=job_name,
		job_id=_glific_sync_job_id(doc_name, continuation=continuation),
		job_key=job_key or f"sync_{doc_name}",
		thread_message_id=thread_message_id,
		initiated_by=initiated_by,
	)


def _update_glific_sync_progress(doc_name):
	synced = _count_synced_members(doc_name)
	frappe.db.set_value(
		"Glific Group",
		doc_name,
		"glific_sync_members_done",
		synced,
		update_modified=True,
	)


def _sync_glific_members_batch_background(
	doc_name,
	user=None,
	job_name=None,
	job_key=None,
	thread_message_id=None,
	initiated_by=None,
):
	"""Background worker: sync one batch of members; re-enqueue if more pending."""
	frappe.set_user(user or "Administrator")
	job_name = job_name or f"sync_glific_group_{doc_name}"
	initiated_by = initiated_by or user or "Administrator"
	job_key = job_key or f"sync_{doc_name}"
	thread_message_id = thread_message_id or glific_job_thread_message_id(job_key)

	try:
		group_id = (frappe.db.get_value("Glific Group", doc_name, "glific_group_id") or "").strip()
		if not group_id:
			frappe.throw(_("Save the group first so Glific Group ID is set."))

		current_status = frappe.db.get_value("Glific Group", doc_name, "glific_sync_status")
		is_first_batch = current_status != "In Progress"
		if is_first_batch:
			total = _count_all_members(doc_name)
			frappe.db.set_value(
				"Glific Group",
				doc_name,
				{
					"glific_sync_status": "In Progress",
					"glific_sync_error": None,
					"glific_sync_members_total": total,
					"glific_sync_members_done": _count_synced_members(doc_name),
				},
				update_modified=True,
			)
			frappe.db.commit()
			send_glific_job_email(
				"member_sync",
				_("Started"),
				doc_name,
				initiated_by,
				job_key,
				thread_message_id=thread_message_id,
			)

		skip_phone = _is_monthly_cohort_doc(doc_name)
		result = _sync_member_batch(
			doc_name,
			group_id,
			batch_limit=SYNC_MEMBER_BATCH_LIMIT,
			skip_phone_lookup=skip_phone,
		)
		_update_glific_sync_progress(doc_name)
		frappe.db.commit()

		if result["has_more"]:
			_enqueue_glific_member_batch(
				doc_name,
				user=user,
				job_name=job_name,
				continuation=True,
				job_key=job_key,
				thread_message_id=thread_message_id,
				initiated_by=initiated_by,
			)
			return

		frappe.db.set_value(
			"Glific Group",
			doc_name,
			{
				"glific_sync_status": "Completed",
				"glific_sync_error": None,
				"glific_synced_at": now_datetime(),
				"glific_sync_members_done": _count_synced_members(doc_name),
			},
			update_modified=True,
		)
		frappe.db.commit()
		send_glific_job_email(
			"member_sync",
			_("Completed"),
			doc_name,
			initiated_by,
			job_key,
			thread_message_id=thread_message_id,
			in_reply_to=thread_message_id,
		)
	except Exception:
		frappe.log_error(title=_("Glific group member sync failed"))
		err = frappe.get_traceback(with_context=True)
		frappe.db.set_value(
			"Glific Group",
			doc_name,
			{"glific_sync_status": "Failed", "glific_sync_error": err[:2000]},
			update_modified=True,
		)
		frappe.db.commit()
		send_glific_job_email(
			"member_sync",
			_("Failed"),
			doc_name,
			initiated_by,
			job_key,
			thread_message_id=thread_message_id,
			in_reply_to=thread_message_id,
			extra_html=f"<pre>{frappe.utils.escape_html(err[:4000])}</pre>",
		)
		raise


def _unsynced_member_count(doc):
	return sum(
		1
		for row in doc.members
		if not (row.status == "Synced" and row.glific_contact_id)
	)


def _should_enqueue_sync(doc):
	if doc.get("cohort_type") in MONTHLY_COHORT_TYPES:
		return True
	return _unsynced_member_count(doc) > SYNC_ENQUEUE_THRESHOLD


def _sync_members_background(doc_name, user=None, job_key=None, thread_message_id=None, initiated_by=None):
	"""Background worker: chained batch sync for large cohorts."""
	_sync_glific_members_batch_background(
		doc_name,
		user=user,
		job_name=f"sync_glific_group_{doc_name}",
		job_key=job_key,
		thread_message_id=thread_message_id,
		initiated_by=initiated_by,
	)


def _glific_delete_job_id(doc_name, continuation=False):
	"""Stable id for new runs; unique id per chain link so RQ accepts re-enqueue."""
	base = f"delete_glific_group_{doc_name}"
	if continuation:
		return f"{base}_continue_{now_datetime().strftime('%Y%m%d%H%M%S%f')}"
	return base


def _enqueue_glific_delete_continuation(doc_name, user, job_key, thread_message_id):
	frappe.enqueue(
		"solve_ninja.solve_ninja.doctype.glific_group.glific_group._delete_glific_group_background",
		queue="long",
		timeout=3600,
		doc_name=doc_name,
		user=user,
		job_key=job_key,
		thread_message_id=thread_message_id,
		continuation=True,
		job_name=f"delete_glific_group_{doc_name}",
		job_id=_glific_delete_job_id(doc_name, continuation=True),
	)


def _delete_glific_group_from_glific(settings, gid):
	response = settings.delete_group(gid, timeout=DELETE_GROUP_TIMEOUT)
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


def _delete_glific_group_background(
	doc_name, user, job_key, thread_message_id, continuation=False
):
	frappe.set_user(user or "Administrator")
	initiated_by = user or "Administrator"

	try:
		gid = (frappe.db.get_value("Glific Group", doc_name, "glific_group_id") or "").strip()
		if gid:
			settings = frappe.get_doc("Glific Settings")
			if _count_synced_contact_ids(doc_name):
				contact_ids = _fetch_synced_contact_ids(
					doc_name, limit=DELETE_CONTACTS_BATCH_LIMIT
				)
				_chunked_remove_contacts_from_group(settings, gid, contact_ids)
				_bulk_clear_removed_contact_ids(doc_name, contact_ids)
				if _count_synced_contact_ids(doc_name):
					_enqueue_glific_delete_continuation(
						doc_name, user, job_key, thread_message_id
					)
					return
			_delete_glific_group_from_glific(settings, gid)

		frappe.delete_doc("Glific Group", doc_name, ignore_permissions=True)
		send_glific_job_email(
			"delete",
			_("Completed"),
			doc_name,
			initiated_by,
			job_key,
			thread_message_id=thread_message_id,
			in_reply_to=thread_message_id,
		)
	except Exception:
		frappe.log_error(title=_("Glific group delete failed"))
		err = frappe.get_traceback(with_context=True)
		send_glific_job_email(
			"delete",
			_("Failed"),
			doc_name,
			initiated_by,
			job_key,
			thread_message_id=thread_message_id,
			in_reply_to=thread_message_id,
			extra_html=f"<pre>{frappe.utils.escape_html(err[:4000])}</pre>",
		)
		raise


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
		rows_prepared = []
		failed_updates = []
		resolved_updates = []

		users_to_resolve = [
			row.user
			for row in self.members
			if not (row.status == "Synced" and row.glific_contact_id) and row.get("user")
		]
		wa_id_map = _prefetch_wa_id_map(users_to_resolve)

		for row in self.members:
			row.error_message = None

			if row.status == "Synced" and row.glific_contact_id:
				continue

			contact_id, err = _resolve_contact_id_for_member(row, wa_id_map=wa_id_map)
			if err:
				row.status = "Failed"
				row.error_message = err
				if row.name:
					failed_updates.append((row.name, err))
				continue

			row.glific_contact_id = contact_id
			if row.name:
				resolved_updates.append((row.name, contact_id))
			rows_prepared.append((row, int(contact_id)))

		if failed_updates:
			_bulk_mark_members_failed(failed_updates)
		if resolved_updates:
			_bulk_update_member_contact_ids(resolved_updates)

		if not rows_prepared:
			return {"message": _("No new members to sync"), "added": 0}

		total_added = _chunked_add_contacts_to_group(
			settings,
			self.glific_group_id,
			rows_prepared,
		)
		return {"message": _("Members synced"), "added": total_added}


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
	"""Queue background delete of Glific collection and ERPNext doc."""
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("delete")

	user = frappe.session.user or "Administrator"
	job_key = f"delete_{doc_name}"
	thread_message_id = glific_job_thread_message_id(job_key)

	send_glific_job_email(
		"delete",
		_("Queued"),
		doc_name,
		user,
		job_key,
		thread_message_id=thread_message_id,
	)

	frappe.enqueue(
		"solve_ninja.solve_ninja.doctype.glific_group.glific_group._delete_glific_group_background",
		queue="long",
		timeout=3600,
		doc_name=doc_name,
		user=user,
		job_key=job_key,
		thread_message_id=thread_message_id,
		job_name=f"delete_glific_group_{doc_name}",
		job_id=f"delete_glific_group_{doc_name}",
	)

	return {
		"queued": True,
		"message": _("Delete queued in background. You will receive an email when it completes."),
	}


@frappe.whitelist()
def sync_members_to_glific(doc_name):
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("write")
	if _should_enqueue_sync(doc):
		user = frappe.session.user or "Administrator"
		job_key = f"sync_{doc_name}"
		thread_message_id = glific_job_thread_message_id(job_key)
		frappe.db.set_value(
			"Glific Group",
			doc.name,
			{"glific_sync_status": "Queued", "glific_sync_error": None},
			update_modified=True,
		)
		_enqueue_glific_member_batch(
			doc_name,
			user=user,
			job_name=f"sync_glific_group_{doc_name}",
			job_key=job_key,
			thread_message_id=thread_message_id,
			initiated_by=user,
		)
		return {"message": _("Sync queued in background"), "queued": True}
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
			"glific_sync_members_done",
			"glific_sync_members_total",
			"creation",
			"modified",
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
