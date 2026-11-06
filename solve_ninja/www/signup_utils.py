from urllib.parse import parse_qs, unquote, urlencode, urlparse

import frappe

from solve_ninja.services.unique_code import WEB_CHECKIN_PATH, resolve_unique_code


def get_signup_states():
	"""Return Samaaja States names for signup selects."""
	return frappe.get_all(
		"Samaaja States",
		pluck="name",
		order_by="name",
		ignore_permissions=True,
	)


def render_signup_form_template():
	"""Render custom signup template with states list."""
	return frappe.get_template("solve_ninja/templates/signup.html").render(
		{"states": get_signup_states()}
	)


def apply_signup_form_context(context):
	"""Override Frappe's empty signup_form_template render with states."""
	context["signup_form_template"] = render_signup_form_template()
	return context


def get_checkin_redirect(code, redirect_to=None):
	"""URL of the /checkin page that applies a code for a logged-in user."""
	params = {"code": code}
	if redirect_to:
		params["redirect-to"] = redirect_to
	return f"{WEB_CHECKIN_PATH}?{urlencode(params)}"


def get_code_from_redirect(redirect_to):
	"""Return the code from a redirect-to that points at /checkin?code=..., else None."""
	if not redirect_to:
		return None
	parsed = urlparse(unquote(redirect_to))
	if parsed.path != WEB_CHECKIN_PATH:
		return None
	return (parse_qs(parsed.query).get("code") or [None])[0]


def apply_checkin_context(context, code):
	"""Expose the check-in target (if the code is valid) so the login page can show it."""
	target = resolve_unique_code(code)
	context["checkin_code"] = target["code"] if target else ""
	context["checkin_title"] = target["title"] if target else ""
	return context
