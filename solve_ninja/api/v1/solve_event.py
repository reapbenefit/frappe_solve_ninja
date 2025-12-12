import frappe
from frappe import qb
from frappe.query_builder.functions import Count
from samaaja.api.common import custom_response
from frappe.utils import now_datetime

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

@frappe.whitelist(allow_guest=True)
def event_checkin(mobile, event_id, whatsapp_name=None):
	"""
	Event checkin API endpoint.
	Creates Solve Event Participation for user.
	Checks if Solve Event Registration exists, if not creates it.
	Checks if user exists or creates user -> Solve Event Registration -> Solve Event Participation.
	
	Args:
	- mobile: Mobile number (10 or 12 digits, default country code 91)
	- event_id: Solve Event ID (name or unique_id)
	- whatsapp_name: WhatsApp name (optional)
	
	Returns:
	- Success response with participation details
	"""
	try:
		# Validate inputs
		if not mobile:
			return custom_response(
				message="Mobile number is required",
				data=None,
				status_code=400,
				error="Mobile number is required"
			)
		
		if not event_id:
			return custom_response(
				message="Event ID is required",
				data=None,
				status_code=400,
				error="Event ID is required"
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
		
		# Find Solve Event by name or unique_id
		solve_event = None
		if frappe.db.exists("Solve Event", event_id):
			solve_event = event_id
		else:
			# Try finding by unique_id
			solve_event = frappe.db.get_value("Solve Event", {"unique_id": event_id}, "name")
		
		if not solve_event:
			return custom_response(
				message="Event not found",
				data=None,
				status_code=404,
				error=f"Event with ID {event_id} not found"
			)
		
		# Get event details for participation
		event_doc = frappe.get_doc("Solve Event", solve_event)
		
		# Find or create user by mobile number
		user_result = find_or_create_user_by_mobile(mobile, whatsapp_name)
		
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
		
		# Check if Solve Event Registration exists, if not create it
		registration = find_or_create_registration(user, solve_event)
		
		# Create Solve Event Participation
		participation = create_participation(user, solve_event, event_doc)
		
		# Build response data
		response_data = {
			"user": user,
			"event": solve_event,
			"event_title": event_doc.title,
			"registration": registration,
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
			message="Event checkin successful",
			data=response_data,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in event_checkin: {str(e)}", "Event Checkin Error")
		return custom_response(
			message="Failed to process event checkin",
			data=None,
			status_code=500,
			error=str(e)
		)

def find_or_create_user_by_mobile(mobile, whatsapp_name=None):
	"""
	Find existing user by mobile number (checking both 10 and 12 digit formats).
	If not found, create a new user.
	
	Args:
	- mobile: Normalized mobile number (12 digits with country code)
	- whatsapp_name: WhatsApp name for new user creation
	
	Returns:
	- dict with keys: user (email), is_new_user (bool), name_used (str)
	"""
	# Check with country code first
	existing_user = frappe.db.get_value("User", {"mobile_no": mobile}, "name")
	if existing_user:
		return {
			"user": existing_user,
			"is_new_user": False,
			"name_used": None
		}
	
	# If mobile has country code, also check without it
	if len(mobile) == 12 and mobile.startswith("91"):
		mobile_without_code = mobile[2:]  # Remove "91" prefix
		existing_user = frappe.db.get_value("User", {"mobile_no": mobile_without_code}, "name")
		if existing_user:
			return {
				"user": existing_user,
				"is_new_user": False,
				"name_used": None
			}
	
	# If mobile is 10 digits, also check with country code (shouldn't happen as we normalize, but just in case)
	if len(mobile) == 10:
		mobile_with_code = "91" + mobile
		existing_user = frappe.db.get_value("User", {"mobile_no": mobile_with_code}, "name")
		if existing_user:
			return {
				"user": existing_user,
				"is_new_user": False,
				"name_used": None
			}
	
	# User doesn't exist, create new user
	try:
		# Determine what name to use
		if whatsapp_name and whatsapp_name.strip():
			user_name = whatsapp_name.strip()
			name_used = whatsapp_name.strip()
		else:
			user_name = mobile  # Use mobile number as name when whatsapp_name not provided
			name_used = mobile
		
		user_doc = frappe.get_doc({
			'doctype': 'User',
			'mobile': mobile,
			'email': f"{mobile}@solveninja.org",
			'mobile_no': mobile,
			'first_name': user_name,
			'new_password': mobile
		})
		user_doc.append("roles", {"role": "Solve Ninja"})
		user_doc.insert(ignore_permissions=True)
		
		# Enqueue background tasks for profile updates if needed
		frappe.enqueue(
			"solve_ninja.api.common.update_ninja_profile",
			user=user_doc.name,
			user_data={"mobile": mobile, "first_name": user_name},
			queue='default',
			job_name=f"Update ninja profile for {user_doc.name}",
			now=False
		)
		
		return {
			"user": user_doc.name,
			"is_new_user": True,
			"name_used": name_used
		}
	except Exception as e:
		frappe.log_error(f"Error creating user: {str(e)}", "User Creation Error")
		return None

def find_or_create_registration(user, solve_event):
	"""
	Find existing Solve Event Registration or create a new one.
	
	Args:
	- user: User name (email)
	- solve_event: Solve Event name
	
	Returns:
	- Registration name
	"""
	# Check if registration already exists
	existing_registration = frappe.db.get_value(
		"Solve Event Registration",
		{"user": user, "solve_event": solve_event},
		"name"
	)
	
	if existing_registration:
		return existing_registration
	
	# Create new registration
	try:
		registration_doc = frappe.get_doc({
			"doctype": "Solve Event Registration",
			"user": user,
			"solve_event": solve_event,
			"source": "snbot"
		})
		registration_doc.insert(ignore_permissions=True)
		return registration_doc.name
	except Exception as e:
		frappe.log_error(f"Error creating registration: {str(e)}", "Registration Creation Error")
		# Don't fail the checkin if registration creation fails
		return None

def create_participation(user, solve_event, event_doc):
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
		participation_doc = frappe.get_doc({
			"doctype": "Solve Event Participation",
			"user": user,
			"solve_event": solve_event,
			"solve_event_date": now_datetime(),
			# "sub_type": event_doc.get("type") or event_doc.get("sub_type"),
			"mode": event_doc.get("mode"),
			"city": event_doc.get("city")
		})
		participation_doc.insert(ignore_permissions=True)
		return participation_doc.name
	except Exception as e:
		frappe.log_error(f"Error creating participation: {str(e)}", "Participation Creation Error")
		frappe.throw(f"Failed to create participation: {str(e)}")

@frappe.whitelist(allow_guest=True)
def program_checkin(mobile, program_id, whatsapp_name=None):
	"""
	Program checkin API endpoint.
	Creates Program Participation for user.
	Checks if user exists or creates user -> Program Participation.
	
	Args:
	- mobile: Mobile number (10 or 12 digits, default country code 91)
	- program_id: Program ID (name or unique_id)
	- whatsapp_name: WhatsApp name (optional)
	
	Returns:
	- Success response with participation details
	"""
	try:
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
			program = frappe.db.get_value("Program", {"unique_id": program_id}, "name")
		
		if not program:
			return custom_response(
				message="Program not found",
				data=None,
				status_code=404,
				error=f"Program with ID {program_id} not found"
			)
		
		# Get program details
		program_doc = frappe.get_doc("Program", program)
		
		# Find or create user by mobile number
		user_result = find_or_create_user_by_mobile(mobile, whatsapp_name)
		
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
			data=None,
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
		participation_doc.insert(ignore_permissions=True)
		return participation_doc.name
	except Exception as e:
		frappe.log_error(f"Error creating program participation: {str(e)}", "Program Participation Creation Error")
		frappe.throw(f"Failed to create program participation: {str(e)}")
