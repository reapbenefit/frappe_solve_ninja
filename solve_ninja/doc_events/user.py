# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe

def after_insert(doc, method):
    create_solve_ninja(doc)

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

def delete_user_with_related_records(user_email):
    """
    Delete a user and all related records (Login OTP, Events, Solve Event Participation, Ninja Profile, User Metadata).
    In production, only allows deletion if email is in approved list.
    
    Args:
        user_email (str): Email address of the user to delete
    """
    # Validate user email is provided
    if not user_email:
        frappe.throw("User email is required", frappe.ValidationError)
    
    # Check if running in production environment
    is_production = not frappe.conf.get("developer_mode", 0)
    
    # In production, validate against approved list
    if is_production:
        approved_list = frappe.conf.get("approved_user_deletion_list", [])
        if not approved_list:
            frappe.throw(
                "No approved user deletion list configured. Please add 'approved_user_deletion_list' to site_config.json",
                frappe.ValidationError
            )
        
        if user_email not in approved_list:
            frappe.throw(
                f"User '{user_email}' is not in the approved deletion list. "
                f"Only users in the approved list can be deleted in production environment.",
                frappe.ValidationError
            )
    
    # Get user by email
    user_name = frappe.db.get_value("User", {"email": user_email}, "name")
    
    if not user_name:
        frappe.throw(
            f"User with email '{user_email}' not found",
            frappe.DoesNotExistError
        )
    
    # Prevent deletion of Administrator
    if user_name == "Administrator":
        frappe.throw("Cannot delete Administrator user", frappe.ValidationError)
    
    # Delete Login OTP records if they exist
    frappe.db.delete("Login OTP", filters={"user": user_name})
    
    # Delete Events records if they exist
    frappe.db.delete("Events", filters={"user": user_name})

    # Delete Events Reviews records if they exist
    frappe.db.delete("Events Review", filters={"user": user_name})

    # Delete Solve Event Participation records if they exist
    frappe.db.delete("Solve Event Participation", filters={"user": user_name})
    
    # Delete Ninja Profile if it exists
    if frappe.db.exists("Ninja Profile", user_name):
        frappe.delete_doc("Ninja Profile", user_name, ignore_permissions=True, force=True)
    
    # Delete User Metadata if it exists
    if frappe.db.exists("User Metadata", user_name):
        frappe.delete_doc("User Metadata", user_name, ignore_permissions=True, force=True)
    
    # Delete User (main record)
    frappe.delete_doc("User", user_name, ignore_permissions=True, force=True)
    frappe.db.commit()