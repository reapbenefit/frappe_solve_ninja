import frappe
import json
from samaaja.api.common import custom_response

# Valid initiative types
VALID_INITIATIVE_TYPES = [
	"Request SolveCon",
	"Organize SolveCon",
	"Start a Chapter",
	"Lead a Chapter"
]

@frappe.whitelist(allow_guest=True)
def get_cities():
	"""
	Get list of cities from Samaaja Cities doctype.
	
	Returns:
	- List of cities with name field
	"""
	try:
		cities_list = frappe.get_all(
			"Samaaja Cities",
			pluck="name"
		)
		
		return custom_response(
			message="Cities retrieved successfully",
			data=cities_list,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_cities: {str(e)}", "Initiative Request API Error")
		return custom_response(
			message="Failed to retrieve cities",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def submit_initiative_request():
	"""
	Submit a new Initiative Request.
	
	Request Body (JSON):
	- full_name (string, required): Full name of requester
	- city (string, required): City name (must exist in Samaaja Cities)
	- phone_number (string, required): Phone number
	- initiative_type (string, required): One of the valid initiative types
	- comments (string, optional): Additional comments
	
	Returns:
	- Success message with created record ID or error details
	"""
	try:
		# Parse request data
		if frappe.request.data:
			request_data = json.loads(frappe.request.data)
		else:
			request_data = frappe.local.form_dict or {}
		
		# Validate required fields
		required_fields = ["full_name", "city", "phone_number", "initiative_type"]
		missing_fields = [field for field in required_fields if not request_data.get(field)]
		
		if missing_fields:
			return custom_response(
				message=f"Missing required fields: {', '.join(missing_fields)}",
				data=None,
				status_code=400,
				error="Validation Error"
			)
		
		# Validate city exists
		city = request_data.get("city")
		if not frappe.db.exists("Samaaja Cities", {"city_name": city}):
			return custom_response(
				message=f"City '{city}' not found. Please select a valid city.",
				data=None,
				status_code=400,
				error="Validation Error"
			)
		
		# Validate initiative_type
		initiative_type = request_data.get("initiative_type")
		if initiative_type not in VALID_INITIATIVE_TYPES:
			return custom_response(
				message=f"Invalid initiative_type. Must be one of: {', '.join(VALID_INITIATIVE_TYPES)}",
				data=None,
				status_code=400,
				error="Validation Error"
			)
		
		# Create Initiative Request document
		initiative_request = frappe.get_doc({
			"doctype": "Initiative Request",
			"full_name": request_data.get("full_name"),
			"city": city,
			"phone_number": request_data.get("phone_number"),
			"initiative_type": initiative_type,
			"comments": request_data.get("comments", "")
		})
		
		initiative_request.insert(ignore_permissions=True)
		frappe.db.commit()
		
		return custom_response(
			message="Initiative request submitted successfully",
			data={
				"id": initiative_request.name,
				"full_name": initiative_request.full_name,
				"city": initiative_request.city,
				"initiative_type": initiative_request.initiative_type
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in submit_initiative_request: {str(e)}\n{frappe.get_traceback()}", "Initiative Request API Error")
		return custom_response(
			message="Failed to submit initiative request",
			data=None,
			status_code=500,
			error=str(e)
		)

