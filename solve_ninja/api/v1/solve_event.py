import frappe
from frappe import qb
from frappe.query_builder.functions import Count
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_upcoming_events(page_length=10, start=0, city=None, event_type=None):
	"""
	Get upcoming events from Solve Event doctype.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- city: Filter by city (list, optional)
	- event_type: Filter by event type (list, optional)
	
	Returns:
	- All fields from Solve Event doctype for upcoming events
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		# Convert string parameters to lists if provided
		if city and isinstance(city, str):
			city = [city]
		elif not city:
			city = []
		if event_type and isinstance(event_type, str):
			event_type = [event_type]
		elif not event_type:
			event_type = []
		
		SolveEvent = frappe.qb.DocType("Solve Event")
		
		# Build base conditions - upcoming events (start_date_time > today)
		base_conditions = SolveEvent.start_date_time > frappe.utils.today()
		
		# City filter
		if city:
			base_conditions = base_conditions & SolveEvent.city.isin(city)
		
		# Event type filter
		if event_type:
			base_conditions = base_conditions & SolveEvent.type.isin(event_type)
		
		# Build query
		query = (
			frappe.qb.from_(SolveEvent)
			.select(
				SolveEvent.title,
				SolveEvent.description,
				SolveEvent.start_date_time,
				SolveEvent.mode,
				SolveEvent.end_date_time,
				SolveEvent.city,
				SolveEvent.unique_id,
				SolveEvent.type,
				SolveEvent.cover_image,
				SolveEvent.name
			)
			.where(base_conditions)
			.orderby(SolveEvent.start_date_time, order=frappe.qb.asc)
			.limit(page_length)
			.offset(start)
		)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(SolveEvent)
			.select(Count(SolveEvent.name).as_("total"))
			.where(base_conditions)
		)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		for row in result:
			row.cover_image = f"{frappe.utils.get_url()}{row.cover_image}" if row.cover_image else None
			
		return custom_response(
			message="Upcoming events retrieved successfully",
			data={
				"data": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				},
				"filters": {
					"city": city,
					"event_type": event_type
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_upcoming_events: {str(e)}")
		return custom_response(
			message="Failed to retrieve upcoming events",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_past_events(page_length=10, start=0, city=None, event_type=None):
	"""
	Get past events from Solve Event doctype.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- city: Filter by city (list, optional)
	- event_type: Filter by event type (list, optional)
	
	Returns:
	- All fields from Solve Event doctype for past events
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		# Convert string parameters to lists if provided
		if city and isinstance(city, str):
			city = [city]
		elif not city:
			city = []
		if event_type and isinstance(event_type, str):
			event_type = [event_type]
		elif not event_type:
			event_type = []
		
		SolveEvent = frappe.qb.DocType("Solve Event")
		
		# Build base conditions - past events (start_date_time <= today)
		base_conditions = SolveEvent.start_date_time <= frappe.utils.today()
		
		# City filter
		if city:
			base_conditions = base_conditions & SolveEvent.city.isin(city)
		
		# Event type filter
		if event_type:
			base_conditions = base_conditions & SolveEvent.type.isin(event_type)
		
		# Build query
		query = (
			frappe.qb.from_(SolveEvent)
			.select(
				SolveEvent.title,
				SolveEvent.description,
				SolveEvent.start_date_time,
				SolveEvent.mode,
				SolveEvent.end_date_time,
				SolveEvent.city,
				SolveEvent.unique_id,
				SolveEvent.type,
				SolveEvent.cover_image,
				SolveEvent.name
			)
			.where(base_conditions)
			.orderby(SolveEvent.start_date_time, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(SolveEvent)
			.select(Count(SolveEvent.name).as_("total"))
			.where(base_conditions)
		)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		return custom_response(
			message="Past events retrieved successfully",
			data={
				"data": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				},
				"filters": {
					"city": city,
					"event_type": event_type
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_past_events: {str(e)}")
		return custom_response(
			message="Failed to retrieve past events",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_solve_events(page_length=10, start=0, solve_event_type = None):
	"""
	Get solve events filtered by sub_type, ordered by creation desc.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- solve__event_type: Filter by type (string, optional)
	
	Returns:
	- All fields from Solve Event doctype filtered by type, ordered by creation desc
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		SolveEvent = frappe.qb.DocType("Solve Event")
		
		# Build base conditions
		base_conditions = None
		
		# Sub type filter
		if solve_event_type:
			base_conditions = SolveEvent.type == solve_event_type
		
		# Build query
		query = (
			frappe.qb.from_(SolveEvent)
			.select(
				SolveEvent.title,
				SolveEvent.description,
				SolveEvent.start_date_time,
				SolveEvent.mode,
				SolveEvent.end_date_time,
				SolveEvent.city,
				SolveEvent.unique_id,
				SolveEvent.type,
				SolveEvent.cover_image,
				SolveEvent.name,
				SolveEvent.creation
			)
			.orderby(SolveEvent.creation, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Apply conditions if any
		if base_conditions:
			query = query.where(base_conditions)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(SolveEvent)
			.select(Count(SolveEvent.name).as_("total"))
		)
		
		# Apply same conditions to count query
		if base_conditions:
			count_query = count_query.where(base_conditions)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		# Process cover image URLs
		for row in result:
			row.cover_image = f"{frappe.utils.get_url()}{row.cover_image}" if row.cover_image else None
		
		return custom_response(
			message="Events retrieved successfully",
			data={
				"result": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				},
				"filters": {
					"solve_event_type": solve_event_type
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_events_by_sub_type: {str(e)}")
		return custom_response(
			message="Failed to retrieve events",
			data=None,
			status_code=500,
			error=str(e)
		)
