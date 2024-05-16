# Copyright (c) 2024, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_columns():
	columns = [
		{
			"label": _("User"),
			"options": "User",
			"fieldname": "user",
			"fieldtype": "Link" ,
			"width": 180,
		},
		{
			"label": _("Event"),
			"options": "Events",
			"fieldname": "event",
			"fieldtype": "Link" ,
			"width": 100,
		},
		{
			"label": _("Location"),
			"options": "Location",
			"fieldname": "location",
			"fieldtype": "Link" ,
			"width": 100,
		},
		{
			"label": _("Title"),
			"fieldname": "title",
			"fieldtype": "Data" ,
			"width": 140,
		},
		{
			"label": _("Type"),
			"fieldname": "type",
			"fieldtype": "Data" ,
			"width": 140,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data" ,
			"width": 70,
		},
		{
			"label": _("Category"),
			"fieldname": "category",
			"fieldtype": "Data" ,
			"width": 120,
		},
		{
			"label": _("Sub Category"),
			"fieldname": "subcategory",
			"fieldtype": "Data" ,
			"width": 100,
		},
		{
			"label": _("Hours Invested"),
			"fieldname": "hours_invested",
			"fieldtype": "Data" ,
			"width": 120,
		},
	]

	return columns


def get_data(filters):
	User = frappe.qb.DocType("User")
	Events = frappe.qb.DocType("Events")

	query = (frappe.qb.from_(Events)
		.inner_join(User)
		.on(Events.user == User.name)
		.select(
			Events.name.as_("event"),
			User.name.as_("user"),
			Events.title.as_("title"),
			Events.type.as_("type"),
			Events.status.as_("status"),
			Events.category.as_("category"),
			Events.subcategory.as_("subcategory"),
			Events.location.as_("location"),
			Events.hours_invested.as_("hours_invested"),
		).where(
			User.enabled == 1
		).where(
			Events.creation.between(filters.from_date, filters.to_date)
		))
	
	if filters.get("have_location"):
		query = query.where(Events.location.isnotnull())
	
	result = query.run(as_dict=True)
	return result