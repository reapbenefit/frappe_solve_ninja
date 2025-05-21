# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe

def after_insert(doc, method):
    if not frappe.db.exists("Ninja Profile", doc.name) and doc.name != "Administrator":
        frappe.get_doc({
            "doctype": "Ninja Profile",
            "user": doc.name
        }).insert(ignore_permissions=True)
    
def on_trash(doc, method):
    """
    Delete the associated Ninja Profile when a User is deleted.
    """
    if frappe.db.exists("Ninja Profile", doc.name):
        frappe.delete_doc("Ninja Profile", doc.name, ignore_permissions=True)