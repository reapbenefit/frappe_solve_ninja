"""
Ninja lifecycle rules: level (0-3) and status (Active / Inactive / Dormant / Alumni).

Rules (MIS requirements):
- New profiles start at Level 0, Active.
- On action: Active / Inactive become Active with Level 1 (< 30 hours in the last 12 months)
  or Level 2 (>= 30 hours). Dormant becomes Active at Level 1.
- Month end: no action in 6 months -> Inactive; no action in 12 months -> Dormant
  (never for Level 3). Level 2 with < 30 hours in the last 12 months -> Level 1.
- Level 3 and Alumni are assigned manually and never changed automatically. The one exception
  is the initial setup of existing profiles: >= 50 hours in the last 12 months starts at Level 3.

Every level / status change is recorded in Ninja Lifecycle Log.
"""

import frappe
from frappe.utils import add_months, cint, flt, get_datetime, now_datetime

LEVEL_2_MIN_HOURS = 30
# Only used when first setting up existing profiles; afterwards Level 3 is assigned manually
LEVEL_3_SETUP_MIN_HOURS = 50
INACTIVE_AFTER_MONTHS = 6
DORMANT_AFTER_MONTHS = 12
ACTIVITY_WINDOW_MONTHS = 12
MANUAL_LEVEL = 3

ACTIVE = "Active"
INACTIVE = "Inactive"
DORMANT = "Dormant"
ALUMNI = "Alumni"

REASON_ACTION = "Action"
REASON_INACTIVE = "Inactive 6 Months"
REASON_DORMANT = "Dormant 12 Months"
REASON_HOURS_BELOW = "Hours Below 30"
REASON_MANUAL = "Manual"
REASON_RECALCULATION = "Manual Recalculation"
REASON_INITIAL_SETUP = "Initial Setup"

LOG_DOCTYPE = "Ninja Lifecycle Log"
PROFILE_DOCTYPE = "Ninja Profile"

# Postgres runs at REPEATABLE READ: locking a row another transaction changed raises 40001
SERIALIZATION_FAILURE = "40001"


# ---------------------------------------------------------------------------
# Pure decision rules (no database access)
# ---------------------------------------------------------------------------


def level_for_hours(hours_12m):
	return 2 if flt(hours_12m) >= LEVEL_2_MIN_HOURS else 1


def decide_on_activity(level, status, hours_12m, has_recent_action, has_action_12m):
	"""Level / status after the ninja's actions are (re)counted."""
	level = cint(level)
	status = status or ACTIVE

	if status == DORMANT:
		if not has_recent_action:
			return level, status
		return (level if level == MANUAL_LEVEL else 1), ACTIVE

	if status == INACTIVE:
		if not has_recent_action:
			return level, status
		status = ACTIVE

	if level == MANUAL_LEVEL or not has_action_12m:
		return level, status
	return level_for_hours(hours_12m), status


def decide_on_inactivity(level, status, last_activity_on, as_of):
	"""Status after the month-end inactivity check. Level is never changed here."""
	level = cint(level)
	status = status or ACTIVE
	if status not in (ACTIVE, INACTIVE) or not last_activity_on:
		return level, status

	last_activity_on = get_datetime(last_activity_on)
	as_of = get_datetime(as_of)
	if last_activity_on <= add_months(as_of, -DORMANT_AFTER_MONTHS) and level != MANUAL_LEVEL:
		return level, DORMANT
	if last_activity_on <= add_months(as_of, -INACTIVE_AFTER_MONTHS):
		return level, INACTIVE
	return level, status


def decide_level_decay(level, hours_12m):
	"""Level 2 drops to Level 1 when the last 12 months fall below the threshold."""
	level = cint(level)
	if level == 2 and flt(hours_12m) < LEVEL_2_MIN_HOURS:
		return 1
	return level


