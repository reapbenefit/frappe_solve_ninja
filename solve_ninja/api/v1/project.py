import frappe
from frappe import qb
from frappe.query_builder.functions import Count
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_funded_projects(page_length=10, start=0, city=None, project_type=None, status=None):
	"""
	Get funded projects with pagination and filtering, ordered by creation desc.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- city: Filter by city (optional, can be string or list)
	- project_type: Filter by project type (optional, can be string or list)
	- status: Filter by project status (optional, can be string or list)
	
	Returns:
	- All fields from Funded Project doctype ordered by creation desc
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		# Convert string parameters to lists if provided
		if city and isinstance(city, str):
			city = [city]
		elif not city:
			city = []
		if project_type and isinstance(project_type, str):
			project_type = [project_type]
		elif not project_type:
			project_type = []
		if status and isinstance(status, str):
			status = [status]
		elif not status:
			status = []
		
		FundedProject = frappe.qb.DocType("Funded Project")
		
		# Build base conditions
		base_conditions = None
		
		# City filter
		if city:
			base_conditions = FundedProject.city.isin(city)
		
		# Project type filter
		if project_type:
			project_type_condition = FundedProject.project_type.isin(project_type)
			if base_conditions:
				base_conditions = base_conditions & project_type_condition
			else:
				base_conditions = project_type_condition
		
		# Status filter
		if status:
			status_condition = FundedProject.status.isin(status)
			if base_conditions:
				base_conditions = base_conditions & status_condition
			else:
				base_conditions = status_condition
		
		# Build query
		query = (
			frappe.qb.from_(FundedProject)
			.select(
				FundedProject.name,
				FundedProject.title,
				FundedProject.lead_ninja_name,
				FundedProject.city,
				FundedProject.description,
				FundedProject.grant_amount,
				FundedProject.funded_date,
				FundedProject.theme,
				FundedProject.media_link,
				FundedProject.outcome_summary,
				FundedProject.testimonial,
				FundedProject.image,
			)
			.orderby(FundedProject.creation, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Apply conditions if any
		if base_conditions:
			query = query.where(base_conditions)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(FundedProject)
			.select(Count(FundedProject.name).as_("total"))
		)
		
		# Apply same conditions to count query
		if base_conditions:
			count_query = count_query.where(base_conditions)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		# Process media link URLs
		for row in result:
			if row.get("image"):
				row.image = f"{frappe.utils.get_url()}{row.image}"
		
		return custom_response(
			message="Funded projects retrieved successfully",
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
					"project_type": project_type,
					"status": status
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_funded_projects: {str(e)}")
		return custom_response(
			message="Failed to retrieve funded projects",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_funded_project_details(project_name):
	"""
	Get detailed information for a specific funded project.
	
	Args:
	- project_name: Name/ID of the funded project
	
	Returns:
	- Complete project details including all fields
	"""
	try:
		if not project_name:
			return custom_response(
				message="Project name is required",
				data=None,
				status_code=400,
				error="Missing project_name parameter"
			)
		
		# Check if project exists
		if not frappe.db.exists("Funded Project", project_name):
			return custom_response(
				message="Project not found",
				data=None,
				status_code=404,
				error=f"Funded Project '{project_name}' does not exist"
			)
		
		# Get project details
		project = frappe.get_doc("Funded Project", project_name)
		project_dict = project.as_dict()
		
		# Process media link URL
		if project_dict.get("media_link"):
			project_dict["media_link"] = f"{frappe.utils.get_url()}{project_dict['media_link']}"
		
		return custom_response(
			message="Project details retrieved successfully",
			data=project_dict,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_funded_project_details: {str(e)}")
		return custom_response(
			message="Failed to retrieve project details",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_funded_projects_by_status(status, page_length=10, start=0):
	"""
	Get funded projects filtered by specific status, ordered by creation desc.
	
	Args:
	- status: Project status to filter by (required)
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	
	Returns:
	- Funded projects with specified status, ordered by creation desc
	"""
	try:
		if not status:
			return custom_response(
				message="Status parameter is required",
				data=None,
				status_code=400,
				error="Missing status parameter"
			)
		
		page_length = int(page_length)
		start = int(start)
		
		FundedProject = frappe.qb.DocType("Funded Project")
		
		# Build query with status filter
		query = (
			frappe.qb.from_(FundedProject)
			.select(
				FundedProject.name,
				FundedProject.title,
				FundedProject.lead_ninja_name,
				FundedProject.city,
				FundedProject.description,
				FundedProject.grant_amount,
				FundedProject.funded_date,
				FundedProject.theme,
				FundedProject.media_link,
				FundedProject.outcome_summary,
				FundedProject.testimonial,
			)
			.where(FundedProject.status == status)
			.orderby(FundedProject.creation, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Get total count
		count_query = (
			frappe.qb.from_(FundedProject)
			.select(Count(FundedProject.name).as_("total"))
			.where(FundedProject.status == status)
		)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		# Process media link URLs
		for row in result:
			if row.get("media_link"):
				row.media_link = f"{frappe.utils.get_url()}{row.media_link}"
		
		return custom_response(
			message=f"Funded projects with status '{status}' retrieved successfully",
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
					"status": status
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_funded_projects_by_status: {str(e)}")
		return custom_response(
			message="Failed to retrieve funded projects by status",
			data=None,
			status_code=500,
			error=str(e)
		)
