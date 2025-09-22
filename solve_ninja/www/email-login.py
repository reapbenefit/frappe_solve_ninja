import frappe
from frappe.www.login import get_context as original_get_context
from frappe.website.utils import get_home_page


def get_context(context):
	"""
	Custom login context for email/password login
	"""
	# Check if user is already logged in
	if frappe.session.user != "Guest":
		# Get redirect URL from query params or use default
		redirect_to = frappe.local.request.args.get("redirect-to")
		redirect_to = sanitize_redirect(redirect_to)
		
		if not redirect_to:
			if frappe.session.data.user_type == "Website User":
				redirect_to = get_home_page()
			else:
				redirect_to = "/app"
		
		frappe.local.flags.redirect_location = redirect_to
		raise frappe.Redirect
	
	# Call the original get_context to get all the standard context
	original_get_context(context)
	
	# Override specific context for email/password login
	context["title"] = "Email Login - Solve Ninja"
	context["disable_user_pass_login"] = 0  # Enable email/password login
	context["disable_signup"] = 0  # Allow signup
	
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
