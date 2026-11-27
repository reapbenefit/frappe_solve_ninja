import frappe


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
