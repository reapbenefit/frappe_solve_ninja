import frappe
from frappe import qb
from frappe.query_builder.functions import Count
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_skill_based_projects(page_length=10, start=0, city=None, skill=None):
	"""
	Get skill-based projects with pagination and filtering.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- city: Filter by city (optional, can be string or list)
	- skill: Filter by skill/badge (optional, can be string or list)
	
	Returns:
	- name: Project ID
	- project_title: Title of the project
	- image: Project image (converted to full URL)
	- skill: Required skill/badge
	- no_of_members_needed: Number of members needed
	- city: Project city
	- join_link: Link to join the project
	- creation: Project creation date
	- modified: Project last modified date
	"""
	try:
		from pypika import Order
		
		page_length = int(page_length)
		start = int(start)
		
		# Parse filters - ensure they are always arrays
		if city and isinstance(city, str):
			city = [city]
		elif not city:
			city = []
			
		if skill and isinstance(skill, str):
			skill = [skill]
		elif not skill:
			skill = []
		
		# Build base query
		SkillBasedProjects = frappe.qb.DocType("Skill Based Projects")
		
		query = (
			frappe.qb.from_(SkillBasedProjects)
			.select(
				SkillBasedProjects.name,
				SkillBasedProjects.project_title,
				SkillBasedProjects.image,
				SkillBasedProjects.skill,
				SkillBasedProjects.no_of_members_needed,
				SkillBasedProjects.city,
				SkillBasedProjects.join_link,
				SkillBasedProjects.creation,
				SkillBasedProjects.modified,
				SkillBasedProjects.description
			)
		)
		
		# Apply filters
		conditions = []
		
		if city:
			conditions.append(SkillBasedProjects.city.isin(city))
			
		if skill:
			conditions.append(SkillBasedProjects.skill.isin(skill))
		
		# Combine conditions
		if conditions:
			base_conditions = conditions[0]
			for condition in conditions[1:]:
				base_conditions = base_conditions & condition
			query = query.where(base_conditions)
		
		# Order by creation descending
		query = query.orderby(SkillBasedProjects.creation, order=frappe.qb.desc)
		
		# Apply pagination
		query = query.limit(page_length).offset(start)
		
		# Execute query
		result = query.run(as_dict=True)
		
		# Convert image to full URL
		for row in result:
			if row.image:
				row.image = f"{frappe.utils.get_url()}{row.image}"
		
		# Get total count for pagination
		count_query = (
			frappe.qb.from_(SkillBasedProjects)
			.select(Count(SkillBasedProjects.name).as_("total"))
		)
		
		if conditions:
			count_query = count_query.where(base_conditions)
		
		total_count = count_query.run(as_dict=True)[0].total
		
		# Calculate pagination info
		has_next = (start + page_length) < total_count
		has_prev = start > 0
		
		response_data = {
			"result": result,
			"total_count": total_count,
			"page_length": page_length,
			"start": start,
			"has_next": has_next,
			"has_prev": has_prev,
			"filters": {
				"city": city,
				"skill": skill
			}
		}
		
		return custom_response(
			message="Skill-based projects retrieved successfully",
			data=response_data,
			status_code=200
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_skill_based_projects: {str(e)}")
		return custom_response(
			message="Failed to retrieve skill-based projects",
			data=None,
			status_code=500,
			error=str(e)
		)








