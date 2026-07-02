# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from solve_ninja.doc_events.events import update_ninja_profile


REASSIGNMENTS = [
	("Events", "user"),
	("Energy Point Log", "user"),
	("Solve Event Participation", "user"),
	("Solve Event Registration", "user"),
	("User Review", "user"),
	("Program Participation", "user"),
	("Chat History", "user"),
	("Chat Session Archive Message", "user"),
	("Glific WA Group Member", "user"),
	("Glific Group Contact", "user"),
	("Mentorship Request", "mentee_user"),
	("Workflow Action", "user"),
	("Workflow Action", "completed_by"),
	("Success Story", "user"),
]

USER_FILL_FIELDS = [
	"first_name",
	"last_name",
	"full_name",
	"user_image",
	"bio",
	"location",
	"birth_date",
]

USER_METADATA_FILL_FIELDS = [
	"summary",
	"story",
	"testimonial",
	"media",
	"pincode",
	"city",
	"state",
	"partner",
	"org_id",
	"year_of_birth",
	"active_since",
	"profile_badges",
	"verified_by",
	"email_id",
	"is_mentor",
	"mentor_expertise",
	"mentor_status",
	"mentor_quote",
	"is_city_chapter_lead",
	"chapter_lead_achivement",
	"is_ninja_in_focus",
]

NINJA_PROFILE_FILL_FIELDS = [
	"acquisition_source_category",
	"acquisition_source_subcategory",
	"acquisition_source_name",
	"acquisition_source_unique_id",
	"wa_id",
	"last_active_date_bot",
]

PROTECTED_USER_FIELDS = {"email", "mobile_no", "username", "name", "enabled"}


@frappe.whitelist()
def get_merge_preview(source_user, target_user):
	"""Return counts and profile fill preview before merging source into target."""
	_validate_merge_users(source_user, target_user)

	source_user = frappe.db.get_value("User", source_user, ["name", "full_name", "username", "enabled"], as_dict=True)
	target_user = frappe.db.get_value("User", target_user, ["name", "full_name", "username", "enabled"], as_dict=True)

	reassignments = _get_reassignment_counts(source_user.name, target_user.name)
	badge_summary = _get_badge_merge_summary(source_user.name, target_user.name)
	ninja_profile = _get_ninja_profile_preview(source_user.name, target_user.name)
	profile_fields = _get_profile_fill_preview(source_user.name, target_user.name)

	return {
		"source_user": source_user,
		"target_user": target_user,
		"reassignments": reassignments,
		"badge_summary": badge_summary,
		"ninja_profile": ninja_profile,
		"profile_fields": profile_fields,
		"user_event_stats_summary": _get_user_event_stats_summary(source_user.name, target_user.name),
	}


@frappe.whitelist()
def merge_users(source_user, target_user):
	"""Merge source user's activity into target, fill empty profile fields, disable source."""
	_validate_merge_users(source_user, target_user)

	source_user = source_user.strip()
	target_user = target_user.strip()

	try:
		reassignments = _reassign_records(source_user, target_user)
		badge_summary = _merge_user_badges(source_user, target_user)
		user_event_stats_summary = _merge_user_event_stats(source_user, target_user)
		_reassign_mentor_metadata(source_user, target_user)
		_merge_profile_documents(source_user, target_user)
		update_ninja_profile(target_user)
		_disable_source_user(source_user)
		_add_merge_comments(source_user, target_user)
		frappe.db.commit()

		return {
			"success": True,
			"message": _("User {0} merged into {1} and disabled.").format(source_user, target_user),
			"reassignments": reassignments,
			"badge_summary": badge_summary,
			"user_event_stats_summary": user_event_stats_summary,
		}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "User Merge Failed")
		raise


def _ensure_system_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Manager can merge users."), frappe.PermissionError)


def _validate_merge_users(source_user, target_user):
	_ensure_system_manager()

	if not source_user or not target_user:
		frappe.throw(_("Both source and target users are required."))

	source_user = source_user.strip()
	target_user = target_user.strip()

	if source_user == target_user:
		frappe.throw(_("Source and target users must be different."))

	if not frappe.db.exists("User", source_user):
		frappe.throw(_("Source user {0} does not exist.").format(source_user))

	if not frappe.db.exists("User", target_user):
		frappe.throw(_("Target user {0} does not exist.").format(target_user))

	if source_user in ("Administrator", "Guest"):
		frappe.throw(_("Cannot merge system user {0}.").format(source_user))


