"""
Exempt mentorship chatbot API endpoints from CSRF validation.

The mentor chatbot is called from the marketplace frontend (Vue SPA) via POST
without a Frappe session/CSRF token. These endpoints are whitelisted with
allow_guest=True and are safe to exempt so the chatbot works from the deployed app.
"""
import frappe

_MENTORSHIP_CMDS = (
    "solve_ninja.api.v1.mentorship_request.initiate_mentorship_request",
    "solve_ninja.api.v1.mentorship_request.continue_mentorship_request",
)

_orig_validate_csrf = frappe.auth.HTTPRequest.validate_csrf_token


def _validate_csrf_token(self):
    form_dict = getattr(frappe.local, "form_dict", None) or {}
    cmd = form_dict.get("cmd") or ""
    if cmd in _MENTORSHIP_CMDS:
        return
    return _orig_validate_csrf(self)


frappe.auth.HTTPRequest.validate_csrf_token = _validate_csrf_token
