
import frappe
from frappe import qb
from frappe.query_builder.functions import Count, Sum
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_city_wise_ninja_stats(page_length=10, start=0, month=None, year=None):
	"""
	Get city-wise statistics including active ninjas, hours invested, and action count.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- month: Filter by month (1-12, optional but must be provided with year)
	- year: Filter by year (1900-2100, optional but must be provided with month)
	
	Note: Both month and year must be provided together, or neither should be provided.
	
	Returns:
	- city: City name from User Metadata
	- active_ninjas: Count of ninjas with contributions > 0
	- hours_invested: Sum of hours_invested from Ninja Profile
	- action_count: Count of events
	"""
	try:
		from pypika import Order
		from pypika.functions import Count, Sum, Extract
		
		page_length = int(page_length)
		start = int(start)
		
		# Validate month and year - both must be provided together or neither
		month_provided = month is not None and month != ""
		year_provided = year is not None and year != ""
		
		if month_provided != year_provided:
			return custom_response(
				message="Both month and year must be provided together, or neither should be provided",
				data=None,
				status_code=400,
				error="Invalid month/year parameter combination"
			)
		
		if month_provided and year_provided:
			month = int(month)
			year = int(year)
			
			if month < 1 or month > 12:
				return custom_response(
					message="Invalid month. Must be between 1 and 12",
					data=None,
					status_code=400,
					error="Invalid month parameter"
				)
			
			if year < 1900 or year > 2100:
				return custom_response(
					message="Invalid year. Must be between 1900 and 2100",
					data=None,
					status_code=400,
					error="Invalid year parameter"
				)
		
		UserMetadata = frappe.qb.DocType("User Metadata")
		Events = frappe.qb.DocType("Events")
		NinjaProfile = frappe.qb.DocType("Ninja Profile")
		
		# Build base conditions
		base_conditions = (
			(UserMetadata.city.isnotnull()) &
			(UserMetadata.city != "") &
			(NinjaProfile.contributions > 0)
		)
		
		# Build event filter conditions
		event_conditions = []
		if month:
			event_conditions.append(Extract('month', Events.creation) == month)
		if year:
			event_conditions.append(Extract('year', Events.creation) == year)
		
		# Single query to get all stats using LEFT JOIN for events
		query = (
			frappe.qb.from_(UserMetadata)
			.join(NinjaProfile).on(NinjaProfile.name == UserMetadata.name)
			.left_join(Events).on(Events.user == UserMetadata.name)
			.select(
				UserMetadata.city,
				Count(NinjaProfile.name).distinct().as_("active_ninjas"),
				Sum(NinjaProfile.hours_invested).as_("hours_invested"),
				Count(Events.name).as_("action_count")
			)
			.where(base_conditions)
			.groupby(UserMetadata.city)
			.limit(page_length)
			.offset(start)
		)
		
		# Apply event date filters if provided
		if event_conditions:
			for condition in event_conditions:
				query = query.where(condition)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(UserMetadata)
			.join(NinjaProfile).on(NinjaProfile.name == UserMetadata.name)
			.select(Count(UserMetadata.city).distinct().as_("total"))
			.where(base_conditions)
		)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		# Sort by active_ninjas in Python since we need to order after grouping
		result.sort(key=lambda x: x['active_ninjas'], reverse=True)
		
		return custom_response(
			message="City-wise ninja statistics retrieved successfully",
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
					"month": month,
					"year": year
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_city_wise_ninja_stats: {str(e)}")
		return custom_response(
			message="Failed to retrieve city-wise ninja statistics",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_ninjas_in_focus(page_length=10, start=0):
	"""
	Get ninjas in focus with their media, testimonial, and story information.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	
	Returns:
	- name: User name (same as username)
	- full_name: Full name from User doctype
	- username: Username from User doctype
	- user_image: User image from User doctype
	- is_ninja_in_focus: Focus status from User Metadata
	- media: Media content from User Metadata
	- testimonial: Testimonial from User Metadata
	- story: Story from User Metadata
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		UserMetadata = frappe.qb.DocType("User Metadata")
		User = frappe.qb.DocType("User")

		# Build base conditions - only ninjas in focus
		base_conditions = (
			(UserMetadata.is_ninja_in_focus == 1) &
			(UserMetadata.name == User.name)
		)
		
		# Query to get ninjas in focus with user details
		query = (
			frappe.qb.from_(UserMetadata)
			.join(User).on(User.name == UserMetadata.name)
			.select(
				UserMetadata.name,
				UserMetadata.is_ninja_in_focus,
				UserMetadata.media,
				UserMetadata.testimonial,
				UserMetadata.story,
                UserMetadata.active_since,
				User.full_name,
				User.username,
				User.user_image,
				User.creation,
				User.headline
			)
			.where(base_conditions)
			.orderby(UserMetadata.modified, order=frappe.qb.desc)
			.limit(page_length)
			.offset(start)
		)
		
		# Get total count separately
		count_query = (
			frappe.qb.from_(UserMetadata)
			.join(User).on(User.name == UserMetadata.name)
			.select(Count(UserMetadata.name).as_("total"))
			.where(base_conditions)
		)
		
		result = query.run(as_dict=True)

		for row in result:
			row.profile_url = f"{frappe.utils.get_url()}/user-profile/{row.username}"
			row.user_image = f"{frappe.utils.get_url()}{row.user_image}" if row.user_image else None
			row.media = f"{frappe.utils.get_url()}{row.media}" if row.media else None

		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		return custom_response(
			message="Ninjas in focus retrieved successfully",
			data={
				"result": result,
				"pagination": {
					"total_count": total_count,
					"page_length": page_length,
					"start": start,
					"has_next": (start + page_length) < total_count,
					"has_prev": start > 0
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_ninjas_in_focus: {str(e)}")
		return custom_response(
			message="Failed to retrieve ninjas in focus",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_opportunities_for_youth(page_length=10, start=0, city=None, mode=None, skills=None):
	"""
	Get opportunities for youth with filtering by city, mode, and skills.
	
	Args:
	- page_length: Number of results per page (default: 10)
	- start: Starting index for pagination (default: 0)
	- city: Filter by city (list, optional)
	- mode: Filter by mode (list, optional)
	- skills: Filter by skills (list, optional)
	
	Returns:
	- All fields from Opportunity Template doctype
	"""
	try:
		page_length = int(page_length)
		start = int(start)
		
		# Convert string parameters to lists if provided
		if city and isinstance(city, str):
			city = [city]
		elif not city:
			city = []
		# Mode filter only accepts list
		if not mode:
			mode = []
		if skills and isinstance(skills, str):
			skills = [skills]
		elif not skills:
			skills = []
		
		OpportunityTemplate = frappe.qb.DocType("Opportunity Template")
		OpportunitySkill = frappe.qb.DocType("Opportunity Skill")
		
		# Build base conditions
		base_conditions = None
		
		# City filter
		if city:
			base_conditions = OpportunityTemplate.city.isin(city)
		
		# Mode filter
		if mode:
			if base_conditions:
				base_conditions = base_conditions & OpportunityTemplate.mode.isin(mode)
			else:
				base_conditions = OpportunityTemplate.mode.isin(mode)
		
		# Skills filter - using child table join
		skills_conditions = None
		if skills:
			skills_conditions = OpportunitySkill.skill_name.isin(skills)
		
		# Build query
		query = (
			frappe.qb.from_(OpportunityTemplate)
			.select(
				OpportunityTemplate.name,
				OpportunityTemplate.eligibility_criteria,
				OpportunityTemplate.opp_description,
				OpportunityTemplate.deadline,
				OpportunityTemplate.opp_type,
				OpportunityTemplate.location,
				OpportunityTemplate.city,
				OpportunityTemplate.start_date,
				OpportunityTemplate.stipend_amount,
				OpportunityTemplate.mode,
				OpportunityTemplate.whatsapp_keyword,
				OpportunityTemplate.header_logo,
				OpportunityTemplate.url
			)
		)
		
		# Add DISTINCT if skills filter is applied to avoid duplicates
		if skills_conditions is not None:
			query = query.distinct()
			# Add modified field to SELECT when using DISTINCT for ORDER BY
			query = query.select(OpportunityTemplate.modified)
		
		# Apply base conditions if any
		if base_conditions is not None:
			query = query.where(base_conditions)
		
		query = query.orderby(OpportunityTemplate.modified, order=frappe.qb.desc).limit(page_length).offset(start)
		
		# Apply skills filter if provided
		if skills_conditions is not None:
			query = query.left_join(OpportunitySkill).on(
				OpportunitySkill.parent == OpportunityTemplate.name
			).where(skills_conditions)
		
		# Get total count separately
		if skills_conditions is not None:
			# For skills filter, count distinct opportunities
			count_query = (
				frappe.qb.from_(OpportunityTemplate)
				.left_join(OpportunitySkill).on(
					OpportunitySkill.parent == OpportunityTemplate.name
				)
				.select(Count(OpportunityTemplate.name).distinct().as_("total"))
			)
			
			# Apply base conditions to count query if any
			if base_conditions is not None:
				count_query = count_query.where(base_conditions)
			
			# Apply skills filter
			count_query = count_query.where(skills_conditions)
		else:
			# No skills filter, simple count
			count_query = (
				frappe.qb.from_(OpportunityTemplate)
				.select(Count(OpportunityTemplate.name).as_("total"))
			)
			
			# Apply base conditions to count query if any
			if base_conditions is not None:
				count_query = count_query.where(base_conditions)
		
		result = query.run(as_dict=True)
		count_result = count_query.run()
		total_count = count_result[0][0] if count_result else 0
		
		# Get skills for each opportunity
		if result:
			opportunity_names = [row['name'] for row in result]
			
			# Fetch skills for all opportunities
			skills_query = (
				frappe.qb.from_(OpportunitySkill)
				.select(OpportunitySkill.parent, OpportunitySkill.skill_name)
				.where(OpportunitySkill.parent.isin(opportunity_names))
			)
			skills_result = skills_query.run(as_dict=True)
			
			# Group skills by opportunity
			skills_by_opportunity = {}
			for skill in skills_result:
				parent = skill['parent']
				if parent not in skills_by_opportunity:
					skills_by_opportunity[parent] = []
				skills_by_opportunity[parent].append(skill['skill_name'])
			
			# Add skills to each opportunity
			for row in result:
				row['header_logo'] = f"{frappe.utils.get_url()}{row['header_logo']}" if row['header_logo'] else None
				row['skills'] = skills_by_opportunity.get(row['name'], [])
		
		return custom_response(
			message="Opportunities for youth retrieved successfully",
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
					"city": city,
					"mode": mode,
					"skills": skills
				}
			},
			status_code=200,
			error=None
		)
		
	except Exception as e:
		frappe.log_error(f"Error in get_opportunities_for_youth: {str(e)}")
		return custom_response(
			message="Failed to retrieve opportunities for youth",
			data=None,
			status_code=500,
			error=str(e)
		)

@frappe.whitelist(allow_guest=True)
def get_learn_page_content(language='en'):
    """
    Get all learn page content for a specific language
    
    Args:
        language (str): Language code ('en' or 'hi')
    
    Returns:
        dict: All learn page content fields
    """
    try:
        learn_content_docs= frappe.db.get_all('Learn Page Content',filters={'language':language, 'is_active':1},fields=['name'])
        
        
        if len(learn_content_docs) == 0:
            return custom_response(
				message=f"No active learn page content found for the specified language {language}",
				data=None,
				status_code=404,
				error=f"Learn Page Content not found for the specified language {language}"
			)
		
        learn_content = frappe.get_doc("Learn Page Content", learn_content_docs[0].name)
		# Return all fields as a flat dictionary
        return {
            # Basic Info
            'language': learn_content.language,
            'name': learn_content.name,
            'is_active': learn_content.is_active,
            
            # Hero Section
            'learn_hero_subtitle': learn_content.learn_hero_subtitle,
            'learn_hero_title': learn_content.learn_hero_title,
            'learn_hero_description': learn_content.learn_hero_description,
            'learn_hero_methodology': learn_content.learn_hero_methodology,
            'learn_hero_program_rating': learn_content.learn_hero_program_rating,
            'learn_hero_built_skills': learn_content.learn_hero_built_skills,
            'learn_hero_youth_engaged': learn_content.learn_hero_youth_engaged,
			'learn_hero_actionsrecorded': learn_content.learn_hero_actionsrecorded,
            
			#Skill projects section
			'learn_skill_based_projects_title': learn_content.learn_skill_based_projects_title,
			'learn_skill_based_projects_filters': learn_content.learn_skill_based_projects_filters,
			'learn_skill_based_projects_skills': learn_content.learn_skill_based_projects_skills,
			'learn_skill_based_projects_detail_labels_location': learn_content.learn_skill_based_projects_detail_labels_location,
			'learn_skill_based_projects_join': learn_content.learn_skill_based_projects_join,			
			'learn_skill_based_projects_clear_all': learn_content.learn_skill_based_projects_clear_all,
			'learn_skill_based_projects_know_more_label': learn_content.learn_skill_based_projects_know_more_label,
			'learn_skill_based_projects_members_needed_label': learn_content.learn_skill_based_projects_members_needed_label,
			'learn_skill_based_projects_members_description_label': learn_content.learn_skill_based_projects_members_description_label,
			'learn_skill_based_projects_members_popup_close_label': learn_content.learn_skill_based_projects_members_popup_close_label,

            # Solver Jam Section
            'learn_solver_jam_title': learn_content.learn_solver_jam_title,
            'learn_solver_jam_description': learn_content.learn_solver_jam_description,
            'learn_solver_jam_register_now': learn_content.learn_solver_jam_register_now,
            'learn_solver_jam_event_completed': learn_content.learn_solver_jam_event_completed,
            'learn_solver_jam_upcoming_events_text': learn_content.learn_solver_jam_upcoming_events_text,
            'learn_solver_jam_past_events_text': learn_content.learn_solver_jam_past_events_text,
            
            # Mentors Section
            'learn_mentors_title': learn_content.learn_mentors_title,
            'learn_mentors_cta_title': learn_content.learn_mentors_cta_title,
            'learn_mentors_cta_description': learn_content.learn_mentors_cta_description,
            'learn_mentors_cta_button': learn_content.learn_mentors_cta_button,
            'learn_mentors_available': learn_content.learn_mentors_available,
            'learn_mentors_slots_full': learn_content.learn_mentors_slots_full,
            
            # Ninjas of Month Section
            'learn_ninjas_of_month_title': learn_content.learn_ninjas_of_month_title,
            'learn_ninjas_of_month_view_profile': learn_content.learn_ninjas_of_month_view_profile,
			'learn_ninjas_of_month_action_taken_label': learn_content.learn_ninjas_of_month_action_taken_label,
            
            # CTA Section
            'learn_cta_title': learn_content.learn_cta_title,
            'learn_cta_button_text': learn_content.learn_cta_button_text
        }
        
    except frappe.DoesNotExistError:
        return custom_response(
			message=f"No active learn page content found for the specified language {language}",
			data=None,
			status_code=404,
			error=f"Learn Page Content not found for the specified language {language}"
		)
    except Exception as e:
        frappe.log_error(f"Error in get_learn_page_content: {str(e)}")
        return custom_response(
			message="Error retrieving learn page content",
			data=None,
			status_code=500,
			error="Error retrieving learn page content " + str(e)
		)
@frappe.whitelist(allow_guest=True)
def get_connect_page_content(language='en'):
    """
    Get all connect page content for a specific language
    
    Args:
        language (str): Language code ('en' or 'hi')
    
    Returns:
        dict: All connect page content fields
    """
    try:
        connect_content_docs = frappe.db.get_all('Connect Page Content', filters={'language': language, 'is_active': 1}, fields=['name'])
        
        if len(connect_content_docs) == 0:
            return custom_response(
                message=f"No active connect page content found for the specified language {language}",
                data=None,
                status_code=404,
                error=f"Connect Page Content not found for the specified language {language}"
            )
        
        connect_content = frappe.get_doc("Connect Page Content", connect_content_docs[0].name)
        # Return all fields as a flat dictionary
        return {
            # Basic Info
            'language': connect_content.language,
            'name': connect_content.name,
            'is_active': connect_content.is_active,
            
            # Ways to Connect Section
            'ways_to_connect_title': connect_content.ways_to_connect_title,
            'ways_to_connect_description': connect_content.ways_to_connect_description,
            
            # SolveCon Section
            'solvecon_title': connect_content.solvecon_title,
            'solvecon_description': connect_content.solvecon_description,
            'solvecon_tag_in_person': connect_content.solvecon_tag_in_person,
            'solvecon_tag_workshops': connect_content.solvecon_tag_workshops,
            'solvecon_tag_talks': connect_content.solvecon_tag_talks,
            'solvecon_link': connect_content.solvecon_link,
            
            # Changemaker Adda Section
            'changemaker_adda_title': connect_content.changemaker_adda_title,
            'changemaker_adda_description': connect_content.changemaker_adda_description,
            'changemaker_adda_tag_online': connect_content.changemaker_adda_tag_online,
            'changemaker_adda_tag_stories': connect_content.changemaker_adda_tag_stories,
            'changemaker_adda_tag_community': connect_content.changemaker_adda_tag_community,
            'changemaker_adda_link': connect_content.changemaker_adda_link,
            
            # Experience the Energy Section
            'experience_energy_title': connect_content.experience_energy_title,
            'experience_energy_subtitle': connect_content.experience_energy_subtitle,
            'experience_energy_explore_button': connect_content.experience_energy_explore_button,
            
            # Gatherings Section
            'gatherings_title': connect_content.gatherings_title,
            'gatherings_select_city': connect_content.gatherings_select_city,
			'gatherings_tab_all_events': connect_content.gatherings_tab_all_events,
            'event_registration_button': connect_content.event_registration_button,
            
            # Want SolveCon Section
            'want_solvecon_title': connect_content.want_solvecon_title,
            'want_solvecon_description': connect_content.want_solvecon_description,
            'want_solvecon_mobile_description': connect_content.want_solvecon_mobile_description,
            
            # Request Option
            'request_option_title': connect_content.request_option_title,
            'request_button': connect_content.request_button,
            
            # Organize Option
            'organize_button': connect_content.organize_button,
            
            # Map Section
            'map_title': connect_content.map_title,
            'map_description': connect_content.map_description,
            
            # Map Events
            'map_event_mumbai_name': connect_content.map_event_mumbai_name,
            'map_event_mumbai_details': connect_content.map_event_mumbai_details,
            'map_event_delhi_name': connect_content.map_event_delhi_name,
            'map_event_delhi_details': connect_content.map_event_delhi_details,
            'map_event_bangalore_name': connect_content.map_event_bangalore_name,
            'map_event_bangalore_details': connect_content.map_event_bangalore_details,
            
            # Footer
            'footer_text': connect_content.footer_text,
            'footer_button': connect_content.footer_button,
            'pathways_title': connect_content.pathways_title
        }
        
    except frappe.DoesNotExistError:
        return custom_response(
            message=f"No active connect page content found for the specified language {language}",
            data=None,
            status_code=404,
            error=f"Connect Page Content not found for the specified language {language}"
        )
    except Exception as e:
        frappe.log_error(f"Error in get_connect_page_content: {str(e)}")
        return custom_response(
            message="Error retrieving connect page content",
            data=None,
            status_code=500,
            error="Error retrieving connect page content " + str(e)
        )
	
@frappe.whitelist(allow_guest=True)
def get_lead_page_content(language='en'):
    """
    Get all lead page content for a specific language
    
    Args:
        language (str): Language code ('en' or 'hi')
    
    Returns:
        dict: All lead page content fields
    """
    try:
        lead_content_docs = frappe.db.get_all('Lead Page Content', filters={'language': language, 'is_active': 1}, fields=['name'])
        
        if len(lead_content_docs) == 0:
            return custom_response(
                message=f"No active lead page content found for the specified language {language}",
                data=None,
                status_code=404,
                error=f"Lead Page Content not found for the specified language {language}"
            )
        
        lead_content = frappe.get_doc("Lead Page Content", lead_content_docs[0].name)
        
        # Return all fields as a flat dictionary
        return {
            # Basic Info
            'language': lead_content.language,
            'name': lead_content.name,
            'is_active': lead_content.is_active,
            
            # Hero Section
            'lead_hero_title': lead_content.lead_hero_title,
            'lead_hero_description': lead_content.lead_hero_description,
            'lead_hero_primary_button': lead_content.lead_hero_primary_button,
            
            # Mentorship Network Section
            'mentorship_network_title': lead_content.mentorship_network_title,
            'mentorship_network_description': lead_content.mentorship_network_description,
            'mentorship_network_primary_button': lead_content.mentorship_network_primary_button,
            'mentorship_network_secondary_button': lead_content.mentorship_network_secondary_button,
            'mentorship_network_card_title': lead_content.mentorship_network_card_title,
            'mentorship_network_card_description': lead_content.mentorship_network_card_description,
            
            # Changemaker Fund Section
            'changemaker_fund_title': lead_content.changemaker_fund_title,
            'changemaker_fund_description': lead_content.changemaker_fund_description,
            'changemaker_fund_funded_badge': lead_content.changemaker_fund_funded_badge,
            'changemaker_fund_cta_button': lead_content.changemaker_fund_cta_button,
            'changemaker_fund_ninja_label': lead_content.changemaker_fund_ninja_label,
            'changemaker_fund_grant_label': lead_content.changemaker_fund_grant_label,
            'changemaker_fund_outcome_label': lead_content.changemaker_fund_outcome_label,
            
            # Changemaker Fund Stats
            'changemaker_fund_stat_1_label': lead_content.changemaker_fund_stat_1_label,
            'changemaker_fund_stat_1_value': lead_content.changemaker_fund_stat_1_value,
            'changemaker_fund_stat_1_description': lead_content.changemaker_fund_stat_1_description,
            'changemaker_fund_stat_2_label': lead_content.changemaker_fund_stat_2_label,
            'changemaker_fund_stat_2_value': lead_content.changemaker_fund_stat_2_value,
            'changemaker_fund_stat_2_description': lead_content.changemaker_fund_stat_2_description,
            'changemaker_fund_stat_3_label': lead_content.changemaker_fund_stat_3_label,
            'changemaker_fund_stat_3_value': lead_content.changemaker_fund_stat_3_value,
            'changemaker_fund_stat_3_description': lead_content.changemaker_fund_stat_3_description,
            
            
            # City Chapters Section
            'city_chapters_title': lead_content.city_chapters_title,
            'city_chapters_description': lead_content.city_chapters_description,
            'city_chapters_pathways_title': lead_content.city_chapters_pathways_title,
            'city_chapters_start_chapter_button': lead_content.city_chapters_start_chapter_button,
            'city_chapters_lead_chapter_button': lead_content.city_chapters_lead_chapter_button,
            'city_chapters_community_highlight_title': lead_content.city_chapters_community_highlight_title,
            
            # City Chapters Stats
            'city_chapters_stat_1_label': lead_content.city_chapters_stat_1_label,
            'city_chapters_stat_1_value': lead_content.city_chapters_stat_1_value,
            'city_chapters_stat_2_label': lead_content.city_chapters_stat_2_label,
            'city_chapters_stat_2_value': lead_content.city_chapters_stat_2_value,
            'city_chapters_stat_3_label': lead_content.city_chapters_stat_3_label,
            'city_chapters_stat_3_value': lead_content.city_chapters_stat_3_value,
            
            # City Chapters Mobile Stats
            'city_chapters_mobile_stat_1_label': lead_content.city_chapters_mobile_stat_1_label,
            'city_chapters_mobile_stat_1_value': lead_content.city_chapters_mobile_stat_1_value,
            'city_chapters_mobile_stat_2_label': lead_content.city_chapters_mobile_stat_2_label,
            'city_chapters_mobile_stat_2_value': lead_content.city_chapters_mobile_stat_2_value,
            'city_chapters_mobile_stat_3_label': lead_content.city_chapters_mobile_stat_3_label,
            'city_chapters_mobile_stat_3_value': lead_content.city_chapters_mobile_stat_3_value,
            'city_chapters_mobile_stat_4_label': lead_content.city_chapters_mobile_stat_4_label,
            'city_chapters_mobile_stat_4_value': lead_content.city_chapters_mobile_stat_4_value,
            
            # CTA Section
            'lead_cta_title': lead_content.lead_cta_title,
            'lead_cta_button_text': lead_content.lead_cta_button_text
        }
        
    except frappe.DoesNotExistError:
        return custom_response(
            message=f"No active lead page content found for the specified language {language}",
            data=None,
            status_code=404,
            error=f"Lead Page Content not found for the specified language {language}"
        )
    except Exception as e:
        frappe.log_error(f"Error in get_lead_page_content: {str(e)}")
        return custom_response(
            message="Error retrieving lead page content",
            data=None,
            status_code=500,
            error="Error retrieving lead page content " + str(e)
        )
	
@frappe.whitelist(allow_guest=True)
def get_home_page_content(language='en'):
    """
    Get all home page content for a specific language
    
    Args:
        language (str): Language code
    
    Returns:
        dict: All home page content fields
    """
    try:
        
        # Get the home page content record 
        home_content_docs= frappe.db.get_all('Home Page Content',filters={'language':language, 'is_active':1},fields=['name'])
		
        if len(home_content_docs) == 0:
            return custom_response(
				message=f"No active home page content found for the specified language {language}",
				data=None,
				status_code=404,
				error=f"Home Page Content not found for the specified language {language}"
			)
		
        home_content = frappe.get_doc("Home Page Content", home_content_docs[0].name)


        # Return all fields as a flat dictionary
        return {
            # Basic Info
            'language': home_content.language,
            'name': home_content.name,
            'is_active': home_content.is_active,
            
            # Hero Section
            'hero_subtitle': home_content.hero_subtitle,
            'hero_title': home_content.hero_title,
            'hero_title_highlight': home_content.hero_title_highlight,
            'hero_description': home_content.hero_description,
            'hero_cta': home_content.hero_cta,
            
            # Features Section
            'features_title': home_content.features_title,
            'features_learn_image': home_content.features_learn_image,
            'features_learn_title': home_content.features_learn_title,
            'features_learn_description': home_content.features_learn_description,
            'features_learn_link_cta': home_content.features_learn_link_cta,
            'features_connect_image': home_content.features_connect_image,
            'features_connect_title': home_content.features_connect_title,
            'features_connect_description': home_content.features_connect_description,
            'features_connect_link_cta': home_content.features_connect_link_cta,
            'features_lead_image': home_content.features_lead_image,
            'features_lead_title': home_content.features_lead_title,
            'features_lead_description': home_content.features_lead_description,
            'features_lead_link_cta': home_content.features_lead_link_cta,
            
            # Testimonials Section
            'testimonials_title': home_content.testimonials_title,
            'testimonials_view_profile_cta': home_content.testimonials_view_profile_cta,
            'testimonials_view_story_cta': home_content.testimonials_view_story_cta,
            'testimonials_hide_story_cta': home_content.testimonials_hide_story_cta,
            'testimonials_liked_profiles': home_content.testimonials_liked_profiles,
            'testimonials_create_portfolio': home_content.testimonials_create_portfolio,
            'testimonials_no_ninjas_message': home_content.testimonials_no_ninjas_message,
            'testimonials_story_title': home_content.testimonials_story_title,
			'testimonials_active_since_label': home_content.testimonials_active_since_label,
			'testimonials_theme_label': home_content.testimonials_theme_label,
            'testimonials_testimonial_label': home_content.testimonials_testimonial_label,

            # City Leaderboard Section
            'city_leaderboard_title': home_content.city_leaderboard_title,
            'city_leaderboard_month': home_content.city_leaderboard_month,
            'city_leaderboard_year': home_content.city_leaderboard_year,
            'city_leaderboard_all_time': home_content.city_leaderboard_all_time,
            'city_leaderboard_city': home_content.city_leaderboard_city,
            'city_leaderboard_active_ninjas': home_content.city_leaderboard_active_ninjas,
            'city_leaderboard_hours_invested': home_content.city_leaderboard_hours_invested,
            'city_leaderboard_actions_taken': home_content.city_leaderboard_actions_taken,
            'city_leaderboard_explore_actions': home_content.city_leaderboard_explore_actions,
            'city_leaderboard_explore_actions_cta': home_content.city_leaderboard_explore_actions_cta,
			'city_leaderboard_nodatamessage': home_content.city_leaderboard_nodatamessage,
            
            # Opportunities Section
            'opportunities_title': home_content.opportunities_title,
            'opportunities_filters': home_content.opportunities_filters,
            'opportunities_location': home_content.opportunities_location,
            'opportunities_skills': home_content.opportunities_skills,
            'opportunities_type': home_content.opportunities_type,
            'opportunities_clear_all': home_content.opportunities_clear_all,
            'opportunities_apply': home_content.opportunities_apply,
            'opportunities_know_more': home_content.opportunities_know_more,
            'opportunities_view_all': home_content.opportunities_view_all,
            'opportunities_show_less': home_content.opportunities_show_less,
            'opportunities_no_results': home_content.opportunities_no_results,
            'opportunities_detail_labels_apply_by': home_content.opportunities_detail_labels_apply_by,
			'opportunities_detail_labels_start_date': home_content.opportunities_detail_labels_start_date,
			'opportunities_detail_labels_location': home_content.opportunities_detail_labels_location,
			'opportunities_description_label': home_content.opportunities_description_label,
			'opportunities_eligibility_criteria_label': home_content.opportunities_eligibility_criteria_label,
			'opportunities_popup_close_label': home_content.opportunities_popup_close_label,
            
            # Footer Section
            'footer_follow': home_content.footer_follow,
            'footer_instagram': home_content.footer_instagram,
            'footer_youtube': home_content.footer_youtube,
            'footer_linkedin': home_content.footer_linkedin,
            'footer_twitter': home_content.footer_twitter,
            'footer_facebook': home_content.footer_facebook,
            'footer_contact': home_content.footer_contact,
            'footer_email': home_content.footer_email,
            'footer_phone': home_content.footer_phone,
            'footer_address': home_content.footer_address,
            'footer_accessibility': home_content.footer_accessibility,
            'footer_privacy': home_content.footer_privacy,
            'footer_help_text': home_content.footer_help_text,
            'footer_home': home_content.footer_home,
            'footer_programs': home_content.footer_programs,
            'footer_opportunities': home_content.footer_opportunities,
            'footer_profile': home_content.footer_profile,
            'footer_copyright': home_content.footer_copyright
        }
        
    except frappe.DoesNotExistError:
        return custom_response(
			message=f"No active home page content found for the specified language {language}",
			data=None,
			status_code=404,
			error=f"Home Page Content not found for the specified language {language}"
		)
    except Exception as e:
        frappe.log_error(f"Error in get_home_page_content: {str(e)}")
        return custom_response(
			message="Error retrieving home page content",
			data=None,
			status_code=500,
			error="Error retrieving home page content " + str(e)
		)
