import frappe
<<<<<<< HEAD
import json
=======
>>>>>>> refs/remotes/origin/master
from frappe.utils import flt
from open_civic_backend.api.common import custom_response

PRECISION = 8

<<<<<<< HEAD
@frappe.whitelist(allow_guest=True)
def new(lat, long):
=======

@frappe.whitelist(allow_guest=True)
def new(lat, long):
    """Allow guests to add a location"""
>>>>>>> refs/remotes/origin/master
    try:
        lat = str(flt(lat, PRECISION))
        long = str(flt(long, PRECISION))
        if not lat or not long:
            frappe.throw("lat and longs are mandatory")

<<<<<<< HEAD
        loc_name = frappe.db.exists(
            "Location",
=======
        # Check if lat long already exists
        # TODO:: Need to have common precision
        # or some better way to avoid duplicates
        loc_name = frappe.db.exists(
            "Locations",
>>>>>>> refs/remotes/origin/master
            {
                "latitude": lat,
                "longitude": long,
            },
        )
        if loc_name:
<<<<<<< HEAD
            return frappe.get_doc("Location", loc_name).as_dict()

        loc = frappe.get_doc(
            {
                "doctype": "Location",
=======
            return frappe.get_doc("Locations", loc_name).as_dict()

        # Create new location based on lat long
        loc = frappe.get_doc(
            {
                "doctype": "Locations",
>>>>>>> refs/remotes/origin/master
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
