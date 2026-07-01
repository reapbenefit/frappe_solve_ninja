import frappe


def execute():
	frappe.db.add_index(
		"Ninja Profile",
		["last_action_date"],
		index_name="ninja_profile_last_action_date_idx",
	)
