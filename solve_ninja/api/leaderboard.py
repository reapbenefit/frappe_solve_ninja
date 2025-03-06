import frappe
from frappe.query_builder.functions import Count, Sum
from frappe import qb

states_of_india = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", ""
]

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
			(Location.city.isnotnull()) & (Location.city.notin(["NULL"]))
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
def get_city_wise_action_count_user_based(page_length=10):
	Events = frappe.qb.DocType("Events")
	User = frappe.qb.DocType("User")

	user_with_events = (
		frappe.qb.from_(User)
		.join(Events).on(Events.user == User.name)  # assuming 'user' field in Events points to User's 'name'
		.select(User.name)  # selecting the desired fields
		.where(
			(User.city.isnotnull()) &  # Ensure city is not null
			(User.city.notin(states_of_india)) &  # Exclude cities in the list
			(Events.name.isnotnull())  # Ensure events exist for the user
		)
	)
	user_with_events = user_with_events.run(as_dict=True)
	users = list(set([user.name for user in user_with_events]))

	# Query to get the number of users grouped by city, with conditions on a list of usernames
	user_count_by_city = (
		qb.from_(User)
		.select(User.city, Count(User.name).as_("action_count"))  # count users per city
		.where(
			User.name.isin(users)  # filter by a list of usernames
		)
		.groupby(User.city)  # group by user city
		.orderby(
			Count(User.name), order=frappe.qb.desc  # Order cities alphabetically
		)
		.limit(page_length)  # limit to 10 results
	)

	# Execute the query and fetch the results
	result = user_count_by_city.run(as_dict=True)

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