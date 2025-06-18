import frappe
import requests

def handle_energy_point_log(doc, method):
    if doc.type == "Auto" and doc.badge and doc.user:
        # Delay the notification slightly to ensure User Badge is updated
        frappe.enqueue(
            "solve_ninja.doc_events.energy_point_log.send_badge_notification",
            energy_point_log=doc,
            now=False  # run in background
        )
    
def send_badge_notification(energy_point_log):
    try:
        doc = frappe.get_doc("Energy Point Log", energy_point_log.name) if isinstance(energy_point_log, dict) else energy_point_log
        user = frappe.get_doc("User", doc.user)
        ninja_profile = frappe.get_doc("Ninja Profile", doc.user)
        user_metadata = frappe.get_doc("User Metadata", doc.user)
        badge = frappe.get_doc("Badge", doc.badge)
        user_badge = frappe.get_doc("User badge", {"user": doc.user, "badge": doc.badge})

        # Resolve template
        badge_template = None
        if badge.template:
            badge_template = frappe.get_doc("Badge Template", badge.template)
        else:
            default_template = frappe.db.get_single_value("Solve Ninja Settings", "default_badge_template")
            if default_template:
                badge_template = frappe.get_doc("Badge Template", default_template)

        if not badge_template or not badge_template.message:
            frappe.log_error("No valid badge template found", "Badge Notification Error")
            return

        # Context including Energy Point Log
        context = {
            "user": user,
            "ninja_profile": ninja_profile,
            "user_metadata": user_metadata,
            "badge": badge,
            "user_badge": user_badge,
            "energy_point_log": doc
        }

        message = frappe.render_template(badge_template.message, context)

        # Channel logic
        channel = frappe.db.get_single_value("Solve Ninja Settings", "badge_notification_channel")

        if channel == "Webhook":
            webhook_url = frappe.db.get_single_value("Solve Ninja Settings", "badge_webhook_url")
            if webhook_url:
                frappe.enqueue(
                    "solve_ninja.doc_events.energy_point_log.send_custom_webhook",
                    doc=user,
                    webhook_url=webhook_url,
                    data={
                        "message": message,
                        "user": user.name,
                        "badge": badge.name,
                        "points": doc.points
                    }
                )

        # Extend for Slack / WhatsApp if needed

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Badge Notification Error")

def send_custom_webhook(doc, webhook_url, data):
    try:
        response = requests.post(webhook_url, json=data, timeout=10)
        response.raise_for_status()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Custom Webhook Failed")