def _doctype_exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))


def _is_empty(value):
	if value is None:
		return True
	if isinstance(value, str):
		return not value.strip()
	return False


def _get_reassignment_counts(source_user, target_user):
	counts = {}
	for doctype, fieldname in REASSIGNMENTS:
		if not _doctype_exists(doctype):
			continue
		key = f"{doctype}.{fieldname}"
		counts[key] = frappe.db.count(doctype, {fieldname: source_user})
	return counts


def _get_badge_merge_summary(source_user, target_user):
	if not _doctype_exists("User badge"):
		return {"badges_to_reassign": 0, "badges_to_sum": 0, "total_source_badges": 0}

	source_badges = frappe.get_all(
		"User badge",
		filters={"user": source_user},
		fields=["name", "badge", "badge_count", "active"],
	)
	badges_to_reassign = 0
	badges_to_sum = 0

	for badge in source_badges:
		target_row = frappe.db.exists("User badge", {"user": target_user, "badge": badge.badge})
		if target_row:
			badges_to_sum += 1
		else:
			badges_to_reassign += 1

	return {
		"badges_to_reassign": badges_to_reassign,
		"badges_to_sum": badges_to_sum,
		"total_source_badges": len(source_badges),
	}


def _get_user_event_stats_summary(source_user, target_user):
	if not _doctype_exists("User Event Stats"):
		return {"stats_to_reassign": 0, "stats_to_sum": 0, "total_source_stats": 0}

	source_stats = frappe.get_all(
		"User Event Stats",
		filters={"user": source_user},
		fields=["name", "event_type", "count"],
	)
	stats_to_reassign = 0
	stats_to_sum = 0

	for stat in source_stats:
		target_row = frappe.db.exists(
			"User Event Stats", {"user": target_user, "event_type": stat.event_type}
		)
		if target_row:
			stats_to_sum += 1
		else:
			stats_to_reassign += 1

	return {
		"stats_to_reassign": stats_to_reassign,
		"stats_to_sum": stats_to_sum,
		"total_source_stats": len(source_stats),
	}


def _get_ninja_profile_preview(source_user, target_user):
	current = {"contributions": 0, "hours_invested": 0}
	projected = {"contributions": 0, "hours_invested": 0}

	if _doctype_exists("Ninja Profile") and frappe.db.exists("Ninja Profile", target_user):
		current = frappe.db.get_value(
			"Ninja Profile",
			target_user,
			["contributions", "hours_invested"],
			as_dict=True,
		) or current

	source_events = frappe.db.count("Events", {"user": source_user}) if _doctype_exists("Events") else 0
	target_events = frappe.db.count("Events", {"user": target_user}) if _doctype_exists("Events") else 0

	source_hours = 0
	target_hours = 0
	if _doctype_exists("Events"):
		source_result = frappe.db.get_all(
			"Events",
			filters={"user": source_user},
			fields=["sum(hours_invested) as total_hours"],
		)
		target_result = frappe.db.get_all(
			"Events",
			filters={"user": target_user},
			fields=["sum(hours_invested) as total_hours"],
		)
		source_hours = flt(source_result[0].get("total_hours")) if source_result else 0
		target_hours = flt(target_result[0].get("total_hours")) if target_result else 0

	projected = {
		"contributions": cint(target_events) + cint(source_events),
		"hours_invested": flt(target_hours) + flt(source_hours),
	}

	return {
		"current": {
			"contributions": cint(current.get("contributions")),
			"hours_invested": flt(current.get("hours_invested")),
		},
		"projected": projected,
	}


