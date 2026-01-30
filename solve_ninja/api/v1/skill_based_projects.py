import frappe
from frappe import qb
from frappe.query_builder.functions import Count
from frappe.query_builder import Case
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


@frappe.whitelist(allow_guest=True)
def get_projects(page_length=10, start=0, project_name=None, status=None, tags=None):
	"""
	Get skill-based projects with pagination and filtering.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- project_name: Filter by project name using LIKE (optional, string)
	- status: Filter by project_status (optional, can be string or list)
	- tags: Filter by project tags from child table (optional, can be string or list)
	
	Returns:
	- project_name: Name of the project
	- project_image: Project image (converted to full URL)
	- project_tags: Array of tag objects from child table
	- impact_metric: Array of impact metric objects from child table
	- average_rating_value: Average rating value
	- Pagination metadata
	"""
	try:
		from pypika import Order
		
		page_length = int(page_length)
		start = int(start)
		
		# Parse filters - ensure tags and status are always arrays
		if tags and isinstance(tags, str):
			tags = [tags]
		elif not tags:
			tags = []
			
		if status and isinstance(status, str):
			status = [status]
		elif not status:
			status = []
		
		# Build base query
		SkillBasedProjects = frappe.qb.DocType("Skill Based Projects")
		ProjectTags = frappe.qb.DocType("Skill Based Projects Tag Detail")
		
		# Build base conditions
		base_conditions = None
		
		# Project name LIKE filter
		if project_name:
			project_name_condition = SkillBasedProjects.project_name.like(f"%{project_name}%")
			base_conditions = project_name_condition
		
		# Status filter
		if status:
			status_condition = SkillBasedProjects.project_status.isin(status)
			if base_conditions:
				base_conditions = base_conditions & status_condition
			else:
				base_conditions = status_condition
		
		# Tags filter - will be handled with JOIN
		tags_condition = None
		if tags:
			tags_condition = ProjectTags.tag.isin(tags)
		
		# Custom ordering: Live first, then Completed, then by modified DESC
		# Use CASE statement to assign priority: Live=1, Completed=2, NULL=3
		status_order = Case().when(SkillBasedProjects.project_status == "Live", 1).when(
			SkillBasedProjects.project_status == "Completed", 2
		).else_(3).as_("status_order")
		
		# Build main query
		query = (
			frappe.qb.from_(SkillBasedProjects)
			.select(
				SkillBasedProjects.name,
				SkillBasedProjects.project_name,
				SkillBasedProjects.project_image,
				SkillBasedProjects.average_rating_value,
				SkillBasedProjects.project_status,
				SkillBasedProjects.overview,
				SkillBasedProjects.detailed_description_title,
				SkillBasedProjects.detailed_description_content,
				SkillBasedProjects.modified,
				SkillBasedProjects.start_date,
				SkillBasedProjects.end_date,
				SkillBasedProjects.participation_count,
				SkillBasedProjects.time_spent_value,
				SkillBasedProjects.completion_count,
				SkillBasedProjects.actions_taken_value,
				SkillBasedProjects.skill,
				SkillBasedProjects.city,
				SkillBasedProjects.action_summary,
				status_order
			)
		)
		
		# Add DISTINCT if tags filter is applied to avoid duplicates
		if tags_condition is not None:
			query = query.distinct()
			# LEFT JOIN with tags table for filtering
			query = query.left_join(ProjectTags).on(
				ProjectTags.parent == SkillBasedProjects.name
			)
		
		# Apply base conditions if any
		if base_conditions is not None:
			query = query.where(base_conditions)
		
		# Apply tags filter if provided
		if tags_condition is not None:
			query = query.where(tags_condition)
		
		# Order by status priority first, then modified DESC
		# Use the Case expression alias in orderby
		query = query.orderby(status_order, order=frappe.qb.asc)
		query = query.orderby(SkillBasedProjects.modified, order=frappe.qb.desc)
		
		# Apply pagination
		query = query.limit(page_length).offset(start)
		
		# Execute query
		result = query.run(as_dict=True)
		
		# Get total count separately with same filters
		count_query = (
			frappe.qb.from_(SkillBasedProjects)
			.select(Count(SkillBasedProjects.name).as_("total"))
		)
		
		# Apply same filters to count query
		if tags_condition is not None:
			count_query = count_query.distinct().left_join(ProjectTags).on(
				ProjectTags.parent == SkillBasedProjects.name
			)
		
		if base_conditions is not None:
			count_query = count_query.where(base_conditions)
		
		if tags_condition is not None:
			count_query = count_query.where(tags_condition)
		
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		# Fetch child table data for each project
		project_names = [row.name for row in result]
		
		# Fetch project tags
		project_tags_map = {}
		if project_names:
			tags_data = frappe.db.get_all(
				"Skill Based Projects Tag Detail",
				filters={"parent": ["in", project_names]},
				fields=["parent", "tag"]
			)
			for tag_row in tags_data:
				if tag_row.parent not in project_tags_map:
					project_tags_map[tag_row.parent] = []
				project_tags_map[tag_row.parent].append(tag_row.tag)
		
		# Fetch impact metrics
		impact_metric_map = {}
		if project_names:
			impact_data = frappe.db.get_all(
				"Skill Based Projects Impact Metric",
				filters={"parent": ["in", project_names]},
				fields=["parent", "title", "value","image"]
			)
			for impact_row in impact_data:
				if impact_row.parent not in impact_metric_map:
					impact_metric_map[impact_row.parent] = []
				impact_metric_map[impact_row.parent].append({
					"title": impact_row.title,
					"value": impact_row.value,
					"image": f"{frappe.utils.get_url()}{impact_row.image}" if impact_row.image else None	
				})
		
		key_objectives_map = {}
		if project_names:
			key_objectives_data = frappe.db.get_all(
				"Skill Based Projects Objective",
				filters={"parent": ["in", project_names]},
				fields=["parent", "objective"]
			)
			for key_objective_row in key_objectives_data:
				if key_objective_row.parent not in key_objectives_map:
					key_objectives_map[key_objective_row.parent] = []
				key_objectives_map[key_objective_row.parent].append(key_objective_row.objective)
		# Process results: attach child table data and convert image URLs
		for row in result:
			# Remove status_order from response
			if "status_order" in row:
				del row["status_order"]
			if "modified" in row:
				del row["modified"]
			
			# Attach child table data
			row["project_tags"] = project_tags_map.get(row.name, [])
			row["impact_metric"] = impact_metric_map.get(row.name, [])
			row["key_objectives"] = key_objectives_map.get(row.name, [])
			# Convert image to full URL
			if row.get("project_image"):
				row["project_image"] = f"{frappe.utils.get_url()}{row.project_image}"
		
		# Calculate pagination info
		has_next = (start + page_length) < total_count
		has_prev = start > 0
		
		response_data = {
			"data": result,
			"pagination": {
				"total_count": total_count,
				"page_length": page_length,
				"start": start,
				"has_next": has_next,
				"has_prev": has_prev
			},
			"filters": {
				"project_name": project_name,
				"status": status,
				"tags": tags
			}
		}
		
		return custom_response(
			message="Projects retrieved successfully",
			data=response_data,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_projects: {str(e)}", "get_projects API Error")
		return custom_response(
			message="Failed to retrieve projects",
			data=None,
			status_code=500,
			error=str(e)
		)


@frappe.whitelist(allow_guest=True)
def get_project_details(id):
	"""
	Get detailed information for a specific skill-based project by ID.
	
	Args:
	- id: Name/ID of the project (mandatory)
	
	Returns:
	- All project fields
	- project_tags: List of tag strings
	- impact_metric: List of dicts with title and value
	- key_objectives: List of objective strings
	"""
	try:
		# Validate id parameter
		if not id:
			return custom_response(
				message="Project ID is required",
				data=None,
				status_code=400,
				error="Missing id parameter"
			)
		
		# Check if project exists
		if not frappe.db.exists("Skill Based Projects", id):
			return custom_response(
				message="Project not found",
				data=None,
				status_code=404,
				error=f"Skill Based Project '{id}' does not exist"
			)
		
		# Get project document with all fields
		project = frappe.get_doc("Skill Based Projects", id)
		project_dict = project.as_dict()
		
		# Fetch project tags as simple list of tag strings
		project_tags = []
		tags_data = frappe.db.get_all(
			"Skill Based Projects Tag Detail",
			filters={"parent": id},
			fields=["tag"]
		)
		for tag_row in tags_data:
			if tag_row.tag:
				project_tags.append(tag_row.tag)
		
		# Fetch impact metrics as list of dicts with title and value
		impact_metrics = []
		impact_data = frappe.db.get_all(
			"Skill Based Projects Impact Metric",
			filters={"parent": id},
			fields=["title", "value"]
		)
		for impact_row in impact_data:
			impact_metrics.append({
				"title": impact_row.title,
				"value": impact_row.value
			})
		
		# Fetch key objectives as simple list of objective strings
		key_objectives = []
		objectives_data = frappe.db.get_all(
			"Skill Based Projects Objective",
			filters={"parent": id},
			fields=["objective"]
		)
		for obj_row in objectives_data:
			if obj_row.objective:
				key_objectives.append(obj_row.objective)
		
		# Attach child table data to project dict
		project_dict["project_tags"] = project_tags
		project_dict["impact_metric"] = impact_metrics
		project_dict["key_objectives"] = key_objectives
		
		# Convert project_image to full URL if present
		if project_dict.get("project_image"):
			project_dict["project_image"] = f"{frappe.utils.get_url()}{project_dict['project_image']}"
		
		return custom_response(
			message="Project details retrieved successfully",
			data=project_dict,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_project_details: {str(e)}", "get_project_details API Error")
		return custom_response(
			message="Failed to retrieve project details",
			data=None,
			status_code=500,
			error=str(e)
		)


@frappe.whitelist(allow_guest=True)
def get_tags():
	"""
	Get all tags from Skill Based Projects Tag doctype.
	
	Returns:
	- List of tag strings (e.g., ["tag1", "tag2", "tag3"])
	"""
	try:
		# Get all tags using pluck to extract only the tag field values
		tags = frappe.get_all("Skill Based Projects Tag", pluck="tag")
		
		return custom_response(
			message="Tags retrieved successfully",
			data=tags,
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_tags: {str(e)}", "get_tags API Error")
		return custom_response(
			message="Failed to retrieve tags",
			data=None,
			status_code=500,
			error=str(e)
		)
