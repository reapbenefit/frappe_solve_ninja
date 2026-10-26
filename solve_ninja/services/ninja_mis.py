"""
Monthly MIS job for ninja lifecycle.

Runs on the 1st of every month (00:30, site timezone) for the month that just ended:
1. Status check as of the month end (Inactive after 6 months, Dormant after 12).
2. Level check as of the month end (Level 2 -> 1 when 12-month hours drop below 30).
3. Ninja Monthly Snapshot for the month.

All steps are set-based (one aggregate pass over Events) and write in bulk, so the cost
grows with the number of rows rather than ninjas x events.
"""

import frappe
from frappe import _
from frappe.utils import (
	add_months,
	cint,
	flt,
	get_datetime,
	get_first_day,
	get_last_day,
	getdate,
	now_datetime,
	today,
)

from solve_ninja.services.ninja_lifecycle import (
	ACTIVE,
	ACTIVITY_WINDOW_MONTHS,
	DORMANT,
	LOG_DOCTYPE,
	PROFILE_DOCTYPE,
	REASON_DORMANT,
	REASON_HOURS_BELOW,
	REASON_INACTIVE,
	REASON_INITIAL_SETUP,
	decide_initial,
	decide_level_decay,
	decide_on_inactivity,
	insert_log_rows,
	is_concurrent_update_error,
	make_log_row,
)

SNAPSHOT_DOCTYPE = "Ninja Monthly Snapshot"
STEPS_ALL = "all"
STEPS_SNAPSHOT = "snapshot"
CHUNK_SIZE = 500
MAX_CHUNK_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def run_monthly_job():
	"""Scheduler entry (cron). Cron jobs run on the default queue, so hand off to long."""
	month_start = get_first_day(add_months(today(), -1))
	frappe.enqueue(
		"solve_ninja.services.ninja_mis.run_for_month",
		queue="long",
		timeout=3600,
		job_id=f"ninja_mis||{month_start}",
		deduplicate=True,
		month=str(month_start),
		steps=STEPS_ALL,
	)


@frappe.whitelist()
def trigger_monthly_mis(month=None, steps=STEPS_ALL):
	"""Run Monthly MIS button on the Ninja Monthly Snapshot list."""
	frappe.only_for("System Manager")
	month_start = validate_run(month, steps)
	frappe.enqueue(
		"solve_ninja.services.ninja_mis.run_for_month",
		queue="long",
		timeout=3600,
		job_id=f"ninja_mis||{month_start}",
		deduplicate=True,
		month=str(month_start),
		steps=steps,
	)
	return _("Monthly MIS for {0} has started in the background. Refresh in a minute.").format(
		month_start.strftime("%B %Y")
	)


def validate_run(month, steps):
	"""Return the month's first day, or throw if the requested run is not allowed."""
	if steps not in (STEPS_ALL, STEPS_SNAPSHOT):
		frappe.throw(_("Invalid steps: {0}").format(steps))

	month_start = getdate(get_first_day(month or add_months(today(), -1)))
	current_month = getdate(get_first_day(today()))
	previous_month = getdate(get_first_day(add_months(today(), -1)))

	if month_start > current_month:
		frappe.throw(_("Cannot run for a future month."))
	if steps == STEPS_ALL and month_start != previous_month:
		frappe.throw(
			_("The full monthly job (status, level, snapshot) can only run for last month ({0}). Use 'Rebuild snapshot only' for other months.").format(
				previous_month.strftime("%B %Y")
			)
		)

	go_live = get_go_live()
	if not go_live:
		frappe.throw(_("Ninja lifecycle has not been initialised yet (run bench migrate)."))
	if month_end_of(month_start) < go_live:
		frappe.throw(
			_("Snapshots start from {0}, when ninja levels and statuses were first set up.").format(
				getdate(go_live).strftime("%B %Y")
			)
		)
	return month_start


