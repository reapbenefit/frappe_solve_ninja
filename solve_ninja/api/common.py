import json
import string
import random
import frappe
from werkzeug.wrappers import Response
from datetime import date
from datetime import datetime
from frappe.utils import logger
import pytz
from http import HTTPStatus
from samaaja.api.common import custom_response

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)
API_KEY = "HeMflsqk-2yJu3Q5mDn9-C_LIasjTXF72n5qpae1GOQu-8Oe0i_Loc4wl3iJSBt-"
INFERENCE_URL = "https://api.dhruva.ai4bharat.org/services/inference"


@frappe.whitelist(allow_guest=True)
def add_event():
    logger.info('STARTS - adding a new event ------------')
    message='event added successfully'
    data=''
    status_code=200
    error=False
    try:
        logger.info(frappe.request.data)
        event_data = json.loads(frappe.request.data)
        event_doc = frappe.get_doc({'doctype': 'Events', 'title':event_data.get("title")})
        event_doc.user=event_data.get("mobile")+"@solveninja.org"
        event_doc.type=event_data.get("type")
        event_doc.category=event_data.get("category")
        event_doc.subcategory=event_data.get("subcategory")
        event_doc.description=event_data.get("description")
        event_doc.url=event_data.get("attachment")
        event_doc.source=event_data.get("source")
        event_doc.hours_invested =event_data.get("hours_invested")
        event_doc.latitude =event_data.get("latitude")
        event_doc.longitude =event_data.get("longitude")
        event_doc.insert(ignore_permissions=True)
        logger.info('ENDS - adding a new event ------------')
        return custom_response('', 200)
    except Exception as e:
        frappe.log_error()
        logger.error(e, exc_info=True)
        message=str(e)
        status_code=500
        error=True
    return custom_response(message,data,status_code,error)

@frappe.whitelist(allow_guest=True)
def highlight_event():
    logger.info('STARTS - highlighting an event ------------')
    message='event highlighted'
    data=''
    status_code=200
    error=False
    event_id=''
    try:
        logger.info(frappe.request)
        req_data = json.loads(frappe.request.data)
        event_id = req_data.get("event_id")
        user_docs = frappe.db.get_all('User', filters={'username':req_data.get("username")},fields=['name'])
        
        user_events= frappe.db.get_all('Events',filters={'user':user_docs[0].name},fields=['name'])
        for event in user_events:
            
            event_doc = frappe.get_doc('Events',event.name)
            if event_doc.name == event_id:
                logger.info(f'highlighting event with id - {event_id}')
                event_doc.highlight = 1
            else:
                event_doc.highlight = 0
            event_doc.save(ignore_permissions=True)
            frappe.db.commit()
        
    except Exception as e:
        logger.error(f'Error occured while highlighting event with id  - {event_id}')
        logger.error(e, exc_info=True)
        message=str(e)
        status_code=500
        error=True
    logger.info('ENDS - highlighting an event ------------')
    return custom_response(message,data,status_code,error)


@frappe.whitelist(allow_guest=True)
def search_users():
    logger.info('STARTS - searching users ------------')
    message='search completed successfully'
    data=''
    status_code=200
    error=False
    mobile=''
    try:
        logger.info(frappe.request.data)
        search_data = json.loads(frappe.request.data).get("search_string")
        users = frappe.db.get_all('User',filters={'full_name': ['like', '%'+search_data+'%']},fields=['name','username','full_name','user_image','location'])
        
        for user in users:
            result = frappe.db.sql("""select coalesce(SUM(nullif(e.hours_invested, 0)::float), 0) 
            as hours_invested, count(*) as contribution_count from  `tabEvents` e where e.user = %s""", user.name,as_dict=True)
            user["hours_invested"] = round(result[0].hours_invested,2)
            user["contribution_count"] = result[0].contribution_count

            user_badges = frappe.db.get_all('User badge', filters={'user':user.name},fields=['badge'])
            curious_cat_badge = frappe.get_doc('Badge','Curious Cat')
            persona_counts=0
            persona = {
                'name':curious_cat_badge.title,
                'image':curious_cat_badge.icon,
                'description':str(curious_cat_badge.description).split("^")[0].strip(),
                'characteristics':str(curious_cat_badge.description).split("^")[1].strip().split("\n"),
            }
            for user_badge in user_badges:
                badge_doc = frappe.get_doc('Badge',user_badge.badge)
                badge_tags= badge_doc.get_tags()
    
                if badge_tags[0] == 'persona':
                    if persona_counts == 0 :
                        persona_counts = persona_counts+1
                        persona['name']  = badge_doc.title
                        persona['image'] = badge_doc.icon
                        persona['description'] = str(badge_doc.description).split("^")[0].strip()
                        persona['characteristics'] = str(badge_doc.description).split("^")[1].strip().split("\n")
                    else:
                        persona_counts = persona_counts+1

                if persona_counts > 1:
                    action_ant_badge = frappe.get_doc('Badge','Action Ant')
                    
                    persona = {
                        'name':action_ant_badge.title,
                        'image':action_ant_badge.icon,
                        'description':str(action_ant_badge.description).split("^")[0].strip(),
                        'characteristics':str(action_ant_badge.description).split("^")[1].strip().split("\n"),
                    }
            user["persona"] = persona               


        data = users    
    except Exception as e:
        logger.error(f'Error occured while searching user ith mobile - {mobile}')
        logger.error(e, exc_info=True)
        message=str(e)
        status_code=500
        error=True
    logger.info('ENDS - searching a new user ------------')
    return custom_response(message,data,status_code,error)

