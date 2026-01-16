import frappe
import json
from samaaja.api.common import custom_response
from solve_ninja.utils import log_integration_request


@frappe.whitelist()
def create_mentorship_request():
	"""
	Create a new Mentorship Request.
	
	Request Body (JSON):
	- mentee_name (string, required): Name of the mentee
	- phone (string, required): Phone number of the mentee
	- mentee_age (string, optional): Age of the mentee
	- mentee_whatsapp_id (string, optional): WhatsApp ID of the mentee
	- investigation_status (string, optional): Investigation status (Yes/No)
	- problem_statement (string, optional): Problem statement
	- location (string, optional): Location of the mentee
	- specific_ask (string, optional): Specific ask response (Yes/No)
	- problem_faced (string, optional): Current problem faced
	- solve_action (string, optional): Solve action taken
	- why_personal (string, optional): Why personal problem
	- investigation_response (string, optional): Investigation response
	- mentor_skills (string, optional): Skills needed from mentor
	- anything_else (string, optional): Any additional information
	- discovered_problem (string, optional): Discovered problem description
	- solving_status (string, optional): Solving status (Yes/No)
	- guidance_needed (string, optional): Type of guidance needed
	
	Returns:
	- Success message with created record ID or error details
	"""
	message = "Mentorship request created successfully"
	status_code = 200
	error = None
	data = None
	request_data = {}
	doc_name = None
	error_data = None
	
	try:
		# Parse request data
		if frappe.request.data:
			request_data = json.loads(frappe.request.data)
		else:
			request_data = frappe.local.form_dict or {}
		
		# Validate required fields
		required_fields = ["mentee_name", "phone"]
		missing_fields = [field for field in required_fields if not request_data.get(field)]
		
		if missing_fields:
			message = f"Missing required fields: {', '.join(missing_fields)}"
			status_code = 400
			error = "Validation Error"
			error_data = {
				"error": message,
				"missing_fields": missing_fields
			}
			raise ValueError(message)
		
		# Create Mentorship Request document with field mapping
		mentorship_request = frappe.get_doc({
			"doctype": "Mentorship Request",
			"mentee": request_data.get("mentee_name"),
			"phone": request_data.get("phone"),
			"mentee_age": request_data.get("mentee_age"),
			"mentee_whatsapp_id": request_data.get("mentee_whatsapp_id"),
			"investigation_status": request_data.get("investigation_status"),
			"problem_statement": request_data.get("problem_statement"),
			"specific_ask": request_data.get("specific_ask"),
			"guidance_details": "Not Provided" if request_data.get("guidance_details", "").startswith("@") else request_data.get("guidance_details"),
			"solve_action": "Not Provided" if request_data.get("solve_action","").startswith("@") else request_data.get("solve_action"),
			"why_personal": request_data.get("why_personal"),
			"investigation_response": "Not Provided" if request_data.get("investigation_response", "").startswith("@") else request_data.get("investigation_response"),
			"mentor_skills": request_data.get("mentor_skills"),
			"anything_else": "Not Provided" if request_data.get("anything_else", "").startswith("@") else request_data.get("anything_else"),
			"discovered_problem": request_data.get("discovered_problem"),
			"solving_status": request_data.get("solving_status"),
			"guidance_needed": "Not Provided" if request_data.get("guidance_needed", "").startswith("@") else request_data.get("guidance_needed")
		})
		
		mentorship_request.insert(ignore_permissions=True)
		frappe.db.commit()
		
		doc_name = mentorship_request.name
		data = {
			"id": mentorship_request.name,
			"mentee": mentorship_request.mentee,
			"phone": mentorship_request.phone
		}
		
	except ValueError as e:
		# Validation errors are already handled above
		pass
		
	except Exception as e:
		frappe.log_error(
			f"Error in create_mentorship_request: {str(e)}\n{frappe.get_traceback()}",
			"Mentorship Request API Error"
		)
		message = "Failed to create mentorship request"
		status_code = 500
		error = str(e)
		error_data = {
			"error": str(e),
			"traceback": frappe.get_traceback()
		}
	
	# Log to Integration Request
	response_data = {
		"message": message,
		"status": "error" if error else "success",
		"data": data,
		"status_code": status_code
	}
	
	log_integration_request(
		request_data=request_data,
		response_data=response_data,
		service_name="Create Mentorship Request API",
		request_description="Create new mentorship request via API",
		error_data=error_data,
		reference_doctype="Mentorship Request" if doc_name else None,
		reference_docname=doc_name,
		error_title="Create Mentorship Request"
	)
	
	return custom_response(
		message=message,
		data=data,
		status_code=status_code,
		error=error
	)

