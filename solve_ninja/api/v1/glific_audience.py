# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

"""Filtered audience queries, preview token, and Glific collection creation for Glific Group."""

import hashlib
import json
import secrets
from typing import Any, Dict, List, Optional, Set

import frappe
from frappe import _
from frappe.query_builder import DocType, Order
from frappe.utils import get_datetime, getdate, now_datetime
from frappe.query_builder.functions import Count

from solve_ninja.services.glific_manager import GlificManager
from solve_ninja.solve_ninja.doctype.glific_group.glific_group import ADD_CONTACTS_CHUNK
from solve_ninja.utils import validate_and_normalize_mobile

PREVIEW_CACHE_PREFIX = "glific_group_preview:"
PREVIEW_TTL_SEC = 3600


def _coerce_multiselect_link_list(val: Any, preferred_key: Optional[str] = None) -> List[str]:
	"""Desk / JSON may send plain names, {\"key\": \"name\"}, or table rows."""
	if val is None:
		return []
	if isinstance(val, str):
		val = val.strip()
		if not val:
			return []
		try:
			val = json.loads(val)
		except Exception:
			return sorted({val})

	out = []
	if isinstance(val, dict):
		if preferred_key and val.get(preferred_key):
			out.append(str(val[preferred_key]).strip())
		else:
			for v in val.values():
				if isinstance(v, str) and v.strip():
					out.append(v.strip())
		return sorted(set(out))

	if not isinstance(val, list):
		return []

	for item in val:
		if preferred_key:
			cell = getattr(item, preferred_key, None)
			if cell is None and isinstance(item, dict):
				cell = item.get(preferred_key)
			if cell:
				out.append(str(cell).strip())
				continue

		if isinstance(item, dict):
			for v in item.values():
				if isinstance(v, str) and v.strip():
					out.append(v.strip())
					break
		elif isinstance(item, (str, int, float)):
			s = str(item).strip()
			if s:
				out.append(s)
	return sorted(set(x for x in out if x))


def _sorted_wa_groups_from_doc(doc) -> List[str]:
	rows = doc.get("filter_glific_wa_groups") if hasattr(doc, "get") else None
	if rows is None:
		rows = getattr(doc, "filter_glific_wa_groups", None) or []
	return _coerce_multiselect_link_list(rows, "glific_wa_group")


def _sorted_cities_from_doc(doc) -> List[str]:
	rows = doc.get("filter_cities") if hasattr(doc, "get") else None
	if rows is None:
		rows = getattr(doc, "filter_cities", None) or []
	return _coerce_multiselect_link_list(rows, "samaaja_city")


def filters_from_doc(doc) -> Dict[str, Any]:
	return {
		"filter_wa_community": cint(doc.get("filter_wa_community")),
		"filter_glific_wa_groups": _sorted_wa_groups_from_doc(doc),
		"filter_wa_community_glific_group_id": (doc.get("filter_wa_community_glific_group_id") or "").strip(),
		"filter_contributions_min": doc.get("filter_contributions_min"),
		"filter_contributions_max": doc.get("filter_contributions_max"),
		"filter_city": doc.get("filter_city"),
		"filter_cities": _sorted_cities_from_doc(doc),
		"filter_gender": doc.get("filter_gender"),
		"filter_acquisition_source_unique_id": (doc.get("filter_acquisition_source_unique_id") or "").strip(),
		"filter_user_organization": doc.get("filter_user_organization"),
		"filter_last_action_date_from": doc.get("filter_last_action_date_from"),
		"filter_last_action_date_to": doc.get("filter_last_action_date_to"),
		"filter_last_active_date_from": doc.get("filter_last_active_date_from"),
		"filter_last_active_date_to": doc.get("filter_last_active_date_to"),
	}


def filters_from_form_dict(form: Dict[str, Any]) -> Dict[str, Any]:
	"""Desk modal / JSON: same normalized shape as ``filters_from_doc``."""
	wa_legacy = (form.get("filter_wa_community_glific_group_id") or "").strip()
	wa_docs = (
		_coerce_multiselect_link_list(form.get("filter_glific_wa_groups"), "glific_wa_group") if form else []
	)

	return {
		"filter_wa_community": cint(form.get("filter_wa_community")),
		"filter_glific_wa_groups": wa_docs,
		"filter_wa_community_glific_group_id": wa_legacy,
		"filter_contributions_min": form.get("filter_contributions_min"),
		"filter_contributions_max": form.get("filter_contributions_max"),
		"filter_city": form.get("filter_city"),
		"filter_cities": _coerce_multiselect_link_list(form.get("filter_cities"), "samaaja_city"),
		"filter_gender": form.get("filter_gender"),
		"filter_acquisition_source_unique_id": (form.get("filter_acquisition_source_unique_id") or "").strip(),
		"filter_user_organization": form.get("filter_user_organization"),
		"filter_last_action_date_from": form.get("filter_last_action_date_from"),
		"filter_last_action_date_to": form.get("filter_last_action_date_to"),
		"filter_last_active_date_from": form.get("filter_last_active_date_from"),
		"filter_last_active_date_to": form.get("filter_last_active_date_to"),
	}


