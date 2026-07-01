import frappe

ROLE_NAME = "Organisation Manager"


def execute():
	if frappe.db.exists("Role", ROLE_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": ROLE_NAME,
			"desk_access": 0,
		}
	).insert(ignore_permissions=True)
