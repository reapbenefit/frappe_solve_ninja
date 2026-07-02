import frappe


def execute():
	"""Indexes to support ninja listing filters, sorts, and skill lookups."""
	frappe.db.add_index(
		"Ninja Profile",
		["last_active_date_bot"],
		index_name="ninja_profile_last_active_date_bot_idx",
	)
	frappe.db.add_index(
		"Ninja Profile",
		["contributions"],
		index_name="ninja_profile_contributions_idx",
	)
	frappe.db.add_index(
		"User Metadata",
		["publish_status", "city"],
		index_name="user_metadata_publish_status_city_idx",
	)
	frappe.db.add_index(
		"User badge",
		["user", "active"],
		index_name="user_badge_user_active_idx",
	)