def cint(v, default=0):
	if v is None or v == "":
		return default
	try:
		return int(v)
	except Exception:
		return default


def _parse_filter_date(val) -> Optional[str]:
	if val is None or val == "":
		return None
	try:
		return str(getdate(val))
	except Exception:
		return None


def _validate_date_ranges(filters: Dict[str, Any]) -> None:
	pairs = (
		(
			_("Last action date"),
			_parse_filter_date(filters.get("filter_last_action_date_from")),
			_parse_filter_date(filters.get("filter_last_action_date_to")),
		),
		(
			_("Last active date"),
			_parse_filter_date(filters.get("filter_last_active_date_from")),
			_parse_filter_date(filters.get("filter_last_active_date_to")),
		),
	)
	for label, from_d, to_d in pairs:
		if from_d and to_d and from_d > to_d:
			frappe.throw(_("{0}: start date must be on or before end date.").format(label))


def filters_have_any_criteria(filters: Dict[str, Any]) -> bool:
	wa_groups = filters.get("filter_glific_wa_groups") or []
	wa_legacy = (filters.get("filter_wa_community_glific_group_id") or "").strip()
	if filters.get("filter_wa_community") and (wa_groups or wa_legacy):
		return True
	if filters.get("filter_contributions_min") is not None:
		return True
	if filters.get("filter_contributions_max") is not None:
		return True
	if filters.get("filter_cities"):
		return True
	if filters.get("filter_city"):
		return True
	if filters.get("filter_gender"):
		return True
	if filters.get("filter_acquisition_source_unique_id"):
		return True
	if filters.get("filter_user_organization"):
		return True
	if _parse_filter_date(filters.get("filter_last_action_date_from")):
		return True
	if _parse_filter_date(filters.get("filter_last_action_date_to")):
		return True
	if _parse_filter_date(filters.get("filter_last_active_date_from")):
		return True
	if _parse_filter_date(filters.get("filter_last_active_date_to")):
		return True
	return False


def _needs_wa_user_restriction(filters: Dict[str, Any]) -> bool:
	return bool(filters.get("filter_wa_community")) and bool(
		(filters.get("filter_glific_wa_groups") or [])
		or ((filters.get("filter_wa_community_glific_group_id") or "").strip())
	)


def _resolve_wa_user_union_for_filters(filters: Dict[str, Any]) -> Set[str]:
	"""Intersection of Ninja users with WA filter; union Glific memberships across chosen groups."""
	names: Set[str] = set()
	for docname in filters.get("filter_glific_wa_groups") or []:
		raw_gid = frappe.db.get_value("Glific WA Group", docname, "glific_group_id")
		if raw_gid is None:
			continue
		names |= _resolve_wa_community_user_names(str(raw_gid).strip())

	legacy = (filters.get("filter_wa_community_glific_group_id") or "").strip()
	if legacy:
		names |= _resolve_wa_community_user_names(legacy)
	return names


def _filter_hash(filters: Dict[str, Any]) -> str:
	payload = json.dumps(filters, sort_keys=True, default=str)
	return hashlib.sha256(payload.encode()).hexdigest()


def _resolve_wa_community_user_names(glific_wa_group_id: str) -> Set[str]:
	"""Phones of Glific contacts in a WhatsApp group -> User names."""
	from solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group import (
		fetch_all_contacts_in_wa_group,
	)

	wa_group_id = str(glific_wa_group_id or "").strip()
	if not wa_group_id:
		return set()

	settings = frappe.get_doc("Glific Settings")
	contacts, err = fetch_all_contacts_in_wa_group(settings, wa_group_id)
	if err:
		return set()

	names: Set[str] = set()
	for c in contacts:
		phone = (c.get("phone") or "").strip()
		if not phone:
			continue
		try:
			norm = validate_and_normalize_mobile(phone)
		except Exception:
			continue
		user = frappe.db.get_value("User", {"mobile_no": norm}, "name")
		if user:
			names.add(user)

	return names


