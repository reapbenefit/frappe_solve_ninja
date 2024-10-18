import frappe
from frappe.query_builder.functions import Count, Sum

def get_active_ninja_count():
	return frappe.db.count("User", {"enabled": 1})

def get_action_count():
	return frappe.db.count("Events")

def get_total_invested_hours():
	Events = frappe.qb.DocType("Events")
	query = (
		frappe.qb.from_(Events)
		.select(
			Sum(Events.hours_invested).as_("hours_invested"),
		)
	)
	result = query.run(as_dict=True)
	if not result:
		return 0

	return result[0]["hours_invested"]

@frappe.whitelist(allow_guest=True)
def get_city_wise_action_count(page_length=10):
	Events = frappe.qb.DocType("Events")
	Location = frappe.qb.DocType("Location")

	query = (
		frappe.qb.from_(Events)
		.join(Location)
		.on(Events.location == Location.name)
		.select(
			Count(Events.name).as_("action_count"),
			Location.city.as_("city")
		)
		.where(
			Location.city.isnotnull()
		)
		.groupby(
			Location.city
		).orderby(
			Count(Events.name), order=frappe.qb.desc
		).limit(page_length)
	)

	# Run the query with debug enabled
	result = query.run(as_dict=True)
	all_actions = get_action_count()

	total_actions = [row.action_count for row in result]
	total_actions = sum(total_actions)
	for row in result:
		row.percentage = frappe.utils.cint((row.action_count/total_actions) * 100)

	return result

@frappe.whitelist(allow_guest=True)
def get_state_wise_user_count(page_length=10):
	# Events = frappe.qb.DocType("Events")
	# Location = frappe.qb.DocType("Location")

	result = frappe.db.get_all('User',
		filters={
			'enabled': 1,
			'state': ('is', 'set')
		},
		fields=['count(name) as user_count', 'state'],
		group_by='state',
		order_by='count(name) desc',
		page_length=page_length
	)
	# query = (
	# 	frappe.qb.from_(Events)
	# 	.join(Location)
	# 	.on(Events.location == Location.name)
	# 	.select(
	# 		Count(Events.name).as_("action_count"),
	# 		Location.city.as_("city")
	# 	)
	# 	.where(
	# 		Location.city.isnotnull()
	# 	)
	# 	.groupby(
	# 		Location.city
	# 	).orderby(
	# 		Count(Events.name), order=frappe.qb.desc
	# 	).limit(page_length)
	# )

	# Run the query with debug enabled
	# result = query.run(as_dict=True)
	# all_actions = get_action_count()

	total_users = [row.user_count for row in result]
	total_users = sum(total_users)
	for row in result:
		row.percentage = frappe.utils.cint((row.user_count/total_users) * 100)

	return result