def _get_profile_fill_preview(source_user, target_user):
	preview = {"user": [], "user_metadata": [], "ninja_profile": []}

	source_user_doc = frappe.get_doc("User", source_user)
	target_user_doc = frappe.get_doc("User", target_user)

	for fieldname in USER_FILL_FIELDS:
		if fieldname in PROTECTED_USER_FIELDS:
			continue
		if _is_empty(getattr(target_user_doc, fieldname, None)) and not _is_empty(
			getattr(source_user_doc, fieldname, None)
		):
			preview["user"].append(fieldname)

	if _doctype_exists("User Metadata"):
		if frappe.db.exists("User Metadata", source_user) and frappe.db.exists("User Metadata", target_user):
			source_meta = frappe.get_doc("User Metadata", source_user)
			target_meta = frappe.get_doc("User Metadata", target_user)
			for fieldname in USER_METADATA_FILL_FIELDS:
				if _is_empty(getattr(target_meta, fieldname, None)) and not _is_empty(
					getattr(source_meta, fieldname, None)
				):
					preview["user_metadata"].append(fieldname)
			if not target_meta.get("tags") and source_meta.get("tags"):
				preview["user_metadata"].append("tags")

	if _doctype_exists("Ninja Profile"):
		if frappe.db.exists("Ninja Profile", source_user) and frappe.db.exists("Ninja Profile", target_user):
			source_np = frappe.get_doc("Ninja Profile", source_user)
			target_np = frappe.get_doc("Ninja Profile", target_user)
			for fieldname in NINJA_PROFILE_FILL_FIELDS:
				if _is_empty(getattr(target_np, fieldname, None)) and not _is_empty(
					getattr(source_np, fieldname, None)
				):
					preview["ninja_profile"].append(fieldname)

	return preview


def _reassign_records(source_user, target_user):
	results = {}
	for doctype, fieldname in REASSIGNMENTS:
		if not _doctype_exists(doctype):
			continue
		count = frappe.db.count(doctype, {fieldname: source_user})
		if count:
			frappe.db.sql(
				f"""
				UPDATE `tab{doctype}`
				SET `{fieldname}` = %s, modified = %s, modified_by = %s
				WHERE `{fieldname}` = %s
				""",
				(target_user, now_datetime(), frappe.session.user, source_user),
			)
		results[f"{doctype}.{fieldname}"] = count
	return results


def _merge_user_badges(source_user, target_user):
	if not _doctype_exists("User badge"):
		return {"badges_reassigned": 0, "badges_merged": 0}

	source_badges = frappe.get_all(
		"User badge",
		filters={"user": source_user},
		fields=["name", "badge", "badge_count", "active"],
	)
	badges_reassigned = 0
	badges_merged = 0

	for badge in source_badges:
		target_row = frappe.db.get_value(
			"User badge",
			{"user": target_user, "badge": badge.badge},
			["name", "badge_count", "active"],
			as_dict=True,
		)
		if target_row:
			new_count = cint(target_row.badge_count) + cint(badge.badge_count)
			new_active = cint(target_row.active) or cint(badge.active)
			frappe.db.set_value(
				"User badge",
				target_row.name,
				{"badge_count": new_count, "active": new_active},
			)
			frappe.delete_doc("User badge", badge.name, ignore_permissions=True, force=True)
			badges_merged += 1
		else:
			frappe.db.set_value("User badge", badge.name, "user", target_user)
			badges_reassigned += 1

	return {"badges_reassigned": badges_reassigned, "badges_merged": badges_merged}


def _merge_user_event_stats(source_user, target_user):
	if not _doctype_exists("User Event Stats"):
		return {"stats_reassigned": 0, "stats_merged": 0}

	source_stats = frappe.get_all(
		"User Event Stats",
		filters={"user": source_user},
		fields=["name", "event_type", "count"],
	)
	stats_reassigned = 0
	stats_merged = 0

	for stat in source_stats:
		target_row = frappe.db.get_value(
			"User Event Stats",
			{"user": target_user, "event_type": stat.event_type},
			["name", "count"],
			as_dict=True,
		)
		if target_row:
			new_count = cint(target_row.count) + cint(stat.count)
			frappe.db.set_value("User Event Stats", target_row.name, "count", new_count)
			frappe.delete_doc("User Event Stats", stat.name, ignore_permissions=True, force=True)
			stats_merged += 1
		else:
			frappe.db.set_value("User Event Stats", stat.name, "user", target_user)
			stats_reassigned += 1

	return {"stats_reassigned": stats_reassigned, "stats_merged": stats_merged}


