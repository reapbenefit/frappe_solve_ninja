import frappe
from frappe.model.document import get_doc
from solve_ninja.utils import find_or_create_user_by_mobile, update_ninja_profile_unique_id

@frappe.whitelist(allow_guest=True)
def register_solve_event():
    import json
    data = json.loads(frappe.request.data)

    # Get mobile and whatsapp_name from request data
    mobile = data.get("mobile") or data.get("user")
    whatsapp_name = data.get("whatsapp_name")
    solve_event = frappe.db.exists("Solve Event", data.get("solve_event"))
    event_unique_id = None
    if not solve_event:
        solve_event = frappe.db.exists("Solve Event", {"unique_id": data.get("solve_event").upper()})
        event_unique_id = data.get("solve_event").upper()
    else:
        event_unique_id = frappe.db.get_value("Solve Event", data.get("solve_event"), "unique_id")

    # Validate mobile number
    if not mobile:
        frappe.throw("Mobile/User number is required.")

    # Find or create user by mobile number
    user_result = find_or_create_user_by_mobile(mobile, whatsapp_name)
    
    if not user_result or not user_result.get("user"):
        frappe.throw("Failed to create or find user")

    user = user_result["user"]

    # Update Ninja Profile with event unique_id
    
    update_ninja_profile_unique_id(user, event_unique_id, solve_event)

    # Set user in data for registration
    data["user"] = user
    data["doctype"] = "Solve Event Registration"
    data["solve_event"] = solve_event if solve_event else frappe.db.exists("Solve Event", {"unique_id": event_unique_id.upper()})
    doc = frappe.get_doc(data)
    doc.insert()
    return doc.as_dict()