def _where_users_in_set(q, User, names: Set[str]):
	"""Restrict query to users in ``names`` (chunked IN for large groups)."""
	if not names:
		return q.where(User.name == "__wa_glific_filter_no_members__")
	lst = list(names)
	chunk = 500
	if len(lst) <= chunk:
		return q.where(User.name.isin(lst))
	crit = User.name.isin(lst[:chunk])
	for i in range(chunk, len(lst), chunk):
		crit = crit | User.name.isin(lst[i : i + chunk])
	return q.where(crit)


def _build_match_query(require_glific_wa_id: bool):
	User = DocType("User")
	NP = DocType("Ninja Profile")
	UM = DocType("User Metadata")

	q = (
		frappe.qb.from_(User)
		.inner_join(NP)
		.on(User.name == NP.user)
		.left_join(UM)
		.on(User.name == UM.user)
		.where(User.enabled == 1)
	)
	if require_glific_wa_id:
		q = q.where(NP.wa_id.isnotnull()).where(NP.wa_id != "")
	return q, User, NP, UM


def _apply_filters(
	q,
	User,
	NP,
	UM,
	filters: Dict[str, Any],
	wa_user_names: Optional[Set[str]] = None,
):
	if filters.get("filter_contributions_min") is not None:
		q = q.where(NP.contributions >= cint(filters["filter_contributions_min"], 0))
	if filters.get("filter_contributions_max") is not None:
		q = q.where(NP.contributions <= cint(filters["filter_contributions_max"], 0))
	cities = filters.get("filter_cities") or []
	if filters.get("filter_city") and not cities:
		cities = [filters["filter_city"]]
	if cities:
		q = q.where(UM.city.isin(cities))
	if filters.get("filter_gender"):
		q = q.where(User.gender == filters["filter_gender"])
	if filters.get("filter_acquisition_source_unique_id"):
		q = q.where(NP.acquisition_source_unique_id == filters["filter_acquisition_source_unique_id"])
	if filters.get("filter_user_organization"):
		q = q.where(UM.org_id == filters["filter_user_organization"])

	action_from = _parse_filter_date(filters.get("filter_last_action_date_from"))
	action_to = _parse_filter_date(filters.get("filter_last_action_date_to"))
	if action_from:
		q = q.where(NP.last_action_date >= get_datetime(f"{action_from} 00:00:00"))
	if action_to:
		q = q.where(NP.last_action_date <= get_datetime(f"{action_to} 23:59:59"))

	active_from = _parse_filter_date(filters.get("filter_last_active_date_from"))
	active_to = _parse_filter_date(filters.get("filter_last_active_date_to"))
	if active_from:
		q = q.where(NP.last_active_date_bot >= active_from)
	if active_to:
		q = q.where(NP.last_active_date_bot <= active_to)

	if _needs_wa_user_restriction(filters):
		q = _where_users_in_set(q, User, wa_user_names or set())
	return q


def audience_match_count(filters: Dict[str, Any], require_glific_wa_id: bool = False) -> int:
	_validate_date_ranges(filters)
	wa_user_names = None
	if _needs_wa_user_restriction(filters):
		wa_user_names = _resolve_wa_user_union_for_filters(filters)

	q, User, NP, UM = _build_match_query(require_glific_wa_id)
	q = _apply_filters(q, User, NP, UM, filters, wa_user_names=wa_user_names)
	row = q.select(Count(User.name).as_("cnt")).run(as_dict=True)
	if not row:
		return 0
	return row[0].get("cnt") or 0


def audience_match_rows(
	filters: Dict[str, Any],
	limit: int = 50,
	offset: int = 0,
	require_glific_wa_id: bool = False,
) -> List[Dict[str, Any]]:
	_validate_date_ranges(filters)
	wa_user_names = None
	if _needs_wa_user_restriction(filters):
		wa_user_names = _resolve_wa_user_union_for_filters(filters)

	q, User, NP, UM = _build_match_query(require_glific_wa_id)
	q = _apply_filters(q, User, NP, UM, filters, wa_user_names=wa_user_names)
	q = q.select(
		User.name.as_("user"),
		User.full_name,
		User.mobile_no,
		User.gender,
		NP.contributions,
		NP.wa_id,
		NP.acquisition_source_unique_id,
		UM.city,
		UM.org_id,
	).orderby(User.full_name, order=Order.asc).limit(limit).offset(offset)
	return q.run(as_dict=True)


