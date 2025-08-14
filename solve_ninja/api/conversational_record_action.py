import frappe

@frappe.whitelist(allow_guest=True)
def resume_glific_flow(flow_id,contact_id,data):
    glific_settings = frappe.get_doc("Glific Settings")
    return glific_settings.resume_glific_flow(flow_id,contact_id,data)