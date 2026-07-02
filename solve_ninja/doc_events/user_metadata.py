# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from solve_ninja.api.common import fetch_data_gov_in

@frappe.whitelist()
def update_user_metadata_location(doc):
    """
    Enqueue-safe method to update location (city, state) from pincode.
    """
    location_data = fetch_data_gov_in(doc.pincode)
    if location_data.get("records"):
        record = location_data["records"][0]
        city = record["district"].title()
        state = record["statename"].title()

        # Create city if not exists
        if not frappe.db.exists('Samaaja Cities', {'city_name': city}):
            frappe.get_doc({
                'doctype': 'Samaaja Cities',
                'city_name': city
            }).insert(ignore_permissions=True)

        doc.city = city
        doc.state = state

def on_save(doc, method):
    """
    Hook to update location fields when User Metadata is saved.
    """
    if doc.pincode and (not doc.city or not doc.state):
        try:
            update_user_metadata_location(doc)
        except Exception as e:
            frappe.log_error(message=f"Error updating user metadata location: {e}", title="Update User Metadata Location Error")
    
    update_mentor_role(doc)

    if doc.is_new() or doc.has_value_changed("org_id"):
        from solve_ninja.doc_events.user import sync_organisation_manager_permission

        sync_organisation_manager_permission(doc.user, org_id=doc.org_id)


def update_mentor_role(doc):
    """
    Syncs the 'Mentor' role on the User document based on the 'is_mentor' field.
    """
    user_roles = frappe.get_roles(doc.user)
    has_mentor_role = "Mentor" in user_roles

    if doc.is_mentor and not has_mentor_role:
        user = frappe.get_doc("User", doc.user)
        user.module_profile = "Mentor"
        user.save(ignore_permissions=True)
        user.add_roles("Mentor")
    
    elif not doc.is_mentor and has_mentor_role:
        user = frappe.get_doc("User", doc.user)
        user.remove_roles("Mentor")
        