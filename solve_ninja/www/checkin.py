from urllib.parse import urlencode

import frappe

from solve_ninja.services.unique_code import resolve_unique_code
from solve_ninja.www.login import sanitize_redirect

no_cache = True


def get_context(context):
	"""
	Website check-in link: /checkin?code=<Program / Solve Event / Social Media unique_id>.

	Guests are sent to /login with the code so they can sign up or log in.
	Logged-in users get the code applied by a POST from this page (GET requests never write).
	"""
	args = frappe.local.request.args
	code = args.get("code")
	redirect_to = sanitize_redirect(args.get("redirect-to"))

	if frappe.session.user == "Guest":
		params = {"code": code} if code else {}
		if redirect_to:
			params["redirect-to"] = redirect_to
		frappe.local.flags.redirect_location = f"/login?{urlencode(params)}#login"
		raise frappe.Redirect

	if not redirect_to:
		if frappe.session.data.user_type == "Website User":
			redirect_to = "/user-profile/me"
		else:
			redirect_to = "/desk"

	target = resolve_unique_code(code)
	context.no_cache = 1
	context.title = "Check in - Solve Ninja"
	context.checkin_code = target["code"] if target else ""
	context.checkin_title = target["title"] if target else ""
	context.redirect_to = redirect_to
	return context
