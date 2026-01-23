# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe

def after_insert(doc, method):
    create_solve_ninja(doc)

def on_trash(doc, method):
    """
    Delete the associated Ninja Profile when a User is deleted.
    """
    if frappe.db.exists("Ninja Profile", doc.name):
        frappe.delete_doc("Ninja Profile", doc.name, ignore_permissions=True)

def after_rename(doc, method, old_name, new_name, merge=False):
    """
    Handle cascading updates when a User is renamed.
    Updates Ninja Profile, User Metadata, and all Events records.
    """
    # Skip if merging users (handled differently by Frappe core)
    if merge:
        return
    
    # 1. Rename Ninja Profile if it exists
    if frappe.db.exists("Ninja Profile", old_name):
        frappe.rename_doc("Ninja Profile", old_name, new_name, 
                        force=True, show_alert=False)
        frappe.logger().info(f"Renamed Ninja Profile from {old_name} to {new_name}")
    
    # 2. Rename User Metadata if it exists
    if frappe.db.exists("User Metadata", old_name):
        frappe.rename_doc("User Metadata", old_name, new_name, 
                        force=True, show_alert=False)
        frappe.logger().info(f"Renamed User Metadata from {old_name} to {new_name}")
    
    # 3. Bulk update all Events records where user field matches old_name
    events = frappe.get_all("Events", filters={"user": old_name}, pluck="name")
    if events:
        # Bulk update using SQL for efficiency
        frappe.db.sql("""
            UPDATE `tabEvents`
            SET `user` = %s
            WHERE `user` = %s
        """, (new_name, old_name))
        frappe.db.commit()
        frappe.logger().info(f"Updated {len(events)} Events records from {old_name} to {new_name}")

def create_solve_ninja(doc):
    if not frappe.db.exists("Ninja Profile", doc.name) and doc.name != "Administrator":
        in_import = frappe.flags.in_import
        frappe.get_doc({
            "doctype": "Ninja Profile",
            "user": doc.name,
            "acquisition_source_category": "Direct" if in_import else None
        }).insert(ignore_permissions=True)