@frappe.whitelist()
def search_audience_standalone(filters_json=None, start=0, page_length=50):
	"""Same behaviour as ``search_users_for_glific_group`` (filters_json-only) for Manage Cohort Desk page."""
	return search_users_for_glific_group(
		filters_json=filters_json, start=start, page_length=page_length
	)


@frappe.whitelist()
def search_users_for_glific_group(
	filters_json=None,
	start=0,
	page_length=50,
):
	"""Paginated user list for filter modal (AND filters)."""
	doc_perm = frappe.has_permission("Glific Group", "write", throw=False)
	if not doc_perm:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	start, page_length = cint(start, 0), min(cint(page_length, 50), 100)
	filters = json.loads(filters_json) if filters_json else {}
	filters = filters_from_form_dict(filters)
	if not filters_have_any_criteria(filters):
		frappe.throw(_("Select at least one filter."))
	total = audience_match_count(filters, require_glific_wa_id=False)
	rows = audience_match_rows(filters, limit=page_length, offset=start, require_glific_wa_id=False)
	return {"total_count": total, "users": rows, "start": start, "page_length": page_length}


@frappe.whitelist()
def add_all_filtered_audience_to_members(doc_name: str = None):
	"""Append one child row per user matching saved cohort filters (batched scan). Duplicates skipped by User or Mobile No."""
	doc_name = doc_name or frappe.form_dict.get("doc_name")
	if not doc_name:
		frappe.throw(_("doc_name required"))
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("write")
	if doc.get("audience_mode") != "Filtered":
		frappe.throw(_("Audience mode must be Filtered."))

	filters = filters_from_doc(doc)
	if not filters_have_any_criteria(filters):
		frappe.throw(_("Select at least one filter before adding members."))

	existing_users: Set[str] = {str(r.user) for r in doc.members if r.get("user")}
	existing_mobile: Set[str] = {
		str(r.mobile_no).strip()
		for r in doc.members
		if str(r.mobile_no or "").strip()
	}

	added = 0
	offset = 0
	batch_size = 500

	while True:
		rows = audience_match_rows(
			filters, limit=batch_size, offset=offset, require_glific_wa_id=False
		)
		if not rows:
			break
		for row in rows:
			uid = row.get("user")
			if not uid:
				continue
			if uid in existing_users:
				continue
			mobile = row.get("mobile_no") or ""
			mob = str(mobile).strip()
			if mob and mob in existing_mobile:
				continue
			doc.append(
				"members",
				{
					"user": uid,
					"status": "Pending",
					"mobile_no": mobile if mobile else None,
					"contact_name": (row.get("full_name") or "").strip(),
				},
			)
			existing_users.add(uid)
			if mob:
				existing_mobile.add(mob)
			added += 1
		offset += batch_size

	if added:
		doc.save()
	else:
		return {"added": 0, "message": _("No new members to add (all matches were already listed).")}
	return {"added": added, "message": _("Added {0} member row(s).").format(added)}


@frappe.whitelist()
def preview_audience(doc_name: str):
	doc_name = doc_name or frappe.form_dict.get("doc_name")
	if not doc_name:
		frappe.throw(_("doc_name required"))
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("write")
	if doc.get("audience_mode") != "Filtered":
		frappe.throw(_("Switch Audience Mode to Filtered."))
	filters = filters_from_doc(doc)
	if not filters_have_any_criteria(filters):
		frappe.throw(_("Select at least one filter before preview."))

	count_all = audience_match_count(filters, require_glific_wa_id=False)
	count_glific = audience_match_count(filters, require_glific_wa_id=True)
	sample = audience_match_rows(
		filters, limit=20, offset=0, require_glific_wa_id=False
	)
	fh = _filter_hash(filters)
	token = secrets.token_urlsafe(24)
	cache_payload = {
		"doc_name": doc.name,
		"filter_hash": fh,
		"user": frappe.session.user,
		"count_all": count_all,
		"count_glific": count_glific,
	}
	frappe.cache().set_value(
		f"{PREVIEW_CACHE_PREFIX}{token}",
		json.dumps(cache_payload),
		expires_in_sec=PREVIEW_TTL_SEC,
	)

	frappe.db.set_value(
		"Glific Group",
		doc.name,
		{
			"preview_token": token,
			"preview_match_count": count_all,
			"preview_sample_json": json.dumps(sample, default=str),
			"preview_generated_at": now_datetime(),
		},
	)

	return {
		"preview_token": token,
		"filter_hash": fh,
		"count": count_all,
		"count_glific_eligible": count_glific,
		"sample": sample,
	}


