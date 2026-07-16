"""Shared helpers for Solve Event registration (marketplace + Glific)."""

import frappe
from frappe import _


def is_active_registration_status(status):
	return (status or "").strip() != "Rejected"


def parse_registration_request_data(solve_event=None, mobile=None):
	data = {}
	if frappe.request and frappe.request.data:
		try:
			import json

			parsed = json.loads(frappe.request.data)
			if isinstance(parsed, dict):
				data.update(parsed)
		except Exception:
			pass

	if solve_event:
		data["solve_event"] = solve_event
	if mobile:
		data["mobile"] = mobile

	return data


def is_marketplace_session_user(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return False
	return user.endswith("@solveninja.org")


def resolve_solve_event_name(identifier):
	value = (identifier or "").strip()
	if not value:
		return None

	if frappe.db.exists("Solve Event", value):
		return value

	return frappe.db.get_value("Solve Event", {"unique_id": value.upper()}, "name")


def find_existing_registration(user, solve_event_name):
	"""Return the active (non-Rejected) registration for user + event, if any."""
	if not user or not solve_event_name:
		return None

	rows = frappe.get_all(
		"Solve Event Registration",
		filters={"user": user, "solve_event": solve_event_name},
		fields=["name", "status"],
		order_by="creation asc",
		limit_page_length=0,
	)
	for row in rows:
		if is_active_registration_status(row.status):
			return row.name

	return None


def find_original_registration_for_user_event(user, solve_event_name, exclude_name=None):
	"""Find the earliest active registration, used when a duplicate Rejected row was created."""
	filters = {"user": user, "solve_event": solve_event_name}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]

	rows = frappe.get_all(
		"Solve Event Registration",
		filters=filters,
		fields=["name", "status"],
		order_by="creation asc",
		limit_page_length=0,
	)
	for row in rows:
		if is_active_registration_status(row.status):
			return row.name

	return None


def _user_mobile_digits(user_doc, mobile_hint=None):
	digits = "".join(ch for ch in str(mobile_hint or "") if ch.isdigit())
	if len(digits) >= 10:
		return digits[-10:]

	mobile = (user_doc.get("mobile_no") or user_doc.get("phone") or "").strip()
	digits = "".join(ch for ch in mobile if ch.isdigit())
	return digits[-10:] if len(digits) >= 10 else digits


def create_marketplace_registration(user, solve_event_name, mobile=None):
	user_doc = frappe.get_doc("User", user)
	registration_doc = frappe.get_doc(
		{
			"doctype": "Solve Event Registration",
			"user": user,
			"solve_event": solve_event_name,
			"full_name": user_doc.full_name or user_doc.first_name or user,
			"mobile": _user_mobile_digits(user_doc, mobile),
			"source": "Web Form",
		}
	)
	registration_doc.insert(ignore_permissions=True, ignore_links=True)

	if registration_doc.status == "Rejected":
		original = find_original_registration_for_user_event(
			user, solve_event_name, exclude_name=registration_doc.name
		)
		if original:
			return frappe.get_doc("Solve Event Registration", original)

	return registration_doc


def register_marketplace_user(data):
	user = frappe.session.user
	if not is_marketplace_session_user(user):
		frappe.throw(_("Please log in to register."), frappe.PermissionError)

	solve_event_identifier = data.get("solve_event")
	if not solve_event_identifier:
		frappe.throw(_("Event is required."))

	solve_event_name = resolve_solve_event_name(solve_event_identifier)
	if not solve_event_name:
		frappe.throw(_("Event not found."))

	existing = find_existing_registration(user, solve_event_name)
	if existing:
		return {
			"success": True,
			"already_registered": True,
			"registration_name": existing,
			"event_id": solve_event_identifier,
		}

	registration_doc = create_marketplace_registration(
		user,
		solve_event_name,
		mobile=data.get("mobile"),
	)

	if registration_doc.status == "Rejected":
		original = find_original_registration_for_user_event(
			user, solve_event_name, exclude_name=registration_doc.name
		)
		if original:
			return {
				"success": True,
				"already_registered": True,
				"registration_name": original,
				"event_id": solve_event_identifier,
			}

	return {
		"success": True,
		"already_registered": False,
		"registration_name": registration_doc.name,
		"event_id": solve_event_identifier,
	}


def enrich_events_with_registration_status(events, user=None):
	if not isinstance(events, list):
		return events

	user = user if user is not None else frappe.session.user
	if not user or user == "Guest":
		for event in events:
			if isinstance(event, dict):
				event["is_registered"] = False
		return events

	event_names = [
		event.get("name")
		for event in events
		if isinstance(event, dict) and event.get("name")
	]
	if not event_names:
		for event in events:
			if isinstance(event, dict):
				event["is_registered"] = False
		return events

	user_rows = frappe.get_all(
		"Solve Event Registration",
		filters={"user": user, "solve_event": ["in", event_names]},
		fields=["solve_event", "status"],
	)
	registered_set = {
		row.solve_event
		for row in user_rows
		if is_active_registration_status(row.status)
	}

	all_rows = frappe.get_all(
		"Solve Event Registration",
		filters={"solve_event": ["in", event_names]},
		fields=["solve_event", "status"],
	)
	count_map = {}
	for row in all_rows:
		if not is_active_registration_status(row.status):
			continue
		count_map[row.solve_event] = count_map.get(row.solve_event, 0) + 1

	for event in events:
		if not isinstance(event, dict):
			continue
		event_name = event.get("name")
		event["is_registered"] = bool(event_name and event_name in registered_set)
		if event_name and event_name in count_map:
			event["registered_count"] = count_map[event_name]

	return events
