import json
import string
import random
import frappe
from werkzeug.wrappers import Response
from datetime import date
from datetime import datetime
from frappe.utils import logger
import pytz
logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

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