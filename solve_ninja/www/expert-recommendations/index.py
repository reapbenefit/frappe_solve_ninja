import frappe
from frappe import _

sitemap = 1
no_cache = 1

def get_context(context):
    if not frappe.request.args.get("user_review"):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    user_review = frappe.db.exists('User Review', frappe.request.args.get("user_review"))
    if not frappe.db.exists('User Review', frappe.request.args.get("user_review")):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)
    context.review = frappe.db.get_value('User Review', user_review, ["*"], as_dict=1)

    if context.review.status == "Accepted":
        frappe.throw(_("Review already Submitted."), frappe.PermissionError)