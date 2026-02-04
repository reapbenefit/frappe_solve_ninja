from math import log, floor
import frappe
from frappe import _

def human_format(number):
	units = ['', 'K', 'M', 'G', 'T', 'P']
	k = 1000.0
	magnitude = int(floor(log(number, k)))
	return '%.2f%s' % (number / k**magnitude, units[magnitude])

def validate_and_normalize_mobile(mobile):
    if not mobile or len(mobile) not in [10, 12] or not mobile.isdigit():
        frappe.throw(_("Mobile number must be either 10 or 12 digits and numeric."))

    if len(mobile) == 10:
        mobile = "91" + mobile

    return mobile

def get_doc_by_unique_id(unique_id):
	"""
	Get doctype type and document name based on unique_id.
	
	Args:
		unique_id (str): The unique_id to search for
		
	Returns:
		dict: Dictionary with 'doctype' and 'name' keys, or None if not found
		Example: {'doctype': 'Program', 'name': 'Program Name'}
	"""
	if not unique_id:
		return None
	
	# List of doctypes to search in order
	doctypes = ["Program", "Solve Event", "Social Media"]
	
	# Search each doctype for a matching unique_id
	for doctype in doctypes:
		doc_name = frappe.db.get_value(doctype, {"unique_id": unique_id}, "name")
		if doc_name:
			return {
				"doctype": doctype,
				"name": doc_name
			}
	
	# No match found
	return None

def find_user_by_mobile(mobile_input): #returns name, actual_mobile, username
	"""
	Generic method to find user by mobile number.
	Tries both 10-digit and 12-digit formats (with/without country code).
	
	Args:
		mobile_input (str): Mobile number (10 or 12 digits)
	
	Returns:
		tuple: (user_name, actual_mobile_format) if found, (None, None) if not found
	"""
	if not mobile_input or len(mobile_input) not in [10, 12] or not mobile_input.isdigit():
		return None, None, None
	
	user_name = None
	actual_mobile = None
	username = None
	if len(mobile_input) == 10:
		# Try with 10-digit first
		user_name = frappe.db.get_value("User", {"mobile_no": mobile_input}, "name")
		if user_name:
			actual_mobile = mobile_input
			username = frappe.db.get_value("User", {"mobile_no": mobile_input}, "username")
		else:
			# Try with 91 prefix
			mobile_with_prefix = "91" + mobile_input
			user_name = frappe.db.get_value("User", {"mobile_no": mobile_with_prefix}, "name")
			if user_name:
				actual_mobile = mobile_with_prefix
				username = frappe.db.get_value("User", {"mobile_no": mobile_with_prefix}, "username")
			else:
				actual_mobile = mobile_input
	else:
		# 12-digit provided, try with country code first, then without
		user_name = frappe.db.get_value("User", {"mobile_no": mobile_input}, "name")
		if user_name:
			actual_mobile = mobile_input
			username = frappe.db.get_value("User", {"mobile_no": mobile_input}, "username")
		else:
			# Try without country code (last 10 digits)
			mobile_without_prefix = mobile_input[2:] if mobile_input.startswith("91") else mobile_input
			user_name = frappe.db.get_value("User", {"mobile_no": mobile_without_prefix}, "name")
			if user_name:
				actual_mobile = mobile_without_prefix
				username = frappe.db.get_value("User", {"mobile_no": mobile_without_prefix}, "username")
			else:
				actual_mobile = mobile_input
	
	return user_name, actual_mobile, username

def is_unique_id_duplicate(unique_id, exclude_doctype=None, exclude_name=None):
	"""
	Check if unique_id already exists across Program, Solve Event, and Social Media doctypes.
	
	Args:
		unique_id (str): The unique_id to check for duplicates
		exclude_doctype (str, optional): Doctype name to exclude from check (e.g., "Program")
		exclude_name (str, optional): Document name to exclude from check
		
	Returns:
		dict: Dictionary with 'doctype' and 'name' keys if duplicate found, None if unique
		Example: {'doctype': 'Program', 'name': 'Program Name'} or None
	"""
	if not unique_id:
		return None
	
	# List of doctypes to check
	doctypes = ["Program", "Solve Event", "Social Media"]
	
	# Check each doctype for a matching unique_id
	for doctype in doctypes:
		# Build filter conditions
		filters = {"unique_id": unique_id}
		
		# If excluding current document, add name filter
		if exclude_doctype == doctype and exclude_name:
			filters["name"] = ["!=", exclude_name]
		
		doc_name = frappe.db.get_value(doctype, filters, "name")
		
		if doc_name:
			# Found a duplicate (or a different document if excluding current)
			return {
				"doctype": doctype,
				"name": doc_name
			}
	
	# No duplicate found
	return None

