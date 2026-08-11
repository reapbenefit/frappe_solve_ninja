import frappe
import json
from frappe import qb
from frappe.query_builder.functions import Count
from samaaja.api.common import custom_response
from frappe.utils import now_datetime
from solve_ninja.utils import (
	find_or_create_user_by_mobile,
	update_ninja_profile_unique_id,
	log_integration_request,
)


def _marketplace_request_data():
	"""Merge form_dict + JSON body (matches Server Script form_dict behavior)."""
	data = {}
	if frappe.form_dict:
		data.update(dict(frappe.form_dict))
	data.pop("cmd", None)

	raw = getattr(getattr(frappe, "request", None), "data", None)
	if raw:
		try:
			body = json.loads(raw)
			if isinstance(body, dict):
				data.update(body)
		except (TypeError, ValueError, json.JSONDecodeError):
			pass
	return data


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
		
		# Condition to not include events with ignore_reg = Yes
		base_conditions = base_conditions & SolveEvent.ignore_reg == "No"
		
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
				SolveEvent.capacity,
				SolveEvent.name,
				SolveEvent.approval_status,
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

		from solve_ninja.api.event_registration_utils import enrich_events_with_registration_status

		enrich_events_with_registration_status(result)
			
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
				SolveEvent.name,
				SolveEvent.approval_status,
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
		
		for row in result:
			row.cover_image = f"{frappe.utils.get_url()}{row.cover_image}" if row.cover_image else None
		
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
				SolveEvent.creation,
				SolveEvent.approval_status,
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

def log_event_checkin_integration_request(request_data, response_data, error_data=None, user_name=None, solve_event=None, participation=None):
	"""
	Log the event_checkin API request to Integration Request doctype.
	"""
	reference_doctype = "Solve Event Participation" if participation else ("User" if user_name else None)
	reference_docname = participation if participation else (user_name if user_name else None)
	
	log_integration_request(
		request_data=request_data,
		response_data=response_data,
		service_name="Event Checkin API",
		request_description="Event checkin via API",
		error_data=error_data,
		reference_doctype=reference_doctype,
		reference_docname=reference_docname,
		error_title="Event Checkin"
	)

