import json

import frappe
from werkzeug.wrappers import Response
from datetime import date
from datetime import datetime
from frappe.utils import logger
import pytz
logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)


def update_user_profile_info(doc, _):
    logger.info("update user progil11111111e")
    user_name = doc.user  # Get the username from the new event that is being created
    ##user_name = '918408880857@solveninja.org'
    try:
        if user_name is not None:  # If username is present then go ahead else don't

            # Get the event type from the the event that is being created. Event type is the action in reap benefit's case
            event_type = doc.type
            event_type_count = 0
            # Update the count of event type for this user in User Event Stats doc type
            user_event_stats_docs = frappe.db.get_all('User Event Stats', filters={'user': user_name, 'event_type': event_type},
                                                      fields=['count', 'name'])  # Check if a count exists for this user and for this skill
            if (len(user_event_stats_docs) == 0):  # If not then insert a new count with 1
                logger.info('document doesnt exists, creating one')
                user_event_stats_doc = frappe.new_doc('User Event Stats')
                user_event_stats_doc.user = user_name
                user_event_stats_doc.event_type = event_type
                user_event_stats_doc.count = 1
                event_type_count = 1
                user_event_stats_doc.insert()
            else:  # else increment the count for existing stats document
                user_event_stats_doc = frappe.get_doc(
                    'User Event Stats', user_event_stats_docs[0].name)
                user_event_stats_doc.count = int(user_event_stats_doc.count)+1
                event_type_count = user_event_stats_doc.count
                user_event_stats_doc.save()

            event_skill_mappings = frappe.db.get_all('Event Type Skill Mapping', filters={'event_type': event_type},
                                                     fields=['skill_name'])  # Basis the event type lookup all mapped skills

            for event_skill_mapping in event_skill_mappings:  # Add all the associated skills to this user
                if event_skill_mapping is not None:
                    skill_name = event_skill_mapping.skill_name
                    new_skill_level = ''
                    new_skill_level_number = 0
                    logger.info(skill_name)
                    logger.info(event_type_count)
                    user_activated_skills = frappe.db.get_all('User Activated Skills', filters={
                        'user': user_name, 'skill_name': skill_name}, fields=['name'])

                    skill_level_docs = frappe.db.get_list('Skill Level', filters=[
                        ['skill_name', '=', skill_name],
                        ['lower_val', '<=', event_type_count],
                        ['upper_val', '>=', event_type_count],
                    ], fields=['skill_level_name', 'name', 'skill_level_number'])

                    if (len(skill_level_docs) != 0):
                        new_skill_level = skill_level_docs[0].name
                        new_skill_level_number = skill_level_docs[0].skill_level_number
                    else:
                        logger.info('No skills found')
                        # If no skill level was found then there could be a boundary condition where number of actions taken is outside the range of the highest level as well. In that case assign the highest level
                        skill_level_docs = frappe.db.get_list('Skill Level', filters=[
                            ['skill_name', '=', skill_name],
                        ], fields=['skill_level_name', 'name', 'skill_level_number'], order_by='upper_val desc')
                        if (len(skill_level_docs) != 0):
                            new_skill_level = skill_level_docs[0].name
                            new_skill_level_number = skill_level_docs[0].skill_level_number
                    # Check if this skill is already added to the user, if no then add else dont add a new.
                    if (len(user_activated_skills) == 0):
                        logger.info('insert a new skill')
                        user = frappe.new_doc('User Activated Skills')
                        user.user = user_name
                        user.skill_name = skill_name
                        if (new_skill_level != ''):
                            user.skill_level = new_skill_level
                        user.insert()
                    else:
                        if (new_skill_level != ''):
                            logger.info('trying saving existing document')
                            user_activated_skill = frappe.get_doc(
                                'User Activated Skills', user_activated_skills[0].name)
                            if (user_activated_skill.skill_level is None):
                                logger.info('saving existing document')
                                user_activated_skill.skill_level = new_skill_level
                                user_activated_skill.save()
                            else:
                                skill_doc = frappe.get_doc(
                                    'Skill Level', user_activated_skill.skill_level)
                                if (skill_doc.skill_level_number < new_skill_level_number):
                                    logger.info('saving existing document')
                                    user_activated_skill.skill_level = new_skill_level
                                    user_activated_skill.save()

            # get persona of this user
            user_persona = None
            user_event_type_count_docs = frappe.db.get_list('User Event Stats', filters=[
                ['user', '=', user_name]
            ], fields=['event_type', 'count'], order_by='count desc')
            if (len(user_event_type_count_docs) != 0):
                dominant_event_type = user_event_type_count_docs[0].event_type
                logger.info(f"dominant_event_type is {dominant_event_type}")
                persona_docs = frappe.db.get_all('Event Type Persona Mapping', filters={
                    'event_type': dominant_event_type}, fields=['persona_name'])
                if (len(persona_docs) != 0):
                    user_persona = persona_docs[0].persona_name
                logger.info(f"persona name is {user_persona}")

            # Update user profile
            user_profile_docs = frappe.db.get_all('SN User Profile', filters={'user': user_name},
                                                  fields=['name'])
            asia = pytz.timezone("Asia/Kolkata")
            if (len(user_profile_docs) == 0):
                # Insert a new user profile document
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
                user_profile = frappe.get_doc(
                    'SN User Profile', user_profile_docs[0].name)

                user_profile.total_actions = user_profile.total_actions + 1
                if (doc.time_invested is not None):
                    user_profile.hours_invested = user_profile.hours_invested + doc.time_invested
                user_profile.last_action_date = date.today()
                user_profile.last_action_date_time = datetime.now(asia)
                if (user_persona is not None):
                    user_profile.persona = user_persona

                user_profile.save()
    except Exception as e:
        logger.info(e)


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
