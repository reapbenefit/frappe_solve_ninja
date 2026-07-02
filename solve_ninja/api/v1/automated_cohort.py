# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

"""Automated monthly cohort classification and Glific collection creation."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

from solve_ninja.solve_ninja.doctype.glific_group.glific_group import _glific_branch_errors

AUTOMATED_COHORT_BUCKETS = (
	"Dormants",
	"High Potentials",
	"Potentials",
	"Engaged Actors",
	"Change Champions",
	"Passive Actors",
	"Others Active",
)

UNCLASSIFIED = "Unclassified"

_COHORT_MONTH_NAMES = (
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

_COHORT_MONTHS = frozenset(_COHORT_MONTH_NAMES)


def _check_glific_group_permission():
	if not frappe.has_permission("Glific Group", "write", throw=False):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _parse_buckets(raw) -> List[str]:
	if raw is None:
		return []
	if isinstance(raw, str):
		raw = frappe.parse_json(raw)
	if not isinstance(raw, list):
		frappe.throw(_("cohort_buckets must be a list"))
	out = []
	for item in raw:
		b = str(item).strip()
		if b in AUTOMATED_COHORT_BUCKETS and b not in out:
			out.append(b)
	return out


def _validate_cohort_month_year(cohort_month: str, cohort_year) -> Tuple[str, int]:
	month = (cohort_month or "").strip()
	if month not in _COHORT_MONTHS:
		frappe.throw(_("Invalid cohort month."))
	try:
		year = int(cohort_year)
	except Exception:
		frappe.throw(_("Cohort year must be a whole number."))
	if year < 2000 or year > 2100:
		frappe.throw(_("Cohort year must be between 2000 and 2100."))
	return month, year


def current_cohort_period() -> Dict[str, Any]:
	"""Current calendar month/year in Frappe site timezone (nowdate)."""
	d = getdate(nowdate())
	return {
		"cohort_month": _COHORT_MONTH_NAMES[d.month - 1],
		"cohort_year": int(d.year),
	}


def _require_client_period_matches_server(
	cohort_month: str, cohort_year
) -> Tuple[str, int]:
	"""Validate client period matches server current period; return server values."""
	server = current_cohort_period()
	client_month, client_year = _validate_cohort_month_year(cohort_month, cohort_year)
	if (
		client_month != server["cohort_month"]
		or client_year != server["cohort_year"]
	):
		frappe.throw(
			_(
				"Month and year must match the current period ({0} {1}). "
				"Refresh the dialog and try again."
			).format(server["cohort_month"], server["cohort_year"])
		)
	return server["cohort_month"], server["cohort_year"]


@frappe.whitelist()
def get_monthly_cohort_period():
	"""Return current month/year for Monthly Cohorts dialog (site timezone)."""
	_check_glific_group_permission()
	return current_cohort_period()


def build_group_name(bucket: str, cohort_month: str, cohort_year: int) -> str:
	return f"{bucket} - {cohort_month} {cohort_year}"


def classify_user(
	contributions: Optional[int],
	last_active_date_bot,
	as_of: Optional[date] = None,
) -> str:
	"""Mutually exclusive bucket for one Ninja Profile row."""
	as_of = getdate(as_of or nowdate())

	if contributions is None and not last_active_date_bot:
		return UNCLASSIFIED

	contrib = 0 if contributions is None else cint(contributions, 0)
	last = getdate(last_active_date_bot) if last_active_date_bot else None

	d90 = add_days(as_of, -90)
	d180 = add_days(as_of, -180)

	active_90 = bool(last and last >= d90)
	active_91_180 = bool(last and last >= d180 and last < d90)

	if contrib >= 1:
		if active_90:
			return "Change Champions" if contrib >= 4 else "Engaged Actors"
		if active_91_180:
			return "Others Active"
		return "Passive Actors"

	if active_90:
		return "High Potentials"
	if active_91_180:
		return "Potentials"
	return "Dormants"


def classify_all_users(as_of: Optional[date] = None) -> Tuple[Dict[str, List[Dict]], Dict[str, int]]:
	"""Return grouped member rows and counts for all buckets including Unclassified."""
	as_of = getdate(as_of or nowdate())
	rows = frappe.db.sql(
		"""
		SELECT
			u.name AS user,
			u.full_name,
			u.mobile_no,
			np.contributions,
			np.last_active_date_bot,
			np.wa_id
		FROM `tabUser` u
		INNER JOIN `tabNinja Profile` np ON np.user = u.name
		WHERE u.enabled = 1
		""",
		as_dict=True,
	)

	grouped: Dict[str, List[Dict]] = {b: [] for b in AUTOMATED_COHORT_BUCKETS}
	grouped[UNCLASSIFIED] = []
	counts: Dict[str, int] = {b: 0 for b in AUTOMATED_COHORT_BUCKETS}
	counts[UNCLASSIFIED] = 0

	for row in rows:
		bucket = classify_user(row.contributions, row.last_active_date_bot, as_of)
		counts[bucket] = counts.get(bucket, 0) + 1
		if bucket == UNCLASSIFIED:
			grouped[UNCLASSIFIED].append(row)
		elif bucket in grouped:
			grouped[bucket].append(row)

	return grouped, counts


def filters_for_bucket(bucket: str, as_of: Optional[date] = None) -> Dict[str, Any]:
	"""Audit snapshot of filter fields equivalent to bucket definition."""
	as_of = getdate(as_of or nowdate())
	d90 = add_days(as_of, -90)
	d180 = add_days(as_of, -180)
	out: Dict[str, Any] = {
		"filter_wa_community": 0,
		"filter_contributions_min": None,
		"filter_contributions_max": None,
		"filter_last_active_date_from": None,
		"filter_last_active_date_to": None,
	}

	if bucket == "Dormants":
		out["filter_contributions_min"] = 0
		out["filter_contributions_max"] = 0
		out["filter_last_active_date_to"] = add_days(d180, -1)
	elif bucket == "High Potentials":
		out["filter_contributions_min"] = 0
		out["filter_contributions_max"] = 0
		out["filter_last_active_date_from"] = d90
	elif bucket == "Potentials":
		out["filter_contributions_min"] = 0
		out["filter_contributions_max"] = 0
		out["filter_last_active_date_from"] = d180
		out["filter_last_active_date_to"] = add_days(d90, -1)
	elif bucket == "Engaged Actors":
		out["filter_contributions_min"] = 1
		out["filter_contributions_max"] = 3
		out["filter_last_active_date_from"] = d90
	elif bucket == "Change Champions":
		out["filter_contributions_min"] = 4
		out["filter_last_active_date_from"] = d90
	elif bucket == "Others Active":
		out["filter_contributions_min"] = 1
		out["filter_last_active_date_from"] = d180
		out["filter_last_active_date_to"] = add_days(d90, -1)
	elif bucket == "Passive Actors":
		out["filter_contributions_min"] = 1
		out["filter_last_active_date_to"] = add_days(d180, -1)

	return out


def get_automated_cohort_doc_name(bucket: str, cohort_month: str, cohort_year: int) -> Optional[str]:
	group_name = build_group_name(bucket, cohort_month, cohort_year)
	return frappe.db.get_value("Glific Group", {"group_name": group_name}, "name")


def _parse_wa_id_as_glific_contact_id(wa_id) -> Optional[str]:
	if wa_id is None or str(wa_id).strip() == "":
		return None
	try:
		return str(int(str(wa_id).strip()))
	except (ValueError, TypeError):
		return None


def _member_rows_from_users(users: List[Dict]) -> List[Dict]:
	rows = []
	for u in users:
		uid = u.get("user")
		if not uid:
			continue
		rows.append(
			{
				"user": uid,
				"status": "Pending",
				"mobile_no": u.get("mobile_no") or None,
				"contact_name": (u.get("full_name") or "").strip(),
				"glific_contact_id": _parse_wa_id_as_glific_contact_id(u.get("wa_id")),
			}
		)
	return rows


def _apply_filters_to_doc(doc, bucket: str, as_of: date) -> None:
	f = filters_for_bucket(bucket, as_of)
	doc.filter_wa_community = 0
	doc.filter_contributions_min = f.get("filter_contributions_min")
	doc.filter_contributions_max = f.get("filter_contributions_max")
	doc.filter_last_active_date_from = f.get("filter_last_active_date_from")
	doc.filter_last_active_date_to = f.get("filter_last_active_date_to")


def _set_members_on_doc(doc, users: List[Dict]) -> int:
	doc.set("members", [])
	for row in _member_rows_from_users(users):
		doc.append("members", row)
	return len(doc.members)


def _find_glific_group_id_by_label(settings, label: str) -> Optional[str]:
	"""Paginate Glific groups until label matches."""
	label = (label or "").strip()
	if not label:
		return None
	offset = 0
	limit = 50
	while offset < 5000:
		resp = settings.list_groups(limit=limit, offset=offset)
		if not resp or resp.get("error"):
			break
		groups = ((resp.get("data") or {}).get("groups")) or []
		if not groups:
			break
		for g in groups:
			if (g.get("label") or "").strip() == label:
				return str(g.get("id"))
		if len(groups) < limit:
			break
		offset += limit
	return None


def _create_or_resolve_glific_group(doc) -> str:
	settings = frappe.get_doc("Glific Settings")
	label = doc.group_name
	existing = (doc.glific_group_id or "").strip()
	if existing:
		return existing

	found = _find_glific_group_id_by_label(settings, label)
	if found:
		return found

	desc = (doc.description or "").strip() or None
	response = settings.create_group(
		label=label,
		description=desc,
		is_restricted=bool(doc.is_restricted),
	)
	if not response or response.get("error"):
		frappe.throw(
			_("Glific request failed: {0}").format(
				(response or {}).get("error") or _("Unknown error")
			)
		)
	api_errors = _glific_branch_errors((response.get("data") or {}).get("createGroup") or {})
	if api_errors:
		# Label may already exist remotely
		found = _find_glific_group_id_by_label(settings, label)
		if found:
			return found
		frappe.throw(_("Failed to create group in Glific: {0}").format(api_errors))

	cg = (response.get("data") or {}).get("createGroup") or {}
	group = cg.get("group")
	if not group or not group.get("id"):
		frappe.throw(_("Glific did not return a group id."))
	return str(group["id"])


def _enqueue_glific_sync(doc_name: str) -> None:
	user = frappe.session.user or "Administrator"
	frappe.enqueue(
		"solve_ninja.api.v1.automated_cohort.sync_automated_cohort_to_glific",
		queue="long",
		timeout=3600,
		doc_name=doc_name,
		user=user,
		job_name=f"sync_automated_cohort_{doc_name}",
	)


def _monthly_cohort_job_key(month: str, year: int, buckets: List[str]) -> str:
	bucket_part = "-".join(b.replace(" ", "_") for b in sorted(buckets))
	return f"{year}-{month}-{bucket_part}"


def _monthly_cohort_job_name(month: str, year: int, buckets: List[str]) -> str:
	return f"create_monthly_cohorts_{_monthly_cohort_job_key(month, year, buckets)}"


def _monthly_cohort_email_subject(month: str, year: int, buckets: List[str]) -> str:
	bucket_label = ", ".join(buckets)
	return _("Monthly Cohort job: {0} {1} ({2})").format(month, year, bucket_label)


def _monthly_cohort_thread_message_id(job_key: str) -> str:
	site = (frappe.local.site or "site").replace("@", "-")
	return f"monthly-cohort.{job_key}@{site}"


def _monthly_cohort_notifications_enabled() -> bool:
	settings = frappe.get_single("Solve Ninja Settings")
	return bool(
		cint(getattr(settings, "enable_monthly_cohort_notifications", 0))
		and (getattr(settings, "monthly_cohort_notification_email", None) or "").strip()
	)


def _send_monthly_cohort_email(
	job_key: str,
	event: str,
	body_html: str,
	month: str,
	year: int,
	buckets: List[str],
	thread_message_id: Optional[str] = None,
	in_reply_to: Optional[str] = None,
) -> Optional[str]:
	if not _monthly_cohort_notifications_enabled():
		return thread_message_id

	settings = frappe.get_single("Solve Ninja Settings")
	recipient = (settings.monthly_cohort_notification_email or "").strip()
	if not recipient:
		return thread_message_id

	msg_id = thread_message_id or _monthly_cohort_thread_message_id(job_key)
	subject = _monthly_cohort_email_subject(month, year, buckets)
	message = f"<p><strong>{frappe.utils.escape_html(event)}</strong></p>{body_html}"

	kwargs = {
		"recipients": [recipient],
		"subject": subject,
		"message": message,
		"reference_doctype": "Solve Ninja Settings",
		"reference_name": "Solve Ninja Settings",
		"message_id": msg_id,
		"delayed": False,
	}
	if in_reply_to:
		kwargs["in_reply_to"] = in_reply_to

	frappe.sendmail(**kwargs)
	return msg_id


def _format_monthly_cohort_email_context(
	month: str,
	year: int,
	buckets: List[str],
	initiated_by: str,
) -> str:
	return (
		f"<p>{_('Period')}: {frappe.utils.escape_html(month)} {year}</p>"
		f"<p>{_('Buckets')}: {frappe.utils.escape_html(', '.join(buckets))}</p>"
		f"<p>{_('Initiated by')}: {frappe.utils.escape_html(initiated_by or 'Administrator')}</p>"
		f"<p>{_('Time')}: {now_datetime()}</p>"
	)


def _check_duplicate_buckets(
	buckets: List[str], month: str, year: int
) -> List[Dict[str, str]]:
	skipped = []
	for bucket in buckets:
		group_name = build_group_name(bucket, month, year)
		existing_name = get_automated_cohort_doc_name(bucket, month, year)
		if existing_name:
			skipped.append(
				{
					"bucket": bucket,
					"group_name": group_name,
					"existing_doc_name": existing_name,
				}
			)
	return skipped


def _run_monthly_automated_collections(
	buckets: List[str],
	month: str,
	year: int,
	confirm: bool,
	as_of: date,
	initiated_by: str,
) -> Dict[str, Any]:
	grouped, counts = classify_all_users(as_of)
	total_users = sum(counts.values())

	result: Dict[str, Any] = {
		"cohort_month": month,
		"cohort_year": year,
		"total_users_processed": total_users,
		"counts_by_bucket": counts,
		"created": [],
		"updated": [],
		"skipped_duplicates": [],
		"errors": [],
		"glific_jobs_queued": 0,
		"initiated_by": initiated_by,
	}

	for bucket in buckets:
		try:
			group_name = build_group_name(bucket, month, year)
			existing_name = get_automated_cohort_doc_name(bucket, month, year)

			if existing_name and not confirm:
				result["skipped_duplicates"].append(
					{
						"bucket": bucket,
						"group_name": group_name,
						"existing_doc_name": existing_name,
					}
				)
				continue

			users = grouped.get(bucket) or []
			doc_name, member_count, is_update = _upsert_automated_cohort_doc(
				bucket, month, year, users, as_of, existing_name=existing_name
			)
			frappe.db.commit()

			_enqueue_glific_sync(doc_name)
			result["glific_jobs_queued"] += 1

			entry = {
				"bucket": bucket,
				"doc_name": doc_name,
				"group_name": group_name,
				"member_count": member_count,
				"glific_sync_status": "Queued",
			}
			if is_update:
				result["updated"].append(entry)
			else:
				result["created"].append(entry)
		except Exception as e:
			frappe.db.rollback()
			result["errors"].append({"bucket": bucket, "message": str(e)})

	return result


def _format_monthly_cohort_result_summary(result: Dict[str, Any]) -> str:
	lines = [
		f"<p>{_('Created')}: {len(result.get('created') or [])}</p>",
		f"<p>{_('Updated')}: {len(result.get('updated') or [])}</p>",
		f"<p>{_('Glific sync jobs queued')}: {result.get('glific_jobs_queued') or 0}</p>",
		f"<p>{_('Total users processed')}: {result.get('total_users_processed') or 0}</p>",
	]
	if result.get("errors"):
		lines.append(f"<p><strong>{_('Errors')}</strong></p><ul>")
		for err in result["errors"]:
			lines.append(
				f"<li>{frappe.utils.escape_html(err.get('bucket', ''))}: "
				f"{frappe.utils.escape_html(err.get('message', ''))}</li>"
			)
		lines.append("</ul>")
	return "".join(lines)


def _create_monthly_automated_collections_background(
	buckets: List[str],
	month: str,
	year: int,
	confirm: int,
	user: str,
	job_key: str,
	thread_message_id: str,
) -> None:
	frappe.set_user(user or "Administrator")
	initiated_by = user or "Administrator"
	as_of = getdate(nowdate())

	try:
		result = _run_monthly_automated_collections(
			buckets, month, year, bool(cint(confirm)), as_of, initiated_by
		)
		body = _format_monthly_cohort_email_context(month, year, buckets, initiated_by)
		body += _format_monthly_cohort_result_summary(result)
		_send_monthly_cohort_email(
			job_key,
			_("Completed"),
			body,
			month,
			year,
			buckets,
			thread_message_id=thread_message_id,
			in_reply_to=thread_message_id,
		)
	except Exception:
		frappe.log_error(title=_("Monthly cohort creation failed"))
		err = frappe.get_traceback(with_context=True)
		body = _format_monthly_cohort_email_context(month, year, buckets, initiated_by)
		body += f"<pre>{frappe.utils.escape_html(err[:4000])}</pre>"
		_send_monthly_cohort_email(
			job_key,
			_("Failed"),
			body,
			month,
			year,
			buckets,
			thread_message_id=thread_message_id,
			in_reply_to=thread_message_id,
		)
		raise


def sync_automated_cohort_to_glific(doc_name: str, user: str = None) -> None:
	"""Background job: create Glific collection if needed, then chained batch member sync."""
	from solve_ninja.api.v1.glific_cohort_notifications import glific_job_thread_message_id
	from solve_ninja.solve_ninja.doctype.glific_group.glific_group import (
		_sync_glific_members_batch_background,
	)

	frappe.set_user(user or "Administrator")
	user = user or "Administrator"

	try:
		meta = frappe.db.get_value(
			"Glific Group",
			doc_name,
			["group_name", "glific_group_id", "description", "is_restricted"],
			as_dict=True,
		)
		if not meta:
			frappe.throw(_("Glific Group not found: {0}").format(doc_name))

		doc_stub = frappe._dict(meta)
		doc_stub.name = doc_name

		gid = _create_or_resolve_glific_group(doc_stub)
		if gid != (meta.glific_group_id or "").strip():
			frappe.db.set_value(
				"Glific Group",
				doc_name,
				"glific_group_id",
				gid,
				update_modified=False,
			)

		job_key = f"sync_{doc_name}"
		thread_message_id = glific_job_thread_message_id(job_key)
		_sync_glific_members_batch_background(
			doc_name,
			user=user,
			job_name=f"sync_automated_cohort_{doc_name}",
			job_key=job_key,
			thread_message_id=thread_message_id,
			initiated_by=user,
		)
	except Exception:
		frappe.log_error(title=_("Automated cohort Glific sync failed"))
		err = frappe.get_traceback(with_context=True)
		frappe.db.set_value(
			"Glific Group",
			doc_name,
			{"glific_sync_status": "Failed", "glific_sync_error": err[:2000]},
			update_modified=True,
		)
		frappe.db.commit()
		raise


def _upsert_automated_cohort_doc(
	bucket: str,
	cohort_month: str,
	cohort_year: int,
	users: List[Dict],
	as_of: date,
	existing_name: Optional[str] = None,
) -> Tuple[str, int, bool]:
	"""Create or update Glific Group. Returns (doc_name, member_count, is_update)."""
	group_name = build_group_name(bucket, cohort_month, cohort_year)
	is_update = bool(existing_name)

	if is_update:
		doc = frappe.get_doc("Glific Group", existing_name)
		doc.group_name = group_name
	else:
		doc = frappe.new_doc("Glific Group")
		doc.group_name = group_name

	doc.cohort_type = "Monthly Cohort"
	doc.automated_cohort_bucket = bucket
	doc.cohort_month = cohort_month
	doc.cohort_year = cohort_year
	doc.audience_mode = "Filtered"
	doc.glific_sync_status = "Queued"
	doc.glific_sync_error = None
	_apply_filters_to_doc(doc, bucket, as_of)
	member_count = _set_members_on_doc(doc, users)
	doc.save()
	return doc.name, member_count, is_update


@frappe.whitelist()
def create_monthly_automated_collections(
	cohort_buckets=None,
	cohort_month=None,
	cohort_year=None,
	confirm_overwrite=None,
):
	"""
	Validate input, optionally check duplicates, enqueue background classification + cohort creation.
	"""
	_check_glific_group_permission()

	buckets = _parse_buckets(cohort_buckets)
	if not buckets:
		frappe.throw(_("Select at least one monthly cohort bucket."))

	month, year = _require_client_period_matches_server(cohort_month, cohort_year)
	confirm = cint(confirm_overwrite, 0)
	user = frappe.session.user or "Administrator"

	if not confirm:
		skipped = _check_duplicate_buckets(buckets, month, year)
		if skipped:
			return {
				"queued": False,
				"cohort_month": month,
				"cohort_year": year,
				"skipped_duplicates": skipped,
			}

	job_key = _monthly_cohort_job_key(month, year, buckets)
	thread_message_id = _monthly_cohort_thread_message_id(job_key)

	body = _format_monthly_cohort_email_context(month, year, buckets, user)
	body += f"<p>{_('The job will classify users, create cohort records, and queue Glific sync.')}</p>"
	_send_monthly_cohort_email(
		job_key,
		_("Queued"),
		body,
		month,
		year,
		buckets,
		thread_message_id=thread_message_id,
	)

	frappe.enqueue(
		"solve_ninja.api.v1.automated_cohort._create_monthly_automated_collections_background",
		queue="long",
		timeout=3600,
		buckets=buckets,
		month=month,
		year=year,
		confirm=confirm,
		user=user,
		job_key=job_key,
		thread_message_id=thread_message_id,
		job_name=_monthly_cohort_job_name(month, year, buckets),
	)

	return {
		"queued": True,
		"message": _("Monthly cohort creation queued in background."),
		"cohort_month": month,
		"cohort_year": year,
		"buckets": buckets,
		"job_key": job_key,
	}
