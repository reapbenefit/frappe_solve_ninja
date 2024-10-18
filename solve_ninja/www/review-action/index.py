import frappe
from solve_ninja.api.events import get_action_html
from frappe import _

sitemap = 1
no_cache = 1

def get_context(context):
    if not frappe.request.args.get("review"):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    review = frappe.db.exists('Events Review', frappe.request.args.get("review"))
    if not frappe.db.exists('Events Review', frappe.request.args.get("review")):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)
    context.review = frappe.db.get_value('Events Review', review, ["*"], as_dict=1)

    if context.review.status == "Accepted":
        frappe.throw(_("Review already Submitted."), frappe.PermissionError)
    context.event_html = get_action_html(context.review.events)

    # frappe.throw(frappe.request.args.get("events"))
    # frappe.errprint(frappe.request.args)