def run_for_month(month=None, steps=STEPS_ALL, users=None, commit=True):
	month_start = getdate(get_first_day(month or add_months(today(), -1)))
	month_end = month_end_of(month_start)
	if steps == STEPS_ALL:
		apply_month_end_rules(month_end, users=users, commit=commit)
	return build_snapshot(month_start, users=users, commit=commit)


def month_end_of(month_start):
	month_end = get_datetime(f"{get_last_day(month_start)} 23:59:59")
	now = now_datetime()
	return now if month_end > now else month_end


def get_go_live():
	return frappe.db.get_value(
		LOG_DOCTYPE, {"reason": REASON_INITIAL_SETUP}, "changed_on", order_by="changed_on asc"
	)


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


def load_activity(as_of, month_start=None, users=None):
	"""
	One pass over Events. Per user:
	last_action_on (<= as_of), last_action_any (no upper bound), hours_12m (as of as_of),
	and, when month_start is given, month_actions / month_hours within [month_start, as_of].
	"""
	as_of = get_datetime(as_of)
	params = {
		"as_of": as_of,
		"window_start": add_months(as_of, -ACTIVITY_WINDOW_MONTHS),
		"month_start": get_datetime(month_start) if month_start else as_of,
	}
	user_condition = ""
	if users:
		user_condition = "and `user` in %(users)s"
		params["users"] = tuple(users)

	rows = frappe.db.sql(
		f"""
		select
			`user`,
			max(case when date_of_action <= %(as_of)s then date_of_action end) as last_action_on,
			max(date_of_action) as last_action_any,
			coalesce(sum(case when date_of_action > %(window_start)s and date_of_action <= %(as_of)s
				then hours_invested else 0 end), 0) as hours_12m,
			coalesce(sum(case when date_of_action >= %(month_start)s and date_of_action <= %(as_of)s
				then 1 else 0 end), 0) as month_actions,
			coalesce(sum(case when date_of_action >= %(month_start)s and date_of_action <= %(as_of)s
				then hours_invested else 0 end), 0) as month_hours
		from `tabEvents`
		where `user` is not null and date_of_action is not null {user_condition}
		group by `user`
		""",
		params,
		as_dict=True,
	)
	return {row.user: row for row in rows}


def load_profiles(users=None, fields=None):
	fields = fields or ["name", "ninja_level", "ninja_status", "hours_last_12_months", "creation"]
	filters = {"name": ["in", users]} if users else {}
	return frappe.get_all(PROFILE_DOCTYPE, filters=filters, fields=fields, limit_page_length=0)


def state_as_of(moment, users=None):
	"""Latest logged (level, status) per ninja at or before `moment`."""
	params = {"moment": get_datetime(moment)}
	user_condition = ""
	if users:
		user_condition = "and ninja in %(users)s"
		params["users"] = tuple(users)
	rows = frappe.db.sql(
		f"""
		select ninja, to_level, to_status
		from (
			select ninja, to_level, to_status,
				row_number() over (partition by ninja order by changed_on desc, creation desc) as rn
			from `tabNinja Lifecycle Log`
			where changed_on <= %(moment)s {user_condition}
		) latest
		where rn = 1
		""",
		params,
		as_dict=True,
	)
	return {row.ninja: (row.to_level, row.to_status) for row in rows}


def initial_states(users=None):
	"""(level, status) written by the one-time setup, used for moments before go-live."""
	filters = {"reason": REASON_INITIAL_SETUP}
	if users:
		filters["ninja"] = ["in", users]
	rows = frappe.get_all(
		LOG_DOCTYPE, filters=filters, fields=["ninja", "to_level", "to_status"], limit_page_length=0
	)
	return {row.ninja: (row.to_level, row.to_status) for row in rows}


# ---------------------------------------------------------------------------
# Steps 1 + 2: month-end status and level rules
# ---------------------------------------------------------------------------


