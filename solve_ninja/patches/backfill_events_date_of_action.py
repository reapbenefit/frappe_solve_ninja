import frappe


def execute():
	"""Set date_of_action = creation where date_of_action is NULL (one-time per site)."""
	
	frappe.db.sql(
		"""
		UPDATE "tabEvents"
		SET date_of_action = creation
		WHERE date_of_action IS NULL
		"""
	)