@frappe.whitelist(allow_guest=True)
def event_checkin(mobile=None, event_id=None, whatsapp_name=None):
	"""
	Event checkin API endpoint.
	Creates Solve Event Participation for user.
	Checks if Solve Event Registration exists, if not creates it.
	Checks if user exists or creates user -> Solve Event Registration -> Solve Event Participation.
	
	Args (can be passed as function parameters or in JSON request body):
	- mobile: Mobile number (10 or 12 digits, default country code 91)
	- event_id: Solve Event ID (name or unique_id)
	- whatsapp_name: WhatsApp name (optional)
	
	Returns:
	- Success response with participation details
	"""
	request_data = {}
	error_data = None
	user_name = None
	solve_event = None
	participation = None
	
	try:
		# Parse request data from JSON body if available
		if frappe.request.data:
			data = json.loads(frappe.request.data)
			# Override function parameters with data from request body if provided
			mobile = data.get("mobile") or mobile
			event_id = data.get("event_id") or event_id
			whatsapp_name = data.get("whatsapp_name") or whatsapp_name
		
		# Store request data for logging
		request_data = {
			"mobile": mobile,
			"event_id": event_id,
			"whatsapp_name": whatsapp_name
		}
		
		# Validate inputs
		if not mobile:
			response = custom_response(
				message="Mobile number is required",
				data=None,
				status_code=400,
				error="Mobile number is required"
			)
			response_data = {
				"message": "Mobile number is required",
				"status": "error",
				"data": None,
				"status_code": 400
			}
			log_event_checkin_integration_request(request_data, response_data, {"error": "Mobile number is required"})
			return response
		
		if not event_id:
			response = custom_response(
				message="Event ID is required",
				data=None,
				status_code=400,
				error="Event ID is required"
			)
			response_data = {
				"message": "Event ID is required",
				"status": "error",
				"data": None,
				"status_code": 400
			}
			log_event_checkin_integration_request(request_data, response_data, {"error": "Event ID is required"})
			return response
		
		# Normalize mobile number (handle 10 or 12 digits, default country code 91)
		mobile = ''.join(filter(str.isdigit, str(mobile)))
		
		if len(mobile) not in [10, 12] or not mobile.isdigit():
			response = custom_response(
				message="Mobile number must be either 10 or 12 digits",
				data=None,
				status_code=400,
				error="Invalid mobile number format"
			)
			response_data = {
				"message": "Mobile number must be either 10 or 12 digits",
				"status": "error",
				"data": None,
				"status_code": 400
			}
			log_event_checkin_integration_request(request_data, response_data, {"error": "Invalid mobile number format"})
			return response
		
		# Add country code if 10 digits
		if len(mobile) == 10:
			mobile = "91" + mobile
		
		# Update request_data with normalized mobile
		request_data["mobile"] = mobile
		
		# Try finding by unique_id
		solve_event, solve_event_title, ignore_reg = frappe.db.get_value(
    		"Solve Event",
			{"unique_id": event_id.upper()},
			["name", "title","ignore_reg"]
		)

		if not solve_event:
			response = custom_response(
				message="Event not found",
				data=None,
				status_code=404,
				error=f"Event with ID {event_id} not found"
			)
			response_data = {
				"message": "Event not found",
				"status": "error",
				"data": None,
				"status_code": 404
			}
			log_event_checkin_integration_request(request_data, response_data, {"error": f"Event with ID {event_id} not found"})
			return response
		
		# Get event details for participation
		event_doc = frappe.get_doc("Solve Event", solve_event)

		# Validate event is currently active (now within start_date_time and end_date_time)
		now = now_datetime()
		start_dt = frappe.utils.get_datetime(event_doc.start_date_time)
		end_dt = frappe.utils.get_datetime(event_doc.end_date_time)
		
		if now < start_dt:
			response = custom_response(
				message="Event has not started yet",
				data={"status": "failed"},
				status_code=200,
				error=False
			)
			response_data = {
				"message": "Event has not started yet",
				"status": "success",
				"data": {"status": "failed"},
				"status_code": 200
			}
			log_event_checkin_integration_request(request_data, response_data, {"error": "Event has not started yet"})
			return response
		
		if now > end_dt:
			response = custom_response(
				message="Event has ended",
				data={"status": "failed"},
				status_code=200,
				error=False
			)
			response_data = {
				"message": "Event has ended",
				"status": "success",
				"data": {"status": "failed"},
				"status_code": 200
			}
			log_event_checkin_integration_request(request_data, response_data, {"error": "Event has ended"})
			return response
		
		# Find or create user by mobile number
		user_result = find_or_create_user_by_mobile(mobile, whatsapp_name, event_id)
		
		if not user_result or not user_result.get("user"):
			return custom_response(
				message="Failed to create or find user",
				data=None,
				status_code=500,
				error="User creation/lookup failed"
			)
		
		user = user_result["user"]
		user_name = user
		is_new_user = user_result.get("is_new_user", False)
		name_used = user_result.get("name_used", None)
		
		#registration = find_or_create_registration(user, solve_event)
		
		# Check if Solve Event Registration exists, if not create it
		if ignore_reg == "No" or ignore_reg is None or ignore_reg == "":	
			registration = find_or_create_registration(user, solve_event)
		else:
			registration = None
		
		# Create Solve Event Participation
		participation = create_participation(user, solve_event)
		
		# Build response data
		response_data_dict = {
			"status": "success",
			"user": user,
			"event": solve_event,
			"event_title": solve_event_title,
			"registration": registration,
			"participation": participation,
			"checkin_time": now_datetime().isoformat()
		}
		
		# Add user creation info if new user was created
		if is_new_user:
			response_data_dict["new_user_created"] = True
			response_data_dict["name_used"] = name_used
			response_data_dict["name_source"] = "whatsapp_name" if whatsapp_name and name_used == whatsapp_name else "mobile_number"
		else:
			response_data_dict["new_user_created"] = False
		
		response = custom_response(
			message="Event checkin successful",
			data=response_data_dict,
			status_code=200,
			error=None
		)
		
		# Log to Integration Request
		response_data = {
			"message": "Event checkin successful",
			"status": "success",
			"data": response_data_dict,
			"status_code": 200
		}
		log_event_checkin_integration_request(request_data, response_data, None, user_name, solve_event, participation)
		
		return response
		
	except Exception as e:
		frappe.log_error(f"Error in event_checkin: {str(e)}", "Event Checkin Error")
		error_data = {
			"error": str(e),
			"traceback": frappe.get_traceback()
		}
		response = custom_response(
			message="Failed to process event checkin",
			data=None,
			status_code=500,
			error=str(e)
		)
		response_data = {
			"message": "Failed to process event checkin",
			"status": "error",
			"data": None,
			"status_code": 500
		}
		log_event_checkin_integration_request(request_data, response_data, error_data, user_name, solve_event, participation)
		return response


