from math import log, floor
import frappe
from frappe import _

def human_format(number):
	units = ['', 'K', 'M', 'G', 'T', 'P']
	k = 1000.0
	magnitude = int(floor(log(number, k)))
	return '%.2f%s' % (number / k**magnitude, units[magnitude])

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