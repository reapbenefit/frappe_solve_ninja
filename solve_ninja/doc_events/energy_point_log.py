import frappe
import requests
import json
from solve_ninja.api.user import validate_and_normalize_mobile
from time import sleep

def handle_energy_point_log(doc, method):
    """
    Handle Energy Point Log creation and trigger badge notification.
    Only triggers notification for Events documents and ensures only one notification per event.
    """
    # Only process Auto type Energy Point Logs with badges for Events documents
    if doc.type != "Auto" or not doc.badge or not doc.user:
        return
    
    if doc.reference_doctype != "Events" or not doc.reference_name:
        return
    
    # Use cache key to prevent duplicate notifications for the same event
    cache_key = f"badge_notification_sent_{doc.reference_name}"
    
    # Check if notification was already enqueued for this event
    if frappe.cache().get(cache_key):
        return
    
    # Verify Events document exists and check source
    try:
        events_doc = frappe.get_doc("Events", doc.reference_name)
        # Check if source should be excluded
        if events_doc.source and events_doc.source in ["SamaajData", "manualupload"]:
            return
    except frappe.DoesNotExistError:
        return
    
    # Set cache key immediately to prevent other EPS from triggering duplicate notifications
    frappe.cache().setex(cache_key, 300, "1")  # 5 minutes expiry
    
    # Enqueue notification - this will collect all EPS for the event
    frappe.enqueue(
        "solve_ninja.doc_events.energy_point_log.send_badge_notification",
        event_name=doc.reference_name,
        now=False  # run in background
    )

# def send_badge_notification(energy_point_log):
#     solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
#     if energy_point_log.reference_doctype != "Events" or not solve_ninja_settings.enable_badge_notification:
#         # Skip if not an event or notifications are disabled
#         return
#     try:
#         doc = frappe.get_doc("Energy Point Log", energy_point_log.name) if isinstance(energy_point_log, dict) else energy_point_log
#         user = frappe.get_doc("User", doc.user)
#         event = frappe.get_doc("Events", doc.reference_name)
#         ninja_profile = frappe.get_doc("Ninja Profile", doc.user, for_update=False)
#         user_metadata = frappe.get_doc("User Metadata", doc.user)
#         badge = frappe.get_doc("Badge", doc.badge)
#         user_badge = frappe.get_doc("User badge", {"user": doc.user, "badge": doc.badge})

#         # Resolve template
#         badge_template = None
#         if badge.template:
#             badge_template = frappe.get_doc("Badge Template", badge.template)
#         else:
#             # Fallback to default badge template if no specific template is set
#             badge_template = frappe.get_doc("Badge Template", solve_ninja_settings.default_badge_template)

#         if not badge_template or not badge_template.parameters_json:
#             frappe.log_error("No valid badge template found", "Badge Notification Error")
#             return

#         # Context including Energy Point Log
#         context = {
#             "user": user,
#             "ninja_profile": ninja_profile,
#             "user_metadata": user_metadata,
#             "badge": badge,
#             "user_badge": user_badge,
#             "energy_point_log": doc,
#             "event": event,
#         }

#         if solve_ninja_settings.channel == "Glific" and user.mobile_no:
#             glific_settings = frappe.get_doc("Glific Settings")
#             if not ninja_profile.wa_id:
#                 mobile_no = validate_and_normalize_mobile(user.mobile_no)
#                 response = glific_settings.get_contact_by_phone(mobile_no)
#                 contact_id = (
#                     response
#                     .get('data', {})
#                     .get('contactByPhone', {})
#                     .get('contact', {})
#                     .get('id')
#                 )
#                 if contact_id:
#                     ninja_profile.db_set("wa_id", contact_id, commit=True)
#                     ninja_profile.reload()
#             if ninja_profile.wa_id:
#                 parameters = json.loads(frappe.render_template(badge_template.parameters_json, context))
#                 glific_settings.send_hsm_message(ninja_profile.wa_id, badge_template.template_id, parameters)

#     except Exception:
#         frappe.log_error(frappe.get_traceback(), "Badge Notification Error")

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

def send_badge_notification_after_insert(doc, method=None):
    """
    Fallback hook that triggers badge notification when Events document is created.
    This is a fallback in case Energy Point Logs are created before this hook runs.
    Checks cache to avoid duplicate notifications if handle_energy_point_log already triggered it.
    """
    if not doc.user or not doc.source or doc.source in ["SamaajData", "manualupload"]:
        return
    
    # Check if notification was already enqueued by handle_energy_point_log
    cache_key = f"badge_notification_sent_{doc.name}"
    if frappe.cache().get(cache_key):
        return
    
    # Set cache to prevent duplicate if Energy Point Logs trigger later
    frappe.cache().setex(cache_key, 300, "1")  # 5 minutes expiry
    
    # Enqueue notification as fallback
    frappe.enqueue(
        "solve_ninja.doc_events.energy_point_log.send_badge_notification",
        event_name=doc.name,
        events=doc,
        now=False  # run in background
    )

def send_badge_notification(event_name, events=None):
    """
    Send badge notification for an Events document.
    Collects all Energy Point Logs for the event and sends one notification with all badges.
    
    Args:
        event_name: Name of the Events document (required)
        events: Events document object (optional, for backward compatibility)
    """
    solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
    if not solve_ninja_settings.enable_badge_notification:
        return
    
    # Small delay to allow all Energy Point Logs to be created
    sleep(3)
    
    # Get the Events document if not provided
    if not events:
        try:
            events = frappe.get_doc("Events", event_name)
        except frappe.DoesNotExistError:
            frappe.log_error(f"Events document {event_name} not found", "Badge Notification Error")
            return
    
    # Query all Energy Point Logs for this event
    eps = frappe.get_all("Energy Point Log", filters={
        "reference_doctype": "Events",
        "reference_name": event_name,
        "type": "Auto",
        "badge": ("is", "set")
    }, fields=["*"])

    if not eps:
        # Clear cache key if no EPS found
        cache_key = f"badge_notification_sent_{event_name}"
        frappe.cache().delete(cache_key)
        return

    # Validate Events document has required fields
    if not events.user:
        return
    
    # Check if source should be excluded
    if events.source and events.source in ["SamaajData", "manualupload"]:
        return

    try:
        user = frappe.get_doc("User", events.user)
        ninja_profile = frappe.get_doc("Ninja Profile", events.user, for_update=False)
        user_metadata = frappe.get_doc("User Metadata", events.user)

        badge_template = frappe.get_doc("Badge Template", solve_ninja_settings.default_badge_template)

        if not badge_template or not badge_template.parameters_json:
            frappe.log_error("No valid badge template found", "Badge Notification Error")
            return

        # Context including all Energy Point Logs
        context = {
            "user": user,
            "ninja_profile": ninja_profile,
            "user_metadata": user_metadata,
            "eps": eps,
            "event": events,
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
        
        # Clear cache key after successful notification
        cache_key = f"badge_notification_sent_{event_name}"
        frappe.cache().delete(cache_key)
        
    except Exception as e:
        frappe.log_error(f"Error sending badge notification for event {event_name}: {str(e)}", "Badge Notification Error")
        # Clear cache key on error so it can be retried
        cache_key = f"badge_notification_sent_{event_name}"
        frappe.cache().delete(cache_key)