@frappe.whitelist(allow_guest=True)
def add_user():
    logger.info('STARTS - adding a new user ------------')
    message='user added successfully'
    data=''
    status_code=200
    error=False
    mobile=''
    try:
        logger.info(frappe.request.data)
        user_data = json.loads(frappe.request.data)
        mobile = user_data.get("mobile")
        user_doc = frappe.get_doc({'doctype': 'User','mobile':mobile})
        user_doc.email=mobile+"@solveninja.org"
        user_doc.first_name=user_data.get("first_name")
        user_doc.wa_id=user_data.get("wa_id")
        org_docs = frappe.get_all('User Organization',filters={'org_id':str(user_data.get("org_id")).upper()},fields=['name'])
        if len(org_docs) > 0:
            user_doc.org_id=org_docs[0].name
        else:
            logger.error(f'Organization id - {user_data.get("org_id")} was not found while registering user with mobile - {mobile}')
        user_doc.gender=user_data.get("gender")
        language_docs = frappe.get_all('Language',filters={'language_code':user_data.get("language")},fields=['name'])
        if len(language_docs) > 0:
            user_doc.language=language_docs[0].name
        else:
            logger.error(f'Language code - {user_data.get("language")} was not found while registering user with mobile - {mobile}')
        user_doc.age=user_data.get("age")
        user_doc.state =user_data.get("state")
        city_exists = frappe.get_all('Samaaja Cities',filters={'city_name':user_data.get("district")})
        if city_exists:
            user_doc.city_name =user_data.get("district")
        else:
            new_city_doc = frappe.get_doc({'doctype':'Samaaja Cities'})
            new_city_doc.city_name=user_data.get("district")
            new_city_doc.insert()
            user_doc.city_name =user_data.get("district")

        user_doc.new_password = mobile
        user_doc.insert(ignore_permissions=True)
        data = 'https://solveninja.org/user-profile/'+user_doc.username
    except Exception as e:
        logger.error(f'Error occured while registering user ith mobile - {mobile}')
        logger.error(e, exc_info=True)
        message=str(e)
        status_code=500
        error=True
    logger.info('ENDS - adding a new user ------------')
    return custom_response(message,data,status_code,error)

@frappe.whitelist(allow_guest=True)
def fetch_profile():
    logger.info('STARTS - fetch profile ------------')
    message='success'
    data=''
    status_code=200
    error=False
    try:
       
        user_data = json.loads(frappe.request.data)
        mobile_no=user_data.get("mobile")
        user_profile_link='https://solveninja.org/user-profile/'

        if mobile_no:
            user_doc = frappe.db.get_all('User', filters={'mobile_no':mobile_no },fields=['username'])
            if len(user_doc) > 0 :
                user_profile_link = user_profile_link + user_doc[0].username
                data=user_profile_link
            else:
                message='User not found with mobile no '+mobile_no
        else:
            message='Mobile no is mandatory'
            status_code=400
    except Exception as e:
        logger.error(e, exc_info=True)
        message=str(e)
        status_code=500
        error=True
    logger.info('ENDS - fetch profile ------------')
    return custom_response(message,data,status_code,error)



@frappe.whitelist(allow_guest=True)
def reset_password():
    logger.info('STARTS - reset password ------------')
    message='password changed successfully'
    data=1
    status_code=200
    error=False
    try:
        user_data = json.loads(frappe.request.data)
        mobile_no=user_data.get("mobile")
        password=user_data.get("password")
        if mobile_no and password:
            user_db_docs = frappe.db.get_all('User', filters={'mobile_no':mobile_no },fields=['name'])
            if len(user_db_docs) > 0 :
                user_doc = frappe.get_doc('User',user_db_docs[0])
                user_doc.new_password=password
                user_doc.save(ignore_permissions=True)
                frappe.db.commit()

            else:
                message='User not found with mobile no '+mobile_no
                status_code=404
        else:
            message='Mobile no and password are mandatory'
            status_code=400
    except Exception as e:
        logger.error(e, exc_info=True)
        message=str(e)
        status_code=200
        error=True
        data=-1
    logger.info('ENDS - reset password ------------')
    return custom_response(message,data,status_code,error)


