import frappe
from frappe.www.login import get_context as original_get_context


def get_context(context):
	"""
	Override the login context to use our custom mobile OTP login template
	"""
	# Call the original get_context to get all the standard context
	original_get_context(context)
	
	# Override the template to use our custom mobile OTP login
	context["template"] = "solve_ninja/overrides/login.html"
	
	return context

