from math import log, floor
import frappe
from frappe import _

def human_format(number):
	units = ['', 'K', 'M', 'G', 'T', 'P']
	k = 1000.0
	magnitude = int(floor(log(number, k)))
	return '%.2f%s' % (number / k**magnitude, units[magnitude])

def validate_and_normalize_mobile(mobile):
    if not mobile or len(mobile) not in [10, 12] or not mobile.isdigit():
        frappe.throw(_("Mobile number must be either 10 or 12 digits and numeric."))

    if len(mobile) == 10:
        mobile = "91" + mobile

    return mobile