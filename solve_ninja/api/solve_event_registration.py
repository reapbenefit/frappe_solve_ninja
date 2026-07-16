import frappe

from solve_ninja.api.event_registration_utils import (
	find_existing_registration,
	is_marketplace_session_user,
	parse_registration_request_data,
	register_marketplace_user,
)
from solve_ninja.utils import find_or_create_user_by_mobile


def _register_glific_via_mobile(data):
	"""Existing Glific / server-to-server registration flow."""
	mobile = data.get("mobile") or data.get("user")
	whatsapp_name = data.get("whatsapp_name")
	solve_event = frappe.db.exists("Solve Event", data.get("solve_event"))
	event_unique_id = None

	if not solve_event:
		solve_event = frappe.db.exists(
			"Solve Event", {"unique_id": data.get("solve_event").upper()}
		)
		event_unique_id = data.get("solve_event").upper()
	else:
		event_unique_id = frappe.db.get_value(
			"Solve Event", data.get("solve_event"), "unique_id"
		)

	if not mobile:
		frappe.throw("Mobile/User number is required.")

	user_result = find_or_create_user_by_mobile(mobile, whatsapp_name, solve_event)
	if not user_result or not user_result.get("user"):
		frappe.throw("Failed to create or find user")

	user = user_result["user"]
	solve_event_name = (
		solve_event
		if solve_event
		else frappe.db.exists("Solve Event", {"unique_id": event_unique_id.upper()})
	)

	existing = find_existing_registration(user, solve_event_name)
	if existing:
		return frappe.get_doc("Solve Event Registration", existing).as_dict()

	data["user"] = user
	data["doctype"] = "Solve Event Registration"
	data["solve_event"] = solve_event_name
	doc = frappe.get_doc(data)
	doc.insert()
	return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def register_solve_event(solve_event=None, mobile=None):
	"""
	Register a user for a Solve Event.

	- Marketplace: logged-in @solveninja.org session user, privileged insert.
	- Glific / integrations: mobile in JSON body, existing flow unchanged.
	"""
	data = parse_registration_request_data(solve_event=solve_event, mobile=mobile)

	if is_marketplace_session_user():
		return register_marketplace_user(data)

	return _register_glific_via_mobile(data)
