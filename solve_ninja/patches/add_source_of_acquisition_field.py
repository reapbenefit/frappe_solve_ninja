# Copyright (c) 2024, ReapBenefit and contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Add source_of_acquisition custom field to User doctype"""
	custom_fields = {
		"User": [
			{
				"fieldname": "source_of_acquisition",
				"fieldtype": "Data",
				"label": "Source of Acquisition",
				"insert_after": "username",
				"module": "Solve Ninja"
			}
		]
	}
	
	create_custom_fields(custom_fields)