def find_or_create_registration(user, solve_event_name):
	"""
	Find existing Solve Event Registration or create a new one.
	Prevents duplicate registrations by checking for any existing registration first.
	
	Args:
	- user: User name (email)
	- solve_event: Solve Event name
	
	Returns:
	- Registration name
	"""
	# First, check if ANY registration already exists (regardless of status)
	# This prevents creating duplicates when called multiple times
	existing_registration = frappe.db.get_value(
		"Solve Event Registration",
		{
			"user": user,	
			"solve_event": solve_event_name
		},
		"name"
	)
	
	if existing_registration:
		# Return existing registration to prevent duplicates
		# This works regardless of status (including None/empty or Rejected)
		return existing_registration
	
	# No existing registration found, create new one
	try:
		registration_doc = frappe.get_doc({
			"doctype": "Solve Event Registration",
			"user": user,
			"solve_event": solve_event_name,
			"source": "snbot"
		})
		registration_doc.insert(ignore_permissions=True,ignore_links=True)
		
		# After insertion, check if it was marked as rejected due to duplicate check
		# This handles race conditions where two API calls happen simultaneously
		if registration_doc.status == "Rejected":
			# Reload to get the latest status
			registration_doc.reload()
			# Find the original registration that caused this to be rejected
			original_registration = frappe.db.get_value(
				"Solve Event Registration",
				{
					"user": user,
					"solve_event": solve_event_name,
					"name": ["!=", registration_doc.name]
				},
				"name",
				order_by="creation asc"
			)
			if original_registration:
				return original_registration
		
		return registration_doc.name
	except Exception as e:
		frappe.log_error(f"Error creating registration: {str(e)}", "Registration Creation Error")
		# If there's a duplicate key error or similar, try to find existing registration
		existing_registration = frappe.db.get_value(
			"Solve Event Registration",
			{
				"user": user,
				"solve_event": solve_event_name
			},
			"name"
		)
		if existing_registration:
			return existing_registration
		# Don't fail the checkin if registration creation fails
		return None

def create_participation(user, solve_event_name):
	"""
	Create Solve Event Participation record.
	
	Args:
	- user: User name (email)
	- solve_event: Solve Event name
	- event_doc: Solve Event document
	
	Returns:
	- Participation name
	"""
	try:
		# Check if participation already exists
		existing_participation = frappe.db.get_value(
			"Solve Event Participation",
			{"user": user, "solve_event": solve_event_name},
			"name"
		)
		
		if existing_participation:
			return existing_participation
		
		# Create new participation
		participation_doc = frappe.get_doc({
			"doctype": "Solve Event Participation",
			"user": user,
			"solve_event": solve_event_name
		})
		participation_doc.insert(ignore_permissions=True)
		return participation_doc.name
	except Exception as e:
		frappe.log_error(f"Error creating participation: {str(e)}", "Participation Creation Error")
		frappe.throw(f"Failed to create participation: {str(e)}")