def decide_initial(last_action_on, profile_created_on, hours_12m, as_of):
	"""Starting level / status for an existing profile, derived from its history."""
	as_of = get_datetime(as_of)
	if not last_action_on:
		level = 0
	elif get_datetime(last_action_on) <= add_months(as_of, -ACTIVITY_WINDOW_MONTHS):
		level = 1
	elif flt(hours_12m) >= LEVEL_3_SETUP_MIN_HOURS:
		level = MANUAL_LEVEL
	else:
		level = level_for_hours(hours_12m)
	_, status = decide_on_inactivity(level, ACTIVE, last_action_on or profile_created_on, as_of)
	return level, status


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_ninja_activity(user, as_of=None):
	"""Hours and action presence for one ninja, from Events by date_of_action."""
	as_of = get_datetime(as_of) if as_of else now_datetime()
	params = {
		"user": user,
		"window_start": add_months(as_of, -ACTIVITY_WINDOW_MONTHS),
		"recent_start": add_months(as_of, -INACTIVE_AFTER_MONTHS),
		"as_of": as_of,
	}
	row = frappe.db.sql(
		"""
		select
			coalesce(sum(hours_invested), 0) as hours_12m,
			count(*) as actions_12m,
			coalesce(sum(case when date_of_action > %(recent_start)s then 1 else 0 end), 0) as actions_6m,
			max(date_of_action) as last_action_on
		from `tabEvents`
		where `user` = %(user)s
			and date_of_action > %(window_start)s
			and date_of_action <= %(as_of)s
		""",
		params,
		as_dict=True,
	)[0]
	last_action_on = row.last_action_on or frappe.db.sql(
		"""select max(date_of_action) from `tabEvents` where `user` = %(user)s and date_of_action <= %(as_of)s""",
		params,
	)[0][0]
	return frappe._dict(
		hours_12m=flt(row.hours_12m),
		has_action_12m=cint(row.actions_12m) > 0,
		has_recent_action=cint(row.actions_6m) > 0,
		last_action_on=last_action_on,
	)


def make_log_row(ninja, from_level, from_status, to_level, to_status, reason, changed_on, event=None):
	return {
		"ninja": ninja,
		"changed_on": get_datetime(changed_on),
		"reason": reason,
		"event": event,
		"from_level": _level_str(from_level),
		"to_level": _level_str(to_level),
		"from_status": from_status,
		"to_status": to_status,
	}


def insert_log_rows(rows):
	"""Bulk insert Ninja Lifecycle Log rows (dicts from make_log_row)."""
	if not rows:
		return
	now = now_datetime()
	user = frappe.session.user or "Administrator"
	fields = [
		"name",
		"creation",
		"modified",
		"owner",
		"modified_by",
		"docstatus",
		"idx",
		"ninja",
		"changed_on",
		"reason",
		"event",
		"from_level",
		"to_level",
		"from_status",
		"to_status",
	]
	values = [
		(
			frappe.generate_hash(length=10),
			now,
			now,
			user,
			user,
			0,
			0,
			row["ninja"],
			row["changed_on"],
			row["reason"],
			row.get("event"),
			row.get("from_level"),
			row.get("to_level"),
			row.get("from_status"),
			row.get("to_status"),
		)
		for row in rows
	]
	frappe.db.bulk_insert(LOG_DOCTYPE, fields, values)


def is_concurrent_update_error(error):
	return frappe.db.is_deadlocked(error) or getattr(error, "pgcode", None) == SERIALIZATION_FAILURE


def _level_str(level):
	return None if level is None or level == "" else str(cint(level))


def _reactivation_level_pending(ninja):
	"""True if the ninja came back from Dormant and has not acted since (stays Level 1)."""
	reactivated_on = frappe.db.get_value(
		LOG_DOCTYPE,
		{"ninja": ninja, "from_status": DORMANT, "to_status": ACTIVE},
		"changed_on",
		order_by="changed_on desc",
	)
	if not reactivated_on:
		return False
	return not frappe.db.exists("Events", {"user": ninja, "creation": [">", reactivated_on]})


# ---------------------------------------------------------------------------
# Per-ninja evaluation
# ---------------------------------------------------------------------------