def update_ninja_profile_unique_id(user, event_unique_id=None, solve_event=None):
	"""
	Update acquisition_source_unique_id in Ninja Profile with event_unique_id or solve_event.
	Uses save() method with ignore_permissions to trigger on_update hooks.
	
	Args:
	- user: User name (email)
	- event_unique_id: Event unique_id to set in Ninja Profile
	- solve_event: Solve Event document to set in Ninja Profile
	"""
	try:
		if (event_unique_id or solve_event) and frappe.db.exists("Ninja Profile", user):
			ninja_profile = frappe.get_doc("Ninja Profile", user)
			if event_unique_id:
				ninja_profile.acquisition_source_unique_id = event_unique_id.upper()
			if solve_event:
				ninja_profile.acquisition_source_category = "Solve Event"
				ninja_profile.acquisition_source_name = solve_event
			ninja_profile.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(f"Error updating Ninja Profile acquisition_source_unique_id for user {user}: {str(e)}", "Update Ninja Profile Unique ID Error")

def find_or_create_user_by_mobile(mobile, whatsapp_name=None, event_unique_id=None):
	"""
	Find existing user by mobile number (checking both 10 and 12 digit formats).
	If not found, create a new user.
	Updates Ninja Profile unique_id with event_unique_id if provided.
	
	Args:
	- mobile: Normalized mobile number (12 digits with country code)
	- whatsapp_name: WhatsApp name for new user creation
	- event_unique_id: Event unique_id to update in Ninja Profile (optional)
	
	Returns:
	- dict with keys: user (email), is_new_user (bool), name_used (str)
	"""
	# Use find_user_by_mobile to check if user exists
	user_name, *_ = find_user_by_mobile(mobile)
	
	if user_name:
		# Update Ninja Profile unique_id if event_unique_id is provided
		# if event_unique_id:
		# 	update_ninja_profile_unique_id(user_name, event_unique_id)
		
		return {
			"user": user_name,
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
			'send_welcome_email': 0
		})
		user_doc.append("roles", {"role": "Solve Ninja"})
		user_doc.insert(ignore_permissions=True)
		
		# Update Ninja Profile unique_id if event_unique_id is provided
		# if event_unique_id:
		#	update_ninja_profile_unique_id(user_doc.name, event_unique_id)
		
		# Enqueue background tasks for profile updates if needed
		frappe.enqueue(
			"solve_ninja.api.common.update_ninja_profile",
			user=user_doc.name,
			user_data={"mobile": mobile, "first_name": user_name, "event_id": event_unique_id} if event_unique_id else {"mobile": mobile, "first_name": user_name},
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

def log_integration_request(request_data, response_data, service_name, request_description, error_data=None, reference_doctype=None, reference_docname=None, error_title=None):
	"""
	Generic method to log API requests to Integration Request doctype.
	
	Args:
		request_data (dict): Request data to log
		response_data (dict): Response data containing message, status, data, status_code
		service_name (str): Name of the integration service (e.g., "Event Checkin API", "Add User API")
		request_description (str): Description of the request (e.g., "Event checkin via API")
		error_data (dict, optional): Error data if request failed
		reference_doctype (str, optional): Reference doctype name
		reference_docname (str, optional): Reference document name
		error_title (str, optional): Title for error logging (defaults to service_name)
	"""
	try:
		request_headers = {}
		if hasattr(frappe.request, 'headers'):
			request_headers = dict(frappe.request.headers)
		
		url = None
		if hasattr(frappe.request, 'url'):
			url = frappe.request.url
		
		response_output = {
			"message": response_data.get("message"),
			"status": response_data.get("status"),
			"data": response_data.get("data"),
			"status_code": response_data.get("status_code")
		}
		
		integration_request = frappe.get_doc({
			"doctype": "Integration Request",
			"integration_request_service": service_name,
			"is_remote_request": 0,
			"url": url,
			"request_headers": frappe.as_json(request_headers) if request_headers else "",
			"data": frappe.as_json(request_data) if request_data else "",
			"output": frappe.as_json(response_output) if response_output else "",
			"error": frappe.as_json(error_data) if error_data else "",
			"status": "Completed" if not error_data else "Failed",
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"request_description": request_description,
		})
		integration_request.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		error_title = error_title or service_name
		frappe.log_error(f"Error logging Integration Request: {str(e)}", f"{error_title} Integration Request Error")