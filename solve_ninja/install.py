# Copyright (c) 2024, ReapBenefit and contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	"""Create custom fields after app installation"""
	create_custom_fields_from_hooks()


def after_migrate():
	"""Create custom fields after migration"""
	create_custom_fields_from_hooks()


def create_custom_fields_from_hooks():
	"""Create custom fields defined in hooks.py"""
	from solve_ninja import hooks
	
	if hasattr(hooks, "custom_fields") and hooks.custom_fields:
		create_custom_fields(hooks.custom_fields)