def _validate_preview_token(doc, preview_token: Optional[str]):
	if not preview_token:
		frappe.throw(_("Save the Preview Token from Preview step (run Preview again)."))
	raw = frappe.cache().get_value(f"{PREVIEW_CACHE_PREFIX}{preview_token}")
	if not raw:
		frappe.throw(_("Preview expired or missing. Run Preview again."))
	try:
		cache_payload = json.loads(raw)
	except Exception:
		frappe.throw(_("Invalid preview state. Run Preview again."))
	if cache_payload.get("doc_name") != doc.name:
		frappe.throw(_("Preview token does not match this document."))
	if cache_payload.get("user") != frappe.session.user:
		frappe.throw(_("Preview was generated by another user."))
	filters = filters_from_doc(doc)
	if _filter_hash(filters) != cache_payload.get("filter_hash"):
		frappe.throw(_("Filters changed after preview. Run Preview again."))
	return cache_payload


@frappe.whitelist()
def create_filtered_glific_collection(doc_name: str, preview_token: str = None):
	doc_name = doc_name or frappe.form_dict.get("doc_name")
	doc = frappe.get_doc("Glific Group", doc_name)
	doc.check_permission("write")
	if doc.get("audience_mode") != "Filtered":
		frappe.throw(_("Audience mode must be Filtered."))

	filters = filters_from_doc(doc)
	if not filters_have_any_criteria(filters):
		frappe.throw(_("Select at least one filter before creating collection."))

	if doc.glific_group_id:
		frappe.throw(_("Glific collection already exists."))

	settings = frappe.get_doc("Glific Settings")
	desc = (doc.description or "").strip() or None
	response = settings.create_group(
		label=doc.group_name,
		description=desc,
		is_restricted=bool(doc.is_restricted),
	)
	from solve_ninja.solve_ninja.doctype.glific_group.glific_group import _glific_branch_errors

	if not response or response.get("error"):
		frappe.throw(
			_("Glific request failed: {0}").format(
				(response or {}).get("error") or _("Unknown error")
			)
		)
	api_errors = _glific_branch_errors((response.get("data") or {}).get("createGroup") or {})
	if api_errors:
		frappe.throw(_("Failed to create group in Glific: {0}").format(api_errors))
	cg = (response.get("data") or {}).get("createGroup") or {}
	group = cg.get("group")
	if not group or not group.get("id"):
		frappe.throw(_("Glific did not return a group id."))
	gid = str(group["id"])
	doc.db_set("glific_group_id", gid, update_modified=False)

	return {
		"message": _(
			"Glific collection created. Add members and use Sync Members to push contacts."
		),
		"glific_group_id": gid,
		"contacts_synced": 0,
	}


def _bulk_add_filtered_contacts_to_glific(doc, settings, filters: Dict[str, Any], glific_group_id: str) -> int:
	"""Resolve Glific contact ids for matching users (wa_id or phone) and updateGroupContacts in chunks."""
	add_ids: List[int] = []
	offset = 0
	batch = 500
	while True:
		rows = audience_match_rows(
			filters, limit=batch, offset=offset, require_glific_wa_id=False
		)
		if not rows:
			break
		for row in rows:
			cid = None
			if row.get("wa_id"):
				try:
					cid = int(str(row["wa_id"]).strip())
				except Exception:
					cid = None
			if not cid and row.get("mobile_no"):
				try:
					phone = validate_and_normalize_mobile(row["mobile_no"])
					cid = GlificManager.get_contact_id_by_phone(phone)
					if cid:
						cid = int(str(cid))
				except Exception:
					cid = None
			if cid and cid not in add_ids:
				add_ids.append(cid)
		offset += batch

	if not add_ids:
		return 0

	total_updated = 0
	for i in range(0, len(add_ids), ADD_CONTACTS_CHUNK):
		chunk = add_ids[i : i + ADD_CONTACTS_CHUNK]
		response = settings.update_group_contacts(
			glific_group_id,
			add_contact_ids=chunk,
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
		from solve_ninja.solve_ninja.doctype.glific_group.glific_group import _glific_branch_errors

		api_errors = _glific_branch_errors(
			(response.get("data") or {}).get("updateGroupContacts") or {}
		)
		if api_errors:
			frappe.throw(_("Failed to add contacts: {0}").format(api_errors))
		total_updated += len(chunk)

	return total_updated

