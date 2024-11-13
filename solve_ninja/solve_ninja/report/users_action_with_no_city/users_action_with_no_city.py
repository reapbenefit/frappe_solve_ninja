# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Count

def execute(filters=None):
	Events = frappe.qb.DocType("Events")
	User = frappe.qb.DocType("User")
	Location = frappe.qb.DocType("Location")

	columns = [
		{
			"label": "User",
			"fieldname": "user",
			"fieldtype": "Link",
			"options": "User",
			"width": 180,
		},
		{
			"label": "Total Action",
			"fieldname": "actions",
			"fieldtype": "Int",
			"width": 180,
		}
	]
	query = (
		frappe.qb.from_(User)
		.join(Events)
		.on(User.name == Events.user)
		.left_join(Location)
		.on(Events.location == Location.name)
		.select(
			Count(Events.name).as_("actions"),
			User.name.as_("user")
		)
		.where(
			Location.city.isnull()
		)
		.groupby(
			User.name
		).orderby(
			Count(Events.name), order=frappe.qb.desc
		)
	)

	# Run the query with debug enabled
	result = query.run(as_dict=True)
	return columns, result