""" 
Author - Ankit Saxena
Date - Oct, 2022
Purpose - The below function will be called when an Event is create by a user. The purpose of this function is to create/update the user profile that includes - skill, skill level, persona, and some stats
Tech debt - as of now (15th oct, 2022), this is a single big function. Need to break it into different functions that do specifc job
"""


def update_user_profile_info(doc, _):
    logger.info('STARTS - updating user info and profile ------------')
    user_name = doc.user  # Get the username from the new event that is being created
    try:
        if user_name is not None:  # If username is present then go ahead else don't
            logger.info(
                f"Updating the profile and stats of a user - {user_name}")

            # Get the event type from the the event that is being created. Event type is the action in reap benefit's case
            event_type = doc.type

            # local variable to capture the number of events user has done for the specifc event_type
            event_type_count = 0

            # STEP 1  - Update the count of event type for this user in User Event Stats doc type
            user_event_stats_docs = frappe.db.get_all('User Event Stats', filters={'user': user_name, 'event_type': event_type},
                                                      fields=['count', 'name'])  # Check if a count exists for this user and for this event_type
            if (len(user_event_stats_docs) == 0):  # If not then insert a new count with 1
                logger.debug(
                    f'Event stats document document doesnt exists for user - {user_name} for event type - {event_type}, creating one')
                user_event_stats_doc = frappe.new_doc('User Event Stats')
                user_event_stats_doc.user = user_name
                user_event_stats_doc.event_type = event_type
                user_event_stats_doc.count = 1
                event_type_count = 1
                user_event_stats_doc.insert()
            else:  # else increment the count for existing stats document
                logger.debug(
                    f'Event stats document document exists for user - {user_name} for event type - {event_type}, updating count')
                user_event_stats_doc = frappe.get_doc(
                    'User Event Stats', user_event_stats_docs[0].name)
                user_event_stats_doc.count = int(user_event_stats_doc.count)+1
                event_type_count = user_event_stats_doc.count
                user_event_stats_doc.save()

            # STEP 2 - Activate the new skills ( and skill level ) for this user. Each event type is mapped to more than 1 skills. Therefore those skills need to be activated for this user
            event_skill_mappings = frappe.db.get_all('Event Type Skill Mapping', filters={'event_type': event_type},
                                                     fields=['skill_name'])  # Basis the event type lookup all mapped skills

            # Look on all the mapped skills and activate them for this user
            for event_skill_mapping in event_skill_mappings:
                if event_skill_mapping is not None:
                    # pull the name of the skill that needs to be activated
                    skill_name_to_be_activated = event_skill_mapping.skill_name
                    new_skill_level = ''  # local variable to hold
                    new_skill_level_number = 0

                    user_existing_skills = frappe.db.get_all('User Activated Skills', filters={
                        'user': user_name, 'skill_name': skill_name_to_be_activated}, fields=['name'])  # Fetch all existing skills that are already active for this user

                    skill_level_docs = frappe.db.get_list('Skill Level', filters=[
                        ['skill_name', '=', skill_name_to_be_activated],
                        ['lower_val', '<=', event_type_count],
                        ['upper_val', '>=', event_type_count],
                    ], fields=['skill_level_name', 'name', 'skill_level_number'])  # Fetch the skill level information basis the skill that needs to be activated for this useer

                    if (len(skill_level_docs) != 0):
                        new_skill_level = skill_level_docs[0].name
                        new_skill_level_number = skill_level_docs[0].skill_level_number
                    else:

                        # If no skill level was found then there could be a boundary condition where number of actions taken is outside the range of the highest level as well. In that case assign the highest level
                        skill_level_docs = frappe.db.get_list('Skill Level', filters=[
                            ['skill_name', '=', skill_name_to_be_activated],
                        ], fields=['skill_level_name', 'name', 'skill_level_number'], order_by='upper_val desc')  # Pick the highest level

                        if (len(skill_level_docs) != 0):
                            new_skill_level = skill_level_docs[0].name
                            new_skill_level_number = skill_level_docs[0].skill_level_number

                    # Check if the skill that needs to be activated is already active ? If no inser this (activate this new skill)
                    if (len(user_existing_skills) == 0):
                        logger.debug(
                            f'Inserting a new skill {skill_name_to_be_activated} for user {user_name} ')
                        user = frappe.new_doc('User Activated Skills')
                        user.user = user_name
                        user.skill_name = skill_name_to_be_activated
                        if (new_skill_level != ''):
                            user.skill_level = new_skill_level
                        user.insert()
                    else:  # Since this user already has skill activated then see if the activated skill level needs to be updated or not
                        if (new_skill_level != ''):  # Ensure the new skill level is not blank
                            user_activated_skill = frappe.get_doc(
                                'User Activated Skills', user_existing_skills[0].name)  # Fetch the skill document
                            # Check if the skill level is blank is blank, if yes then insert this new skill level
                            if (user_activated_skill.skill_level is None):
                                logger.debug(
                                    f'Updating existing skill document of skill -  {skill_name_to_be_activated} for user {user_name} with new skill level of - {new_skill_level}')
                                user_activated_skill.skill_level = new_skill_level
                                user_activated_skill.save()
                            else:  # since the skill already has a skill level, lets check if the new skill level is higher than the existing one, if yes then update it
                                skill_doc = frappe.get_doc(
                                    'Skill Level', user_activated_skill.skill_level)
                                if (skill_doc.skill_level_number < new_skill_level_number):
                                    logger.debug(
                                        f'Updating existing skill document of skill -  {skill_name_to_be_activated} for user {user_name} with new skill level of - {new_skill_level}')
                                    user_activated_skill.skill_level = new_skill_level
                                    user_activated_skill.save()

            # STEP 3 - # Update user profile

            # Determine the person first
            user_persona = None
            user_event_type_count_docs = frappe.db.get_list('User Event Stats', filters=[
                ['user', '=', user_name]
            ], fields=['event_type', 'count'], order_by='count desc')  # get the count of event types for this user and order by event type so that the event type with highest count is obtained
            if (len(user_event_type_count_docs) != 0):
                # get the event type with highest event count
                dominant_event_type = user_event_type_count_docs[0].event_type
                persona_docs = frappe.db.get_all('Event Type Persona Mapping', filters={
                    'event_type': dominant_event_type}, fields=['persona_name'])  # basis the dominant event type , fetch the person from event type persona mapping
                if (len(persona_docs) != 0):
                    # save the persona to a local variable
                    user_persona = persona_docs[0].persona_name

            # Update user profile
            user_profile_docs = frappe.db.get_all('SN User Profile', filters={'user': user_name},
                                                  fields=['name'])  # fetch the user profile
            # local variable to store the timezone of user THIS IS HARDCODED WITH AN ASSUMPTION THAT USERS ARE ONLY FROM INDIA REGION !!
            asia = pytz.timezone("Asia/Kolkata")
            if (len(user_profile_docs) == 0):
                # Insert a new user profile document since profile doesn't exist
                logger.debug(
                    f'Inserting a new profile document for user {user_name} with persona as {user_persona}')
                user_profile = frappe.new_doc('SN User Profile')
                user_profile.user = user_name
                user_profile.total_actions = 1
                user_profile.hours_invested = doc.time_invested
                user_profile.last_action_date = date.today()
                user_profile.last_action_date_time = datetime.now(asia)
                if (user_persona is not None):
                    user_profile.persona = user_persona
                user_profile.insert()
            else:
                # since the profile document exists, update it
                user_profile = frappe.get_doc(
                    'SN User Profile', user_profile_docs[0].name)
                logger.debug(
                    f'Updating existing profile document for user {user_name} with persona as {user_persona}')
                user_profile.total_actions = user_profile.total_actions + 1
                if (doc.time_invested is not None):
                    user_profile.hours_invested = user_profile.hours_invested + doc.time_invested
                user_profile.last_action_date = date.today()
                user_profile.last_action_date_time = datetime.now(asia)
                if (user_persona is not None):
                    user_profile.persona = user_persona
                user_profile.save()
        else:
            logger.info("User not present in the event !!!!")

    except Exception as e:
        logger.info(e)
    logger.info('ENDS - updating user info and profile ------------')


def has_permission(doc, user=None, permission_type=None):
    logger.info("Checking permission")
    roles = frappe.get_roles(frappe.session.user)
    logger.info(f"getting roles {roles}")
    if "System Manager" in roles:
        return True
    if doc.user == frappe.session.user:
        logger.info("returning true")
        return True
    return False


def update_organization_id_case(doc, _):
    logger.info(
                f"Chaging the case for org id - {doc.org_id}")
    doc.org_id = doc.org_id.upper()
