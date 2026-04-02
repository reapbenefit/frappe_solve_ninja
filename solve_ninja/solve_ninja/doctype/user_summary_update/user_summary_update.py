# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
import pandas as pd
from frappe.model.document import Document


class UserSummaryUpdate(Document):

	@frappe.whitelist()
	def start_import(self):
		if not self.file:
			frappe.throw("Please attach a CSV or Excel file before starting the import.")

		self.status = "Queued"
		self.total_users = 0
		self.success_count = 0
		self.error_count = 0
		self.log = ""
		self.save(ignore_permissions=True)

		frappe.enqueue(
			"solve_ninja.solve_ninja.doctype.user_summary_update.user_summary_update.process_import",
			doc_name=self.name,
			queue="long",
			timeout=3600,
		)


def process_import(doc_name: str) -> None:
	doc = frappe.get_doc("User Summary Update", doc_name)
	doc.status = "In Progress"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		file_doc = frappe.get_doc("File", {"file_url": doc.file})
		file_path = file_doc.get_full_path()

		ext = file_path.rsplit(".", 1)[-1].lower()
		if ext in ("xlsx", "xls"):
			df = pd.read_excel(file_path)
		else:
			df = pd.read_csv(file_path)

		# Normalise column names to lowercase for flexible matching
		df.columns = [c.strip().lower() for c in df.columns]

		if "username" in df.columns:
			id_col = "username"
			use_email = False
		elif "email" in df.columns:
			id_col = "email"
			use_email = True
		else:
			doc.status = "Failed"
			doc.log = "CSV/Excel must have a 'username' or 'email' column."
			doc.save(ignore_permissions=True)
			frappe.db.commit()
			return

		from solve_ninja.services.user.user_manager import UserManager

		total = len(df)
		success_count = 0
		error_count = 0
		log_rows = []

		for idx, row in df.iterrows():
			val = str(row[id_col]).strip()
			if not val or val.lower() == "nan":
				continue

			if use_email:
				user_name = val
			else:
				user_name = frappe.db.get_value("User", {"username": val}, "name")
				if not user_name:
					error_count += 1
					log_rows.append((idx + 1, val, "Error", f"Username '{val}' not found"))
					continue

			try:
				UserManager.generate_summary_for_user(user_name=user_name, force=bool(doc.force))
				success_count += 1
				log_rows.append((idx + 1, val, "Success", ""))
			except Exception as e:
				error_count += 1
				log_rows.append((idx + 1, val, "Error", str(e)))

		doc.total_users = total
		doc.success_count = success_count
		doc.error_count = error_count
		doc.log = _build_log_table(log_rows)
		doc.status = "Failed" if success_count == 0 and error_count > 0 else "Completed"
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "User Summary Update Error")
		doc.status = "Failed"
		doc.log = f'<p class="text-danger">{frappe.utils.escape_html(str(e))}</p>'
		doc.save(ignore_permissions=True)
		frappe.db.commit()


def _build_log_table(rows: list) -> str:
	if not rows:
		return ""

	header = (
		"<thead><tr>"
		"<th style='width:60px'>Row</th>"
		"<th>User</th>"
		"<th style='width:90px'>Status</th>"
		"<th>Message</th>"
		"</tr></thead>"
	)

	body_rows = []
	for row_num, user, status, message in rows:
		color = "green" if status == "Success" else "red"
		badge = f'<span style="color:{color};font-weight:600">{status}</span>'
		msg = frappe.utils.escape_html(message) if message else ""
		body_rows.append(
			f"<tr>"
			f"<td>{row_num}</td>"
			f"<td>{frappe.utils.escape_html(user)}</td>"
			f"<td>{badge}</td>"
			f"<td>{msg}</td>"
			f"</tr>"
		)

	return (
		'<table class="table table-bordered table-sm" style="margin-top:8px">'
		f"{header}<tbody>{''.join(body_rows)}</tbody>"
		"</table>"
	)
