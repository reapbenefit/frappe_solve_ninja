# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from samaaja.overrides.user import username as samaaja_generate_username

ORGANISATION_MANAGER_ROLE = "Organisation Manager"
SYSTEM_MANAGER_ROLE = "System Manager"
USER_ORGANIZATION_DOCTYPE = "User Organization"


def after_insert(doc, method):
    create_solve_ninja(doc)

def regenerate_username_on_firstname_change(doc, method):
    """
    Regenerate username using Samaaja's username logic when first_name changes.
    This runs only for existing users; new user creation continues to use
    Samaaja's own hooks.
    """
    # Skip new documents so that Samaaja continues to own username creation
    if doc.is_new():
        return

    # Optionally skip system users
    if doc.name == "Administrator":
        return

    # Check if first_name actually changed compared to the persisted value
    existing_first_name = frappe.db.get_value("User", doc.name, "first_name")
    if existing_first_name == doc.first_name:
        return

    # Clear current username so Samaaja's handler regenerates it
    doc.username = None
    samaaja_generate_username(doc, method)

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

def on_user_update(doc, method):
	sync_organisation_manager_permission(doc.name)


def sync_organisation_manager_permission(user, org_id=None):
	"""Keep User Permission (User Organization) in sync with Organisation Manager role."""
	if not user or user in ("Administrator", "Guest"):
		return

	roles = set(frappe.get_roles(user))
	if SYSTEM_MANAGER_ROLE in roles:
		return

	has_role = ORGANISATION_MANAGER_ROLE in roles
	if org_id is None:
		org_id = frappe.db.get_value("User Metadata", user, "org_id")

	desired = org_id if (has_role and org_id) else None
	existing = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": USER_ORGANIZATION_DOCTYPE},
		fields=["name", "for_value"],
	)

	if desired is None:
		for perm in existing:
			frappe.delete_doc("User Permission", perm.name, ignore_permissions=True)
		return

	has_matching = False
	for perm in existing:
		if perm.for_value == desired:
			has_matching = True
		else:
			frappe.delete_doc("User Permission", perm.name, ignore_permissions=True)

	if not has_matching:
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": USER_ORGANIZATION_DOCTYPE,
				"for_value": desired,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)


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