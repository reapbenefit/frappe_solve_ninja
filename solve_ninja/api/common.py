import json
import frappe
from werkzeug.wrappers import Response

from frappe.utils import logger
logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)


def update_user_profile(doc, _):
    logger.info("update user progile")
    return True
    response = Response()
    response.mimetype = 'application/json'
    response.charset = 'utf-8'
    response.status_code = status_code
    status = "error" if error else "success"
    response.data = json.dumps(
        {"message": message, "status": status, "data": data}, default=str)
    return response


def has_permission(doc, user=None, permission_type=None):
    logger.info("Checking permission")
    roles = frappe.get_roles(frappe.session.user)
    logger.info(f"getting roles {roles}")
    if "System Manager" in roles:
        return True
    if doc.user == frappe.session.user:
        logger.info("returning true")
        return True
    return False
