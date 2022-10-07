import frappe
import json
from open_civic_backend.api.common import custom_response


@frappe.whitelist()
def new():
    user_data = json.loads(frappe.request.data)
    try:
        mobile_no = user_data.get("mobile_no")
        email = user_data.get("email")
        if not mobile_no:
            frappe.throw("mobile_no field is mandatory")

        if not email:
            frappe.throw("email field is mandatory")

        existing = frappe.db.exists(
            "User", {
                "mobile_no": mobile_no
            }
        )

        if existing:
            frappe.throw("User already exists with mobile no")

        existing = frappe.db.exists(
            "User", {
                "name": email
            }
        )

        if existing:
            frappe.throw("User already exists with email")

        user = frappe.get_doc(
            {
                "doctype": "User",
                **user_data,
            }
        )
        user.insert(ignore_permissions=True)
        user = user.as_dict()
        return user
    except Exception as e:
        frappe.db.rollback()
        return custom_response(str(e), None, 500, True)
