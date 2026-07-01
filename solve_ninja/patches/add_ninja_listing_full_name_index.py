import frappe


def execute():
	frappe.db.add_index(
		"User",
		["full_name"],
		index_name="user_full_name_idx",
	)
