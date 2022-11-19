import frappe
from frappe.utils import flt
from open_civic_backend.api.common import custom_response

PRECISION = 8


@frappe.whitelist(allow_guest=True)
def new(lat, long):
    try:
        lat = str(flt(lat, PRECISION))
        long = str(flt(long, PRECISION))
        if not lat or not long:
            frappe.throw("lat and longs are mandatory")

        loc_name = frappe.db.exists(
            "Locations",
            {
                "latitude": lat,
                "longitude": long,
            },
        )
        if loc_name:
            return frappe.get_doc("Locations", loc_name).as_dict()

        loc = frappe.get_doc(
            {
                "doctype": "Locations",
                "latitude": lat,
                "longitude": long,
            }
        )
        loc.insert(ignore_permissions=True)
        loc = loc.as_dict()
        return loc
    except Exception as e:
        frappe.db.rollback()
        return custom_response(str(e), None, 500, True)
