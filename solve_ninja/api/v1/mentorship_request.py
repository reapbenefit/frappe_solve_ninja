import asyncio
import frappe
import json
from samaaja.api.common import custom_response
from solve_ninja.services.mentorship_request_manager import MentorshipRequestManager
from solve_ninja.utils import parse_request_data

@frappe.whitelist(allow_guest=True)
def create():
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
	try:
		request_data = parse_request_data()
		return MentorshipRequestManager.create(request_data).to_custom_response()
	except Exception as e:
		frappe.log_error(f"Error in parse_request_data: {str(e)}")
		return custom_response(
			message="Failed to parse request data",
			data={"error": str(e)},
			status_code=500,
			error=True,
		)

@frappe.whitelist(allow_guest=True)
def get_mentorship_request_for_feedback(request_id):
	"""
	Get mentorship request data for feedback forms.
	Whitelisted for guest access so feedback forms can prefill data.
	"""
	try:
		if not request_id:
			frappe.throw("Request ID is required", frappe.ValidationError)
		if not frappe.db.exists("Mentorship Request", request_id):
			frappe.throw("Mentorship request not found", frappe.DoesNotExistError)
		mentorship_request = frappe.get_doc("Mentorship Request", request_id)
		return {
			"mentor_name": mentorship_request.mentor_name or "",
			"mentee": mentorship_request.mentee or "",
			"mentee_name": mentorship_request.mentee or "",
			"request_id": request_id,
		}
	except Exception as e:
		frappe.log_error(
			f"Error in get_mentorship_request_for_feedback: {str(e)}\n{frappe.get_traceback()}",
			"Mentorship Request Feedback API Error",
		)
		frappe.throw(f"Failed to retrieve mentorship request data: {str(e)}")

