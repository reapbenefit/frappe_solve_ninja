import frappe


def execute():
	"""Backfill User Organizations for existing Programs (shared document ID)."""
	programs = frappe.get_all("Program", pluck="name")
	for program_name in programs:
		try:
			frappe.get_doc("Program", program_name).ensure_user_organization()
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Backfill User Organization failed for Program {program_name}",
			)
