# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import functions as fn

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
	# Subquery to find users with events that have locations with a city
	users_with_city = (
		frappe.qb.from_(User)
		.join(Events).on(User.name == Events.user)
		.join(Location).on(Events.location == Location.name)
		.select(User.name)
		.where(Location.city.isnotnull())  # Filters for events with a city in the location
	)

	# Main query to get users with events but exclude those with any location having a city
	query = (
		frappe.qb.from_(User)
		.join(Events).on(User.name == Events.user)
		.left_join(Location).on(Events.location == Location.name)
		.select(
			fn.Count(Events.name).as_("actions"),
			User.name.as_("user")
		)
		.where(
			User.name.notin(users_with_city)  # Excludes users who have events with locations that have a city
		)
		.groupby(User.name)
		.having(
			fn.Count(Events.name) > 0  # Ensures the user has at least one event
		)
		.orderby(fn.Count(Events.name), order=frappe.qb.desc)
	)

	# Run the query with debug enabled
	result = query.run(as_dict=True)
	return columns, result