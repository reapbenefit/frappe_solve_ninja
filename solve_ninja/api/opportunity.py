import frappe

@frappe.whitelist(allow_guest=True)
def get_opportunity_type(opportunity_title):
    doc = frappe.get_doc("Opportunity Template", {"title": opportunity_title})
    return doc.opp_type

@frappe.whitelist(allow_guest=True)
def get_opportunity_by_route(opportunity_route):
    doc = frappe.get_doc("Opportunity Template", {"route": opportunity_route})
    return doc

@frappe.whitelist(allow_guest=True)
def get_opportunity_by_title(opportunity_title):
    doc = frappe.get_doc("Opportunity Template", {"title": opportunity_title})
    return doc

@frappe.whitelist(allow_guest=True)
def get_opportunity_doc(opportunity_type):
    doc = frappe.get_doc("Opportunity Type", {"type": opportunity_type})
    return doc