def evaluate_ninja(ninja, reason=REASON_ACTION, include_inactivity=False, as_of=None, event=None):
	"""
	Re-evaluate one ninja and persist any level / status change with a log entry.

	- Action path (include_inactivity=False): reactivation + level rules only.
	- Recalculation (include_inactivity=True): also applies the inactivity and level decay rules.
	Returns a dict with the final level / status and whether anything changed.
	"""
	as_of = get_datetime(as_of) if as_of else now_datetime()
	profile = frappe.db.get_value(
		PROFILE_DOCTYPE,
		ninja,
		["name", "ninja_level", "ninja_status", "creation"],
		as_dict=True,
		for_update=True,
	)
	if not profile:
		return None

	old_level = cint(profile.ninja_level)
	old_status = profile.ninja_status or ACTIVE
	activity = get_ninja_activity(ninja, as_of)

	new_level, new_status = decide_on_activity(
		old_level, old_status, activity.hours_12m, activity.has_recent_action, activity.has_action_12m
	)
	if (
		old_status == ACTIVE
		and old_level == 1
		and new_level == 2
		and _reactivation_level_pending(ninja)
	):
		new_level = 1

	logs = []
	if (new_level, new_status) != (old_level, old_status):
		logs.append(make_log_row(ninja, old_level, old_status, new_level, new_status, reason, as_of, event))

	if include_inactivity:
		level, status = decide_on_inactivity(
			new_level, new_status, activity.last_action_on or profile.creation, as_of
		)
		level = decide_level_decay(level, activity.hours_12m)
		if (level, status) != (new_level, new_status):
			logs.append(make_log_row(ninja, new_level, new_status, level, status, reason, as_of, event))
			new_level, new_status = level, status

	values = {"hours_last_12_months": activity.hours_12m, "hours_calculated_on": as_of}
	if new_level != old_level:
		values["ninja_level"] = str(new_level)
	if new_status != old_status:
		values["ninja_status"] = new_status

	frappe.db.set_value(PROFILE_DOCTYPE, ninja, values, update_modified=False)
	insert_log_rows(logs)

	return {
		"ninja": ninja,
		"changed": bool(logs),
		"from_level": old_level,
		"from_status": old_status,
		"level": new_level,
		"status": new_status,
		"hours_last_12_months": activity.hours_12m,
	}


def evaluate_ninja_after_events_change(user):
	"""
	Called from the Events profile-refresh job after any insert / update / delete.

	Runs inside a savepoint so a clash with a concurrent update (e.g. the monthly job)
	only undoes this evaluation; it is then retried in a fresh job.
	"""
	if not user or not frappe.db.exists(PROFILE_DOCTYPE, user):
		return
	latest_event = frappe.db.get_value(
		"Events", {"user": user}, "name", order_by="creation desc"
	)

	save_point = "ninja_lifecycle_eval"
	frappe.db.savepoint(save_point)
	try:
		evaluate_ninja(user, reason=REASON_ACTION, event=latest_event)
	except Exception as error:
		frappe.db.rollback(save_point=save_point)
		if not is_concurrent_update_error(error):
			raise
		frappe.enqueue(
			"solve_ninja.services.ninja_lifecycle.evaluate_ninja_after_events_change",
			queue="default",
			user=user,
			enqueue_after_commit=True,
		)
	else:
		frappe.db.release_savepoint(save_point)


@frappe.whitelist()
def recalculate_ninja(ninja):
	"""Recalculate Level & Status button on Ninja Profile."""
	frappe.only_for("System Manager")
	result = evaluate_ninja(ninja, reason=REASON_RECALCULATION, include_inactivity=True)
	if result is None:
		frappe.throw(frappe._("Ninja Profile {0} not found").format(ninja))
	return result


def log_manual_change(doc):
	"""Ninja Profile.on_update: record level / status edits made by staff in the form."""
	before = doc.get_doc_before_save()
	if not before:
		return
	old = (cint(before.ninja_level), before.ninja_status or ACTIVE)
	new = (cint(doc.ninja_level), doc.ninja_status or ACTIVE)
	if old == new:
		return
	insert_log_rows([make_log_row(doc.name, old[0], old[1], new[0], new[1], REASON_MANUAL, now_datetime())])
