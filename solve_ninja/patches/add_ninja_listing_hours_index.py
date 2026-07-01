import frappe


def execute():
	frappe.db.add_index(
		"Ninja Profile",
		["hours_invested"],
		index_name="ninja_profile_hours_invested_idx",
	)