def _reassign_mentor_metadata(source_user, target_user):
	"""Mentorship Request.assigned_mentor links to User Metadata (name = user email)."""
	if not _doctype_exists("Mentorship Request"):
		return

	if not frappe.db.exists("User Metadata", source_user):
		return

	count = frappe.db.count("Mentorship Request", {"assigned_mentor": source_user})
	if count and frappe.db.exists("User Metadata", target_user):
		frappe.db.sql(
			"""
			UPDATE `tabMentorship Request`
			SET `assigned_mentor` = %s, modified = %s, modified_by = %s
			WHERE `assigned_mentor` = %s
			""",
			(target_user, now_datetime(), frappe.session.user, source_user),
		)


def _merge_profile_documents(source_user, target_user):
	_merge_user_fields(source_user, target_user)
	_merge_user_metadata(source_user, target_user)
	_merge_ninja_profile_fields(source_user, target_user)


def _merge_user_fields(source_user, target_user):
	source_doc = frappe.get_doc("User", source_user)
	target_doc = frappe.get_doc("User", target_user)
	updated = False

	for fieldname in USER_FILL_FIELDS:
		if fieldname in PROTECTED_USER_FIELDS:
			continue
		source_value = getattr(source_doc, fieldname, None)
		target_value = getattr(target_doc, fieldname, None)
		if _is_empty(target_value) and not _is_empty(source_value):
			target_doc.set(fieldname, source_value)
			updated = True

	if updated:
		target_doc.flags.ignore_permissions = True
		target_doc.save(ignore_permissions=True)


def _merge_user_metadata(source_user, target_user):
	if not _doctype_exists("User Metadata"):
		return
	if not frappe.db.exists("User Metadata", source_user) or not frappe.db.exists("User Metadata", target_user):
		return

	source_doc = frappe.get_doc("User Metadata", source_user)
	target_doc = frappe.get_doc("User Metadata", target_user)
	updated = False

	for fieldname in USER_METADATA_FILL_FIELDS:
		source_value = getattr(source_doc, fieldname, None)
		target_value = getattr(target_doc, fieldname, None)
		if _is_empty(target_value) and not _is_empty(source_value):
			target_doc.set(fieldname, source_value)
			updated = True

	if not target_doc.get("tags") and source_doc.get("tags"):
		target_doc.set("tags", [])
		for row in source_doc.tags:
			target_doc.append(
				"tags",
				{
					"tag": row.tag,
				},
			)
		updated = True

	if updated:
		target_doc.flags.ignore_permissions = True
		target_doc.save(ignore_permissions=True)


def _merge_ninja_profile_fields(source_user, target_user):
	if not _doctype_exists("Ninja Profile"):
		return
	if not frappe.db.exists("Ninja Profile", source_user) or not frappe.db.exists("Ninja Profile", target_user):
		return

	source_doc = frappe.get_doc("Ninja Profile", source_user)
	target_doc = frappe.get_doc("Ninja Profile", target_user)
	updated = False

	for fieldname in NINJA_PROFILE_FILL_FIELDS:
		source_value = getattr(source_doc, fieldname, None)
		target_value = getattr(target_doc, fieldname, None)
		if _is_empty(target_value) and not _is_empty(source_value):
			target_doc.set(fieldname, source_value)
			updated = True

	if updated:
		target_doc.flags.ignore_permissions = True
		target_doc.save(ignore_permissions=True)


def _disable_source_user(source_user):
	frappe.db.set_value("User", source_user, "enabled", 0)


def _add_merge_comments(source_user, target_user):
	comment_text = _(
		"Merged user {0} into this account. Performed by {1} on {2}."
	).format(source_user, frappe.session.user, now_datetime())

	for user_name, content in (
		(target_user, comment_text),
		(
			source_user,
			_("This account was merged into {0} by {1} on {2}.").format(
				target_user, frappe.session.user, now_datetime()
			),
		),
	):
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "User",
				"reference_name": user_name,
				"content": content,
			}
		).insert(ignore_permissions=True)
