import frappe
from frappe.www.login import get_context as original_get_context
from frappe.website.utils import get_home_page
from solve_ninja.www.signup_utils import (
	apply_checkin_context,
	apply_signup_form_context,
	get_checkin_redirect,
)

no_cache = True


def get_context(context):
	"""
	Custom login context for mobile OTP login
	"""
	code = frappe.local.request.args.get("code")

	# Check if user is already logged in
	if frappe.session.user != "Guest":
		# Get redirect URL from query params or use default
		redirect_to = frappe.local.request.args.get("redirect-to")
		redirect_to = sanitize_redirect(redirect_to)

		if code:
			frappe.local.flags.redirect_location = get_checkin_redirect(code, redirect_to)
			raise frappe.Redirect
		
		if not redirect_to:
			if frappe.session.data.user_type == "Website User":
				redirect_to = get_home_page()
			else:
				redirect_to = "/desk"
		
		frappe.local.flags.redirect_location = redirect_to
		raise frappe.Redirect
	
	# Call the original get_context to get all the standard context
	original_get_context(context)
	
	# Override specific context for mobile OTP login
	context["title"] = "Mobile Login - Solve Ninja"
	context["disable_user_pass_login"] = 1  # Disable email/password login
	context["disable_signup"] = 0  # Allow signup
	apply_signup_form_context(context)
	apply_checkin_context(context, code)
	
	return context


def sanitize_redirect(redirect: str | None) -> str | None:
	"""Only allow redirect on same domain."""
	if not redirect:
		return redirect
	
	from urllib.parse import urlparse
	parsed_redirect = urlparse(redirect)
	if not parsed_redirect.netloc:
		return redirect
	
	parsed_request_host = urlparse(frappe.local.request.url)
	if parsed_request_host.netloc == parsed_redirect.netloc:
		return redirect
	
	return None
