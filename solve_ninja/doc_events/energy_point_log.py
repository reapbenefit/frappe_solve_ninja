import frappe
import requests
import json
from solve_ninja.utils import validate_and_normalize_mobile

def handle_energy_point_log(doc, method):
    if doc.type == "Auto" and doc.badge and doc.user:
        # Delay the notification slightly to ensure User Badge is updated
        frappe.enqueue(
            "solve_ninja.doc_events.energy_point_log.send_badge_notification",
            energy_point_log=doc,
            now=False  # run in background
        )

def send_badge_notification(energy_point_log):
    solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
    if energy_point_log.reference_doctype != "Events" or not solve_ninja_settings.enable_badge_notification:
        # Skip if not an event or notifications are disabled
        return
    try:
        doc = frappe.get_doc("Energy Point Log", energy_point_log.name) if isinstance(energy_point_log, dict) else energy_point_log
        user = frappe.get_doc("User", doc.user)
        event = frappe.get_doc("Events", doc.reference_name)
        ninja_profile = frappe.get_doc("Ninja Profile", doc.user, for_update=False)
        user_metadata = frappe.get_doc("User Metadata", doc.user)
        badge = frappe.get_doc("Badge", doc.badge)
        user_badge = frappe.get_doc("User badge", {"user": doc.user, "badge": doc.badge})

        # Resolve template
        badge_template = None
        if badge.template:
            badge_template = frappe.get_doc("Badge Template", badge.template)
        else:
            # Fallback to default badge template if no specific template is set
            badge_template = frappe.get_doc("Badge Template", solve_ninja_settings.default_badge_template)

        if not badge_template or not badge_template.parameters_json:
            frappe.log_error("No valid badge template found", "Badge Notification Error")
            return

        # Context including Energy Point Log
        context = {
            "user": user,
            "ninja_profile": ninja_profile,
            "user_metadata": user_metadata,
            "badge": badge,
            "user_badge": user_badge,
            "energy_point_log": doc,
            "event": event,
        }

        if solve_ninja_settings.channel == "Glific" and user.mobile_no:
            glific_settings = frappe.get_doc("Glific Settings")
            if not ninja_profile.wa_id:
                mobile_no = validate_and_normalize_mobile(user.mobile_no)
                response = glific_settings.get_contact_by_phone(mobile_no)
                contact_id = (
                    response
                    .get('data', {})
                    .get('contactByPhone', {})
                    .get('contact', {})
                    .get('id')
                )
                if contact_id:
                    ninja_profile.db_set("wa_id", contact_id, commit=True)
                    ninja_profile.reload()
            if ninja_profile.wa_id:
                parameters = json.loads(frappe.render_template(badge_template.parameters_json, context))
                glific_settings.send_hsm_message(ninja_profile.wa_id, badge_template.template_id, parameters)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Badge Notification Error")

def send_glific_message(doc, url, headers, data):
    response = None
    error = None
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
    except Exception:
        error = frappe.get_traceback()
        frappe.log_error(error, "Glific Message Send Error")
    finally:
        log_glific_integration_request(doc, url, headers, data, response.json() if response else None, error)


def log_glific_integration_request(doc, url, headers, data, response, error=None):
    frappe.get_doc({
        "doctype": "Integration Request",
        "integration_request_service": "Glific HSM",
        "is_remote_request": 1,
        "url": url,
        "request_headers": frappe.as_json(headers),
        "data": frappe.as_json(data),
        "output": frappe.as_json(response) if response else "",
        "error": frappe.as_json(error) if error else "",
        "status": "Completed" if response and not error else "Failed",
        "reference_doctype": doc.doctype,
        "reference_docname": doc.name,
        "request_description": "Send WhatsApp HSM message via Glific",
    }).insert(ignore_permissions=True)
