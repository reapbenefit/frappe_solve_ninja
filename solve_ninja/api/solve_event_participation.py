import frappe
from frappe.model.document import get_doc

@frappe.whitelist(allow_guest=True)
def participate_solve_event():
    import json
    data = json.loads(frappe.request.data)

    if data.get("user") and not data["user"].endswith("@solveninja.org"):
        candidate_user = f"{data['user']}@solveninja.org"
        if frappe.db.exists("User", candidate_user):
            data["user"] = candidate_user
        else:
            frappe.throw(f"User {candidate_user} does not exist.")

    data["doctype"]="Solve Event Participation"
    doc = frappe.get_doc(data)
    doc.insert()
    return doc.as_dict()