def apply_month_end_rules(month_end, users=None, commit=True):
	"""Apply inactivity and level-decay rules as of month_end. Returns number of changes."""
	month_end = get_datetime(month_end)
	activity = load_activity(month_end, users=users)
	profiles = load_profiles(users)

	candidates = []
	for profile in profiles:
		decision = _month_end_decision(profile, activity.get(profile.name), month_end)
		if decision:
			candidates.append(profile.name)

	changes = 0
	for start in range(0, len(candidates), CHUNK_SIZE):
		chunk = candidates[start : start + CHUNK_SIZE]
		for attempt in range(1, MAX_CHUNK_ATTEMPTS + 1):
			if commit:
				# Fresh snapshot, so the locked re-read sees actions committed meanwhile
				frappe.db.commit()
			try:
				changes += _apply_month_end_chunk(chunk, activity, month_end)
				if commit:
					frappe.db.commit()
				break
			except Exception as error:
				if not (commit and is_concurrent_update_error(error) and attempt < MAX_CHUNK_ATTEMPTS):
					raise
				frappe.db.rollback()
	return changes


def _apply_month_end_chunk(chunk, activity, month_end):
	Profile = frappe.qb.DocType(PROFILE_DOCTYPE)
	# Re-read under row locks so a concurrent action is never overwritten
	locked = (
		frappe.qb.from_(Profile)
		.select(
			Profile.name,
			Profile.ninja_level,
			Profile.ninja_status,
			Profile.hours_last_12_months,
			Profile.creation,
		)
		.where(Profile.name.isin(chunk))
		.for_update()
		.run(as_dict=True)
	)
	latest_actions = dict(
		frappe.db.sql(
			"""select `user`, max(date_of_action) from `tabEvents`
			where `user` in %(users)s group by `user`""",
			{"users": tuple(chunk)},
		)
	)

	updates, logs = {}, []
	for profile in locked:
		stats = frappe._dict(activity.get(profile.name) or {})
		stats.last_action_any = latest_actions.get(profile.name)
		decision = _month_end_decision(profile, stats, month_end)
		if not decision:
			continue
		values, profile_logs = decision
		if values:
			updates[profile.name] = values
		logs.extend(profile_logs)

	frappe.db.bulk_update(PROFILE_DOCTYPE, updates, update_modified=False)
	insert_log_rows(logs)
	return len(logs)


def _month_end_decision(profile, activity, month_end):
	"""Return (profile_updates, log_rows) or None if nothing to change."""
	activity = activity or frappe._dict()
	level = cint(profile.ninja_level)
	status = profile.ninja_status or ACTIVE
	hours_12m = flt(activity.get("hours_12m"))

	values, logs = {}, []
	# Acted after the month end: the action rules already own their current state
	acted_since = activity.get("last_action_any") and get_datetime(activity.last_action_any) > month_end
	if not acted_since:
		last_activity_on = activity.get("last_action_on") or profile.creation
		new_level, new_status = decide_on_inactivity(level, status, last_activity_on, month_end)
		if new_status != status:
			reason = REASON_DORMANT if new_status == DORMANT else REASON_INACTIVE
			logs.append(make_log_row(profile.name, level, status, new_level, new_status, reason, month_end))
			values["ninja_status"] = new_status
			status = new_status

		decayed = decide_level_decay(level, hours_12m)
		if decayed != level:
			logs.append(make_log_row(profile.name, level, status, decayed, status, REASON_HOURS_BELOW, month_end))
			values["ninja_level"] = str(decayed)

		if flt(profile.hours_last_12_months) != hours_12m:
			values["hours_last_12_months"] = hours_12m

	if not values and not logs:
		return None
	return values, logs


# ---------------------------------------------------------------------------
# Step 3: monthly snapshot
# ---------------------------------------------------------------------------


