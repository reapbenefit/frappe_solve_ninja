import frappe

from solve_ninja.services.unique_code import build_web_checkin_url


def execute():
	for doctype in ("Program", "Solve Event", "Social Media"):
		frappe.reload_doctype(doctype)
		rows = frappe.get_all(
			doctype,
			filters={"unique_id": ["is", "set"]},
			fields=["name", "unique_id"],
		)
		for row in rows:
			frappe.db.set_value(
				doctype,
				row.name,
				"web_checkin_url",
				build_web_checkin_url(row.unique_id),
				update_modified=False,
			)
