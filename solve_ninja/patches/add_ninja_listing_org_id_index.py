import frappe


def execute():
	frappe.db.add_index(
		"User Metadata",
		["org_id"],
		index_name="user_metadata_org_id_idx",
	)
