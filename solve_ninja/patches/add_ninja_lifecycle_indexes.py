import frappe


def execute():
	"""
	Indexes for ninja lifecycle rules and MIS lookups.

	Named explicitly: on Postgres, Frappe names search_index indexes after the bare
	fieldname, so a second doctype with the same fieldname silently gets no index.
	"""
	# Per-ninja 12-month hours and last-action lookups
	frappe.db.add_index(
		"Events",
		["user", "date_of_action"],
		index_name="events_user_date_of_action_idx",
	)
	# Profile Connections and "state as of" lookups for snapshots
	frappe.db.add_index(
		"Ninja Lifecycle Log",
		["ninja", "changed_on"],
		index_name="ninja_lifecycle_log_ninja_changed_on_idx",
	)
	frappe.db.add_index(
		"Ninja Lifecycle Log",
		["changed_on"],
		index_name="ninja_lifecycle_log_changed_on_idx",
	)
	# Month rebuilds and per-ninja Connections
	frappe.db.add_index(
		"Ninja Monthly Snapshot",
		["month", "ninja"],
		index_name="ninja_monthly_snapshot_month_ninja_idx",
	)
	frappe.db.add_index(
		"Ninja Monthly Snapshot",
		["ninja"],
		index_name="ninja_monthly_snapshot_ninja_idx",
	)