def build_snapshot(month_start, users=None, commit=True):
	"""(Re)build Ninja Monthly Snapshot rows for the month. Returns number of rows."""
	month_start = getdate(get_first_day(month_start))
	start_moment = get_datetime(f"{month_start} 00:00:00")
	month_end = month_end_of(month_start)

	profiles = [
		p
		for p in load_profiles(users, fields=["name", "creation"])
		if get_datetime(p.creation) <= month_end
	]
	names = [p.name for p in profiles] if users else None
	start_states = state_as_of(start_moment, names)
	end_states = state_as_of(month_end, names)
	setup_states = initial_states(names)
	activity = load_activity(month_end, month_start=start_moment, users=names)

	quarter = f"{month_start.year} Q{(month_start.month - 1) // 3 + 1}"
	rows = []
	for profile in profiles:
		created_in_month = get_datetime(profile.creation) >= start_moment
		start = None if created_in_month else _resolve_state(profile.name, start_states, setup_states)
		end = _resolve_state(profile.name, end_states, setup_states)

		if not ((start and start[1] != DORMANT) or end[1] != DORMANT):
			continue

		stats = activity.get(profile.name) or frappe._dict()
		rows.append(
			{
				"ninja": profile.name,
				"level_start": start[0] if start else None,
				"status_start": start[1] if start else None,
				"level_end": end[0],
				"status_end": end[1],
				"level_changed": int(bool(start) and start[0] != end[0]),
				"status_changed": int(bool(start) and start[1] != end[1]),
				"new_this_month": int(created_in_month),
				"actions_count": cint(stats.get("month_actions")),
				"hours_invested": flt(stats.get("month_hours")),
			}
		)

	delete_filters = {"month": month_start}
	if users:
		delete_filters["ninja"] = ["in", users]
	frappe.db.delete(SNAPSHOT_DOCTYPE, delete_filters)
	_insert_snapshot_rows(rows, month_start, quarter)
	if commit:
		frappe.db.commit()
	return len(rows)


def _resolve_state(ninja, logged_states, setup_states):
	state = logged_states.get(ninja) or setup_states.get(ninja)
	if not state:
		return ("0", ACTIVE)
	return (str(cint(state[0])), state[1] or ACTIVE)


def _insert_snapshot_rows(rows, month_start, quarter):
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
		"month",
		"quarter",
		"new_this_month",
		"level_start",
		"level_end",
		"level_changed",
		"status_start",
		"status_end",
		"status_changed",
		"actions_count",
		"hours_invested",
	]
	values = (
		(
			frappe.generate_hash(length=10),
			now,
			now,
			user,
			user,
			0,
			0,
			row["ninja"],
			month_start,
			quarter,
			row["new_this_month"],
			row["level_start"],
			row["level_end"],
			row["level_changed"],
			row["status_start"],
			row["status_end"],
			row["status_changed"],
			row["actions_count"],
			row["hours_invested"],
		)
		for row in rows
	)
	frappe.db.bulk_insert(SNAPSHOT_DOCTYPE, fields, values)


# ---------------------------------------------------------------------------
# One-time setup (patch)
# ---------------------------------------------------------------------------


def initialise_lifecycle(as_of=None, users=None, commit=True):
	"""Set level / status for existing profiles from their history and log Initial Setup."""
	as_of = get_datetime(as_of) if as_of else now_datetime()
	already_set_up = set(initial_states(users).keys())
	activity = load_activity(as_of, users=users)

	updates, logs = {}, []
	for profile in load_profiles(users):
		if profile.name in already_set_up:
			continue
		stats = activity.get(profile.name) or frappe._dict()
		hours_12m = flt(stats.get("hours_12m"))
		level, status = decide_initial(stats.get("last_action_on"), profile.creation, hours_12m, as_of)
		updates[profile.name] = {
			"ninja_level": str(level),
			"ninja_status": status,
			"hours_last_12_months": hours_12m,
		}
		logs.append(make_log_row(profile.name, None, None, level, status, REASON_INITIAL_SETUP, as_of))

	names = list(updates)
	for start in range(0, len(names), CHUNK_SIZE):
		chunk = names[start : start + CHUNK_SIZE]
		frappe.db.bulk_update(PROFILE_DOCTYPE, {name: updates[name] for name in chunk}, update_modified=False)
		insert_log_rows(logs[start : start + CHUNK_SIZE])
		if commit:
			frappe.db.commit()
	return len(names)
