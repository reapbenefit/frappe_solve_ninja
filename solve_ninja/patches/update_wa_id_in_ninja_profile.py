import frappe

def execute():
    """
    Patch to update or create Ninja Profile for Users who have a non-empty wa_id field,
    but only if the User doctype has a wa_id column.
    """
    if not frappe.db.has_column("User", "wa_id"):
        frappe.logger().info("Skipping patch: 'wa_id' column not found in User table.")
        return

    users_with_wa_id = frappe.get_all(
        "User",
        filters={"wa_id": ["not in", ["", None]], "name": ["!=", "Administrator"]},
        fields=["name", "wa_id"]
    )

    for user in users_with_wa_id:
        if frappe.db.exists("Ninja Profile", user.name):
            frappe.db.set_value("Ninja Profile", user.name, "wa_id", user.wa_id)
        else:
            frappe.get_doc({
                "doctype": "Ninja Profile",
                "user": user.name,
                "wa_id": user.wa_id
            }).insert(ignore_permissions=True)
