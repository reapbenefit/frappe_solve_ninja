import frappe

from solve_ninja.doc_events.user import sync_organisation_manager_permission

ORGANISATION_MANAGER_ROLE = "Organisation Manager"


def execute():
	managers = frappe.get_all(
		"Has Role",
		filters={"role": ORGANISATION_MANAGER_ROLE, "parenttype": "User"},
		pluck="parent",
	)

	for user in managers:
		sync_organisation_manager_permission(user)
