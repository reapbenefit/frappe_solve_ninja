import frappe
import json
from frappe.utils import cint, flt, now_datetime
from frappe import qb
from frappe.query_builder import DocType, Order
from frappe.query_builder.functions import Coalesce, Sum, Count, Lower
from datetime import timedelta
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_top_reviewed_users(page_length=10, start=0, days=30, filters=None):
	"""
	Get top users with their recent activity based on specified days.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- days: Number of days for recent rank calculation (default: 30)
	- filters: JSON string containing additional filters (optional)
	
	Returns:
	- User data with recent activity
	"""
	try:
		start = cint(start)
		page_length = cint(page_length)
		days = cint(days)
		
		filters = json.loads(filters) if filters else {}

		# Define Doctypes
		User = DocType("User")
		Events = DocType("Events")
		NinjaProfile = DocType("Ninja Profile")
		UserMetadata = DocType("User Metadata")

		# Calculate time condition based on days
		time_condition = now_datetime() - timedelta(days=days)

		# Base Query: Always Fetch Rank from `Ninja Profile`
		user_count = frappe.db.count("User", {"enabled": 1})
		query = (
			frappe.qb.from_(User)
			.join(NinjaProfile).on(User.name == NinjaProfile.name)
			.join(UserMetadata).on(User.name == UserMetadata.name)
			.join(Events).on(User.name == Events.user)
			.select(
				User.name,
				User.username,
				User.user_image,
				User.headline,
				UserMetadata.city,
				Coalesce(NinjaProfile.rank, user_count).as_("rank"),
				User.org_id,
				User.user_image,
				User.location,
				User.full_name,
				Coalesce(Sum(Events.hours_invested), 0).as_("hours_invested"),
				Coalesce(Count(Events.user), 0).as_("contribution_count"),
				Sum(Events.hours_invested).as_("recent_rank")
			)
			.distinct()
			.where(
				(User.enabled == 1) &
				(NinjaProfile.rank != 0) &
				(Events.creation >= frappe.utils.format_datetime(time_condition, "yyyy-MM-dd HH:mm:ss"))
			)
			.groupby(
				User.name, User.username, UserMetadata.city, User.org_id, User.user_image, 
				User.location, User.full_name, NinjaProfile.rank
			)
			.orderby(Sum(Events.hours_invested), order=Order.desc)
			.orderby(User.full_name, order=Order.asc)
		)
		
		# Apply Filters Dynamically
		if filters.get("organization"):
			query = query.where(User.org_id == filters["organization"])
		
		if filters.get("city"):
			query = query.where(User.city == filters["city"])

		if filters.get("ninja"):
			full_name_filter = f"%{filters['ninja'].lower()}%"
			query = query.where(Lower(User.full_name).like(full_name_filter))
		
		# Apply hour range filter
		if filters.get("hr_range"):
			if "-" in filters.get("hr_range"):
				min_hr, max_hr = map(flt, filters.get("hr_range").split("-"))
				query = query.having(Coalesce(Sum(Events.hours_invested), 0).between(min_hr, max_hr))
			
			elif "+" in filters.get("hr_range"):
				min_hr = flt(filters.get("hr_range").replace("+", ""))
				query = query.having(Coalesce(Sum(Events.hours_invested), 0) > min_hr)

		# Get total count for pagination
		count_query = (
			frappe.qb.from_(User)
			.join(NinjaProfile).on(User.name == NinjaProfile.name)
			.join(UserMetadata).on(User.name == UserMetadata.name)
			.join(Events).on(User.name == Events.user)
			.select(Count(User.name).distinct().as_("total"))
			.where(
				(User.enabled == 1) &
				(NinjaProfile.rank != 0) &
				(Events.creation >= frappe.utils.format_datetime(time_condition, "yyyy-MM-dd HH:mm:ss"))
			)
			.groupby(User.name)
		)
		
		# Apply same filters to count query
		if filters.get("organization"):
			count_query = count_query.where(User.org_id == filters["organization"])
		
		if filters.get("city"):
			count_query = count_query.where(User.city == filters["city"])

		if filters.get("ninja"):
			full_name_filter = f"%{filters['ninja'].lower()}%"
			count_query = count_query.where(Lower(User.full_name).like(full_name_filter))

		# Apply pagination
		query = query.limit(page_length).offset(start)

		# Execute queries
		users = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0

		# Assign Serial Numbers (Recent Rank)
		for count, data in enumerate(users, start + 1):
			data["user_image"] = f"{frappe.utils.get_url()}{data.user_image}" if data.user_image else None
			data["recent_rank"] = count

		# Generate profile URLs
		for row in users:
			if frappe.conf.get("cmp_base_url"):
				row.user_profile = f"{frappe.conf.get('cmp_base_url')}/user-profile/{row.username}"
			else:
				row.user_profile = frappe.utils.get_url(f"/user-profile/{row.username}")

		return custom_response(
			message="Top users retrieved successfully",
			data={
				"result": users,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				},
				"filters": {
					"days": days,
					"applied_filters": filters
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_top_reviewed_users: {str(e)}")
		return custom_response(
			message="Failed to retrieve top users",
			data=None,
			status_code=500,
			error=str(e)
		)