@frappe.whitelist(allow_guest=True)
def program_checkin(mobile=None, program_id=None, whatsapp_name=None):
	"""
	Program checkin API endpoint.
	Creates Program Participation for user.
	Checks if user exists or creates user -> Program Participation.
	
	Args (can be passed as function parameters or in JSON request body):
	- mobile: Mobile number (10 or 12 digits, default country code 91)
	- program_id: Program ID (name or unique_id)
	- whatsapp_name: WhatsApp name (optional)
	
	Returns:
	- Success response with participation details
	"""
	try:
		# Parse request data from JSON body if available
		try:
			if getattr(frappe, "request", None) and frappe.request.data:
				data = json.loads(frappe.request.data)
				# Override function parameters with data from request body if provided
				mobile = data.get("mobile") or mobile
				program_id = data.get("program_id") or program_id
				whatsapp_name = data.get("whatsapp_name") or whatsapp_name
		except (TypeError, ValueError, json.JSONDecodeError):
			pass
		
		# Validate inputs
		if not mobile:
			return custom_response(
				message="Mobile number is required",
				data=None,
				status_code=400,
				error="Mobile number is required"
			)
		
		if not program_id:
			return custom_response(
				message="Program ID is required",
				data=None,
				status_code=400,
				error="Program ID is required"
			)
		
		# Normalize mobile number (handle 10 or 12 digits, default country code 91)
		mobile = ''.join(filter(str.isdigit, str(mobile)))
		
		if len(mobile) not in [10, 12] or not mobile.isdigit():
			return custom_response(
				message="Mobile number must be either 10 or 12 digits",
				data=None,
				status_code=400,
				error="Invalid mobile number format"
			)
		
		# Add country code if 10 digits
		if len(mobile) == 10:
			mobile = "91" + mobile
		
		# Find Program by name or unique_id
		program = None
		if frappe.db.exists("Program", program_id):
			program = program_id
		else:
			# Try finding by unique_id
			program = frappe.db.get_value("Program", {"unique_id": program_id.upper()}, "name")
		
		if not program:
			return custom_response(
				message="Program not found",
				data=None,
				status_code=404,
				error=f"Program with ID {program_id} not found"
			)
		
		# Get program details
		program_doc = frappe.get_doc("Program", program)

		from solve_ninja.api.common import assign_user_organization

		# Find or create user by mobile number.
		# Pass program name as user_organization — only applied for new users in add_user_async
		# when User Organization already exists (created on Program save).
		user_organization = program if frappe.db.exists("User Organization", program) else None
		user_result = find_or_create_user_by_mobile(
			mobile, whatsapp_name, user_organization=user_organization
		)
		
		if not user_result or not user_result.get("user"):
			return custom_response(
				message="Failed to create or find user",
				data=None,
				status_code=500,
				error="User creation/lookup failed"
			)
		
		user = user_result["user"]
		is_new_user = user_result.get("is_new_user", False)
		name_used = user_result.get("name_used", None)
		
		# Update Ninja Profile with program unique_id (only for new users)
		if is_new_user:
			program_unique_id = program_doc.get("unique_id")
			if program_unique_id:
				update_ninja_profile_unique_id(user, program_unique_id)

			# If user already exists in DB (async finished, or enqueue ran inline),
			# assign org now. Otherwise add_user_async assigns via user_organization.
			if user_organization and frappe.db.exists("User", user):
				assign_user_organization(user, user_organization)
		
		# Create Program Participation
		participation = create_program_participation(user, program)
		
		# Build response data
		response_data = {
			"user": user,
			"program": program,
			"program_name": program_doc.program_name,
			"participation": participation,
			"checkin_time": now_datetime().isoformat()
		}
		
		# Add user creation info if new user was created
		if is_new_user:
			response_data["new_user_created"] = True
			response_data["name_used"] = name_used
			response_data["name_source"] = "whatsapp_name" if whatsapp_name and name_used == whatsapp_name else "mobile_number"
		else:
			response_data["new_user_created"] = False
		
		return custom_response(
			message="Program checkin successful",
			data=response_data,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in program_checkin: {str(e)}", "Program Checkin Error")
		return custom_response(
			message="Failed to process program checkin",
			data={"error": str(e)},
			status_code=500,
			error=str(e)
		)

def create_program_participation(user, program):
	"""
	Create Program Participation record.
	
	Args:
	- user: User name (email)
	- program: Program name
	
	Returns:
	- Participation name
	"""
	try:
		# Check if participation already exists
		existing_participation = frappe.db.get_value(
			"Program Participation",
			{"user": user, "program": program},
			"name"
		)
		
		if existing_participation:
			return existing_participation
		
		# Create new participation
		participation_doc = frappe.get_doc({
			"doctype": "Program Participation",
			"user": user,
			"program": program
		})
		participation_doc.insert(ignore_permissions=True, ignore_links=True)
		return participation_doc.name
	except Exception as e:
		frappe.log_error(f"Error creating program participation: {str(e)}", "Program Participation Creation Error")
		frappe.throw(f"Failed to create program participation: {str(e)}")


# ---------------------------------------------------------------------------
# Marketplace Events / Host-at-Adda APIs
# Migrated from Server Scripts (create_solve_event, set_solve_event_cover_image,
# get_adda_rooms, get_adda_room_availability). Response shape matches the
# previous Server Script `message` payloads for frontend compatibility.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def get_adda_rooms(city=None):
	"""
	List Adda Room records, optionally filtered by city.

	POST /api/method/solve_ninja.api.v1.solve_event.get_adda_rooms
	Body (optional): { "city": "Bengaluru" }
	"""
	data = _marketplace_request_data()
	city_value = str(city or data.get("city") or "").strip()

	filters = {}
	if city_value:
		filters["city"] = city_value

	rooms = frappe.get_all(
		"Adda Room",
		filters=filters,
		fields=["name", "room_name", "city", "capacity"],
		order_by="room_name asc",
	)

	return {
		"status": "success",
		"city": city_value or None,
		"rooms": rooms,
	}


@frappe.whitelist(allow_guest=True)
def get_adda_room_availability(date=None, city=None, room_name=None):
	"""
	Bookings that block a room on a given day (Pending Review + Approved only).

	POST /api/method/solve_ninja.api.v1.solve_event.get_adda_room_availability
	Body: { "date": "YYYY-MM-DD", "city"?: string, "room_name"?: string }
	"""
	data = _marketplace_request_data()
	date_key = str(date or data.get("date") or data.get("booking_date") or "").strip()[:10]
	city_value = str(city or data.get("city") or "").strip()
	room_value = str(room_name or data.get("room_name") or data.get("room") or "").strip()

	if not date_key or len(date_key) != 10:
		frappe.throw("date is required (YYYY-MM-DD)")

	day_start = f"{date_key} 00:00:00"
	day_end = f"{date_key} 23:59:59"

	filters = {
		"room_name": ["is", "set"],
		"start_date_time": ["between", [day_start, day_end]],
		"approval_status": ["in", ["Pending Review", "Approved"]],
	}
	if room_value:
		filters["room_name"] = room_value
	if city_value:
		filters["city"] = city_value

	rows = frappe.get_all(
		"Solve Event",
		filters=filters,
		fields=[
			"name",
			"title",
			"city",
			"room_name",
			"start_date_time",
			"end_date_time",
			"approval_status",
			"type",
		],
		order_by="start_date_time asc",
		ignore_permissions=True,
	)

	bookings = []
	for row in rows:
		status = (row.approval_status or "Pending Review").strip()
		if status in ("1", "Yes", "yes", "true", "True"):
			status = "Approved"
		elif status in ("0", "No", "no", "false", "False", ""):
			status = "Pending Review"

		if status not in ("Pending Review", "Approved"):
			continue

		start = str(row.start_date_time or "")
		end = str(row.end_date_time or "")
		start_time = start[11:19] if len(start) >= 19 else ""
		end_time = end[11:19] if len(end) >= 19 else ""

		if not row.room_name or not start_time or not end_time:
			continue

		bookings.append(
			{
				"name": row.name,
				"title": row.title,
				"city": row.city,
				"room": row.room_name,
				"room_name": row.room_name,
				"booking_date": date_key,
				"start_time": start_time,
				"end_time": end_time,
				"start_date_time": start,
				"end_date_time": end,
				"approval_status": status,
				"status": "Confirmed" if status == "Approved" else "Pending",
				"event_type": row.type,
			}
		)

	return {
		"success": True,
		"date": date_key,
		"city": city_value or None,
		"room_name": room_value or None,
		"bookings": bookings,
	}


@frappe.whitelist()
def create_solve_event():
	"""
	Create a Solve Event (Host at Adda). Requires a logged-in session.

	POST /api/method/solve_ninja.api.v1.solve_event.create_solve_event
	"""
	data = _marketplace_request_data()

	if frappe.session.user in (None, "", "Guest"):
		frappe.throw("Please log in to submit an event")

	cover_image = str(data.get("image") or data.get("cover_image") or "").strip()
	room_name = str(data.get("room_name") or "").strip()

	approval_status = str(data.get("approval_status") or "Pending Review").strip()
	if approval_status not in ("Pending Review", "Approved", "Rejected"):
		approval_status = "Pending Review"

	mandatory_map = {
		"title": data.get("title"),
		"type": data.get("type"),
		"description": data.get("description"),
		"start_date_time": data.get("start") or data.get("start_date_time"),
		"end_date_time": data.get("end") or data.get("end_date_time"),
		"city": data.get("city"),
		"people_expected": data.get("people_expected"),
	}

	missing = [k for k, v in mandatory_map.items() if v is None or str(v).strip() == ""]
	if missing:
		frappe.throw(f"Missing mandatory fields: {', '.join(missing)}")

	try:
		people_expected = int(mandatory_map["people_expected"])
	except (TypeError, ValueError):
		frappe.throw("people_expected must be a valid number")

	start = mandatory_map["start_date_time"]
	end = mandatory_map["end_date_time"]

	if room_name:
		existing = frappe.get_all(
			"Solve Event",
			filters={
				"room_name": room_name,
				"approval_status": ["in", ["Pending Review", "Approved"]],
				"start_date_time": ["<", end],
				"end_date_time": [">", start],
			},
			fields=["name", "title", "start_date_time", "end_date_time", "approval_status"],
			ignore_permissions=True,
			limit_page_length=5,
		)
		if existing:
			clash = existing[0]
			frappe.throw(
				f"Room '{room_name}' is already booked for this time "
				f"({clash.title or clash.name}). Pick another room or time."
			)

	event_doc = {
		"doctype": "Solve Event",
		"title": str(mandatory_map["title"]).strip(),
		"type": str(mandatory_map["type"]).strip(),
		"description": str(mandatory_map["description"]).strip(),
		"start_date_time": start,
		"end_date_time": end,
		"city": str(mandatory_map["city"]).strip(),
		"people_expected": people_expected,
		"approval_status": approval_status,
		"mode": data.get("mode", "Offline"),
		"venue_details": data.get("venue_details"),
		"wa_group_link": data.get("wa_group_link"),
		"additional_notification_emails": data.get("additional_notification_emails"),
	}

	if cover_image:
		event_doc["cover_image"] = cover_image

	if room_name:
		event_doc["room_name"] = room_name

	if data.get("capacity") not in (None, ""):
		try:
			event_doc["capacity"] = int(data.get("capacity"))
		except (TypeError, ValueError):
			frappe.throw("capacity must be a valid number")

	doc = frappe.get_doc(event_doc)

	if not cover_image:
		doc.flags.ignore_mandatory = True

	doc.flags.ignore_permissions = True
	doc.insert()

	return {
		"status": "success",
		"name": doc.name,
		"title": doc.title,
		"owner": frappe.session.user,
		"room_name": room_name or None,
		"approval_status": approval_status,
		"cover_image_pending": not bool(cover_image),
	}


@frappe.whitelist()
def set_solve_event_cover_image(event_id=None, file_url=None, name=None, cover_image=None):
	"""
	Set Solve Event.cover_image after upload_file.

	POST /api/method/solve_ninja.api.v1.solve_event.set_solve_event_cover_image
	Body: { "event_id": "<Solve Event name>", "file_url": "/files/...." }
	"""
	if frappe.session.user in (None, "", "Guest"):
		frappe.throw("Please log in to update the cover image")

	data = _marketplace_request_data()
	docname = str(event_id or name or data.get("event_id") or data.get("name") or "").strip()
	url = str(file_url or cover_image or data.get("file_url") or data.get("cover_image") or "").strip()

	if not docname:
		frappe.throw("event_id is required")
	if not url:
		frappe.throw("file_url is required")

	if not frappe.db.exists("Solve Event", docname):
		frappe.throw(f"Solve Event not found: {docname}")

	frappe.db.set_value("Solve Event", docname, "cover_image", url)

	return {
		"status": "success",
		"success": True,
		"name": docname,
		"cover_image": url,
	}
