# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

"""Threaded email notifications for Glific cohort jobs (sync, delete)."""

from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

OPERATION_LABELS = {
	"member_sync": _("Glific member sync"),
	"delete": _("Glific delete"),
}


def glific_job_notifications_enabled() -> bool:
	settings = frappe.get_single("Solve Ninja Settings")
	return bool(
		cint(getattr(settings, "enable_monthly_cohort_notifications", 0))
		and (getattr(settings, "monthly_cohort_notification_email", None) or "").strip()
	)


def glific_job_thread_message_id(job_key: str) -> str:
	site = (frappe.local.site or "site").replace("@", "-")
	return f"glific-job.{job_key}@{site}"


def glific_job_email_subject(operation: str, doc_name: str) -> str:
	label = OPERATION_LABELS.get(operation, operation)
	return _("{0}: {1}").format(label, doc_name)


def get_glific_group_member_stats(doc_name: str) -> dict:
	synced = cint(
		frappe.db.count(
			"Glific Group Contact",
			{"parent": doc_name, "parenttype": "Glific Group", "status": "Synced"},
		)
	)
	failed = cint(
		frappe.db.count(
			"Glific Group Contact",
			{"parent": doc_name, "parenttype": "Glific Group", "status": "Failed"},
		)
	)
	pending = cint(
		frappe.db.sql(
			"""
			SELECT COUNT(*) FROM `tabGlific Group Contact`
			WHERE parent = %(parent)s
			  AND parenttype = 'Glific Group'
			  AND COALESCE(status, 'Pending') = 'Pending'
			""",
			{"parent": doc_name},
		)[0][0]
	)
	total = cint(
		frappe.db.count(
			"Glific Group Contact",
			{"parent": doc_name, "parenttype": "Glific Group"},
		)
	)
	return {
		"total": total,
		"synced": synced,
		"failed": failed,
		"pending": pending,
	}


def format_glific_job_stats(doc_name: str, initiated_by: str) -> str:
	meta = frappe.db.get_value(
		"Glific Group",
		doc_name,
		["group_name", "glific_group_id", "cohort_type"],
		as_dict=True,
	) or {}
	stats = get_glific_group_member_stats(doc_name)
	return (
		f"<p>{_('Doc')}: {frappe.utils.escape_html(doc_name)}</p>"
		f"<p>{_('Group name')}: {frappe.utils.escape_html(meta.get('group_name') or doc_name)}</p>"
		f"<p>{_('Cohort type')}: {frappe.utils.escape_html(meta.get('cohort_type') or '—')}</p>"
		f"<p>{_('Glific group id')}: {frappe.utils.escape_html(meta.get('glific_group_id') or '—')}</p>"
		f"<p>{_('Members total')}: {stats['total']}</p>"
		f"<p>{_('Synced')}: {stats['synced']} | {_('Failed')}: {stats['failed']} | {_('Pending')}: {stats['pending']}</p>"
		f"<p>{_('Initiated by')}: {frappe.utils.escape_html(initiated_by or 'Administrator')}</p>"
		f"<p>{_('Time')}: {now_datetime()}</p>"
	)


def send_glific_job_email(
	operation: str,
	event: str,
	doc_name: str,
	initiated_by: str,
	job_key: str,
	thread_message_id: Optional[str] = None,
	in_reply_to: Optional[str] = None,
	extra_html: str = "",
) -> Optional[str]:
	if not glific_job_notifications_enabled():
		return thread_message_id

	settings = frappe.get_single("Solve Ninja Settings")
	recipient = (settings.monthly_cohort_notification_email or "").strip()
	if not recipient:
		return thread_message_id

	msg_id = thread_message_id or glific_job_thread_message_id(job_key)
	subject = glific_job_email_subject(operation, doc_name)
	body = format_glific_job_stats(doc_name, initiated_by)
	if extra_html:
		body += extra_html
	message = f"<p><strong>{frappe.utils.escape_html(event)}</strong></p>{body}"

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
