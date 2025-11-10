import frappe
from frappe import qb
from frappe.query_builder.functions import Count
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_mentors(page_length=10, start=0):
	"""
	Get mentors with their expertise, status, and quote information.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	
	Returns:
	- name: User name (same as username)
	- full_name: Full name from User doctype
	- username: Username from User doctype
	- user_image: User image from User doctype
	- is_mentor: Mentor status from User Metadata
	- mentor_quote: Mentor quote from User Metadata
	- mentor_expertise: Mentor expertise from User Metadata
	- mentor_status: Mentor status from User Metadata
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		UserMetadata = frappe.qb.DocType("User Metadata")
		User = frappe.qb.DocType("User")
		
		# Build base conditions - only mentors
		base_conditions = (
			(UserMetadata.is_mentor == 1) &
			(UserMetadata.name == User.name)
		)
		
		# Query to get mentors with user details
		query = (
			frappe.qb.from_(UserMetadata)
			.join(User).on(User.name == UserMetadata.name)
			.select(
				UserMetadata.name,
				UserMetadata.is_mentor,
				UserMetadata.mentor_quote,
				UserMetadata.mentor_expertise,
				UserMetadata.mentor_status,
				User.full_name,
				User.username,
				User.user_image
			)
			.where(base_conditions)
			.orderby(UserMetadata.modified, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(UserMetadata)
			.join(User).on(User.name == UserMetadata.name)
			.select(Count(UserMetadata.name).as_("total"))
			.where(base_conditions)
		)
		
		result = query.run(as_dict=True)

		for row in result:
			row.profile_url = f"{frappe.utils.get_url()}/user-profile/{row.username}"
			row.user_image = f"{frappe.utils.get_url()}{row.user_image}" if row.user_image else None

		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		return custom_response(
			message="Mentors retrieved successfully",
			data={
				"result": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_mentors: {str(e)}")
		return custom_response(
			message="Failed to retrieve mentors",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_chapter_lead(page_length=10, start=0):
	"""
	Get chapter leads with their achievement and status information.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	
	Returns:
	- name: User name (same as username)
	- full_name: Full name from User doctype
	- username: Username from User doctype
	- user_image: User image from User doctype
	- is_city_chapter_lead: Chapter lead status from User Metadata
	- chapter_lead_achivement: Chapter lead achievement from User Metadata
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		UserMetadata = frappe.qb.DocType("User Metadata")
		User = frappe.qb.DocType("User")
		
		# Build base conditions - only chapter leads
		base_conditions = (
			(UserMetadata.is_city_chapter_lead == 1) &
			(UserMetadata.name == User.name)
		)
		
		# Query to get chapter leads with user details
		query = (
			frappe.qb.from_(UserMetadata)
			.join(User).on(User.name == UserMetadata.name)
			.select(
				UserMetadata.name,
				UserMetadata.is_city_chapter_lead,
				UserMetadata.chapter_lead_achivement,
				User.full_name,
				User.username,
				User.user_image
			)
			.where(base_conditions)
			.orderby(UserMetadata.modified, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(UserMetadata)
			.join(User).on(User.name == UserMetadata.name)
			.select(Count(UserMetadata.name).as_("total"))
			.where(base_conditions)
		)
		
		result = query.run(as_dict=True)

		for row in result:
			row.profile_url = f"{frappe.utils.get_url()}/user-profile/{row.username}"
			row.user_image = f"{frappe.utils.get_url()}{row.user_image}" if row.user_image else None

		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		return custom_response(
			message="Chapter leads retrieved successfully",
			data={
				"result": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_chapter_lead: {str(e)}")
		return custom_response(
			message="Failed to retrieve chapter leads",
			data=None,
			status_code=500,
			error=str(e)
		)
