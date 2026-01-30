# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_url_to_form
from solve_ninja.api.user import find_or_create_user_by_mobile
from solve_ninja.api.user import validate_and_normalize_mobile
from frappe.model.workflow import apply_workflow


class MentorshipRequest(Document):
	def validate(self):
		self.update_mentor_details()
		self.update_mentee_details()
		# self.send_feedback_to_mentor()
		# self.send_feedback_to_mentee()

	def update_mentee_details(self):
		"""
		Update the mentee details based on the mentee user.
		"""
		if self.phone and not self.mentee_user:
			user_doc = find_or_create_user_by_mobile(self.phone, self.mentee or self.phone)
			self.mentee_user = user_doc.get("user")

	def update_mentor_details(self):
		"""
		Update the mentor details based on the mentor expertise.
		"""
		if self.assigned_mentor:
			self.mentor_name = frappe.get_value("User", self.assigned_mentor, "full_name")
	
	# def send_feedback_to_mentor(self):

	def on_update(self):
		"""
		Send notification to mentor when assigned_mentor field changes
		Log workflow state changes as comments
		"""
		# Check if assigned_mentor has changed
		doc_before_save = self.get_doc_before_save()
		if doc_before_save:
			old_mentor = doc_before_save.get("assigned_mentor")
			new_mentor = self.get("assigned_mentor")
			
			# Only send notification if mentor was assigned (changed from None/empty to a value)
			# or if mentor was changed to a different mentor
			if new_mentor and new_mentor != old_mentor:
				try:
					self.send_mentorship_assignment_notification()
				except Exception as e:
					# Log error but don't prevent document save
					frappe.log_error(message=f"Error sending mentorship assignment notification: {str(e)}", title="Mentorship Assignment Notification Error")
			
			# Log workflow state changes
			old_state = doc_before_save.get("workflow_state")
			new_state = self.get("workflow_state")
			
			if old_state != new_state:
				# State has changed - log it as a comment
				if new_state:
					comment_text = f"Workflow state changed: {old_state or 'None'} → {new_state}"
				else:
					comment_text = f"Workflow state changed: {old_state} → None"
				
				try:
					self.add_comment("Comment", comment_text)
				except Exception as e:
					# Log error but don't prevent document save
					frappe.log_error(message=f"Error adding workflow state comment: {str(e)}", title="Workflow State Comment Error")
				
				# Send HSM notification if state changed to "Invalid Request"
				if new_state and new_state == "Invalid Request":
					try:
						self.send_invalid_request_notification_to_mentee()
					except Exception as e:
						# Log error but don't prevent document save
						frappe.log_error(message=f"Error sending invalid request notification to mentee: {str(e)}", title="Invalid Request Notification Error")
				
				# Send HSM notification to both mentor and mentee if state changed to "Mentorship Completed" or "Mentee Dropped-Out"
				if new_state and new_state in ["Mentorship Completed", "Mentee Dropped-Out"]:
					try:
						self.send_completion_notification_to_both()
					except Exception as e:
						# Log error but don't prevent document save
						frappe.log_error(message=f"Error sending completion notification: {str(e)}", title="Completion Notification Error")

		self.auto_assign_mentor()
	
	def send_mentorship_assignment_notification(self):
		"""
		Send WhatsApp notification to mentor when assigned to a mentorship request
		Follows the same pattern as send_hsm_otp for wa_id handling
		"""
		# Get Solve Ninja Settings
		solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
		
		# Check if Glific is enabled and mentor request template ID is configured
		if solve_ninja_settings.channel != "Glific" or not solve_ninja_settings.mentor_request_template_id:
			frappe.log_error("Glific not enabled or mentor request template ID not configured")
			self.add_comment("Comment", "Mentorship assignment notification failed: Glific not enabled or template ID not configured")
			return False
		
		assigned_mentor = self.get("assigned_mentor")
		if not assigned_mentor:
			frappe.log_error("No assigned mentor found in mentorship request")
			self.add_comment("Comment", "Mentorship assignment notification failed: No assigned mentor found")
			return False
		
		# Get Glific Settings
		glific_settings = frappe.get_doc("Glific Settings")
		
		# Get ninja profile - name matches assigned_mentor value
		if not frappe.db.exists("Ninja Profile", assigned_mentor):
			frappe.log_error(f"Ninja Profile not found for assigned_mentor: {assigned_mentor}")
			self.add_comment("Comment", f"Mentorship assignment notification failed: Ninja Profile not found for mentor {assigned_mentor}")
			return False
		
		ninja_profile = frappe.get_doc("Ninja Profile", assigned_mentor, for_update=False)
		
		# Get contact ID - same pattern as send_hsm_otp
		contact_id = None
		
		if not ninja_profile.wa_id:
			# Get User Metadata to get User, then get mobile number
			if not frappe.db.exists("User Metadata", assigned_mentor):
				frappe.log_error(f"User Metadata not found for assigned_mentor: {assigned_mentor}")
				self.add_comment("Comment", f"Mentorship assignment notification failed: User Metadata not found for mentor {assigned_mentor}")
				return False
			
			user_metadata = frappe.get_doc("User Metadata", assigned_mentor)
			user_name = user_metadata.user
			
			# Get User's mobile number
			user = frappe.get_doc("User", user_name)
			if not user.mobile_no:
				frappe.log_error(f"User {user_name} does not have mobile number")
				self.add_comment("Comment", f"Mentorship assignment notification failed: User {user_name} does not have mobile number")
				return False
			
			# Get contact by phone if wa_id not stored
			mobile_no = validate_and_normalize_mobile(user.mobile_no)
			response = glific_settings.get_contact_by_phone(mobile_no)
			contact_id = (
				response
				.get('data', {})
				.get('contactByPhone', {})
				.get('contact', {})
				.get('id')
			)
			if contact_id:
				# Store wa_id in ninja profile for future use
				ninja_profile.db_set("wa_id", contact_id, commit=True)
				ninja_profile.reload()
		else:
			# Use existing wa_id
			contact_id = ninja_profile.wa_id
		
		if not contact_id:
			frappe.log_error(f"Failed to get Glific contact for mentor {assigned_mentor}")
			self.add_comment("Comment", f"Mentorship assignment notification failed: Failed to get Glific contact for mentor {assigned_mentor}")
			return False
		
		# Prepare template parameters with mentorship request details
		# Template structure:
		# {{1}} mentee
		# {{2}} phone
		# {{3}} discovered_problem
		# {{4}} why_personal
		# {{6}} url to mentorship_request
		# Build URL with public view token
		if self.public_view_token:
			base_url = frappe.utils.get_url()
			mentorship_url = f"{base_url}/mentorship-request?token={self.public_view_token}"
		else:
			# Fallback to regular form URL if token not available
			mentorship_url = get_url_to_form("Mentorship Request", self.name)
		
		parameters = [
			self.mentee or "N/A",  # {{1}} Mentee name
			self.phone or "N/A",  # {{2}} Phone
			self.discovered_problem or "N/A",  # {{3}} Discovered problem
			self.why_personal or "N/A",  # {{4}} Why personal
			mentorship_url  # {{6}} URL to mentorship request
		]
		
		# Send HSM message using the existing method
		response = glific_settings.send_hsm_message(contact_id, solve_ninja_settings.mentor_request_template_id, parameters)
		
		# Check if message was sent successfully
		if response and response.get("data") and response["data"].get("sendHsmMessage"):
			message_data = response["data"]["sendHsmMessage"]
			if message_data.get("message") and not message_data.get("errors"):
				self.add_comment("Comment", f"Mentorship assignment notification sent successfully to mentor {self.mentor_name}")
				
			else:
				error_details = str(message_data.get('errors', 'Unknown error'))
				frappe.log_error(f"HSM send failed for mentorship assignment", message_data.get('errors'))
				self.add_comment("Comment", f"Mentorship assignment notification failed: HSM send error - {error_details}")
				
		else:
			# Handle specific error cases
			if response and response.get("errors"):
				error_messages = [error.get("message", "Unknown error") for error in response["errors"]]
				error_text = "; ".join(error_messages)
				frappe.log_error(f"HSM send failed for mentorship assignment to {self.mentor_name}: {error_text}")
				self.add_comment("Comment", f"Mentorship assignment notification failed: {error_text}")
			else:
				frappe.log_error(f"Invalid HSM response for mentorship assignment", response)
				self.add_comment("Comment", "Mentorship assignment notification failed: Invalid HSM response")
		
		# Send notification to mentee
		# Check if mentee phone is available
		if not self.phone:
			frappe.log_error("No phone number found for mentee")
			self.add_comment("Comment", "Mentorship assignment notification to mentee skipped: No phone number found")
			return False
		
		# Get mentee contact ID - same pattern as mentor
		mentee_contact_id = None
		
		# First, try to use mentee_whatsapp_id if available
		if self.mentee_whatsapp_id:
			mentee_contact_id = self.mentee_whatsapp_id
		else:
			# Get contact by phone if wa_id not stored
			mobile_no = validate_and_normalize_mobile(self.phone)
			response = glific_settings.get_contact_by_phone(mobile_no)
			mentee_contact_id = (
				response
				.get('data', {})
				.get('contactByPhone', {})
				.get('contact', {})
				.get('id')
			)
			
			# If we got contact_id, store it in mentee_whatsapp_id for future use
			if mentee_contact_id:
				self.db_set("mentee_whatsapp_id", mentee_contact_id, commit=False)
		
		if not mentee_contact_id:
			frappe.log_error(f"Failed to get Glific contact for mentee {self.mentee} with phone {self.phone}")
			self.add_comment("Comment", f"Mentorship assignment notification to mentee failed: Failed to get Glific contact")
			return False
		
		# Send HSM message to mentee
		response = glific_settings.send_hsm_message(mentee_contact_id, solve_ninja_settings.mentor_assignment_notification_template, [])
		# Check if message was sent successfully
		if response and response.get("data") and response["data"].get("sendHsmMessage"):
			message_data = response["data"]["sendHsmMessage"]
			if message_data.get("message") and not message_data.get("errors"):
				self.add_comment("Comment", f"Mentorship assignment notification to the mentee sent successfully - {self.mentee}")
				return True
			else:
				error_details = str(message_data.get('errors', 'Unknown error'))
				frappe.log_error(f"HSM send failed for mentorship assignment to mentee - {self.mentee}", message_data.get('errors'))
				self.add_comment("Comment", f"Mentorship assignment notification to mentee failed: HSM send error - {error_details}")
				return False
		else:
			# Handle specific error cases
			if response and response.get("errors"):
				error_messages = [error.get("message", "Unknown error") for error in response["errors"]]
				error_text = "; ".join(error_messages)
				frappe.log_error(f"HSM send failed for mentorship assignment to mentee - {self.mentee}: {error_text}")
				self.add_comment("Comment", f"Mentorship assignment notification to mentee failed: {error_text}")
			else:
				frappe.log_error(f"Invalid HSM response for mentorship assignment to mentee", response)
				self.add_comment("Comment", "Mentorship assignment notification to mentee failed: Invalid HSM response")
			return False
	
	def send_invalid_request_notification_to_mentee(self):
		"""
		Send WhatsApp notification to mentee when mentorship request status is changed to Invalid Request
		"""
		# Get Solve Ninja Settings
		solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
		
		# Check if Glific is enabled and template ID is configured
		# Using mentor_assignment_notification_template for now - you may want to add a specific field like mentee_invalid_request_template
		if solve_ninja_settings.channel != "Glific" or not solve_ninja_settings.mentor_assignment_notification_template:
			frappe.log_error("Glific not enabled or notification template ID not configured")
			self.add_comment("Comment", "Invalid request notification failed: Glific not enabled or template ID not configured")
			return False
		
		# Check if mentee phone is available
		if not self.phone:
			frappe.log_error("No phone number found for mentee")
			self.add_comment("Comment", "Invalid request notification failed: No phone number found for mentee")
			return False
		
		# Get Glific Settings
		glific_settings = frappe.get_doc("Glific Settings")
		
		# Get mentee contact ID
		contact_id = None
		
		# First, try to use mentee_whatsapp_id if available
		if self.mentee_whatsapp_id:
			contact_id = self.mentee_whatsapp_id
		else:
			# Get contact by phone if wa_id not stored
			mobile_no = validate_and_normalize_mobile(self.phone)
			response = glific_settings.get_contact_by_phone(mobile_no)
			contact_id = (
				response
				.get('data', {})
				.get('contactByPhone', {})
				.get('contact', {})
				.get('id')
			)
			
			# If we got contact_id, store it in mentee_whatsapp_id for future use
			if contact_id:
				self.db_set("mentee_whatsapp_id", contact_id, commit=False)
		
		if not contact_id:
			frappe.log_error(f"Failed to get Glific contact for mentee {self.mentee} with phone {self.phone}")
			self.add_comment("Comment", f"Invalid request notification failed: Failed to get Glific contact for mentee")
			return False
		
		# Send HSM message - using empty parameters list as you mentioned no parameters needed
		# Note: If your template requires parameters, you'll need to add them here
		response = glific_settings.send_hsm_message(contact_id, solve_ninja_settings.invalid_request_notification_template, [])
		
		# Check if message was sent successfully
		if response and response.get("data") and response["data"].get("sendHsmMessage"):
			message_data = response["data"]["sendHsmMessage"]
			if message_data.get("message") and not message_data.get("errors"):
				self.add_comment("Comment", f"Invalid request notification sent successfully to mentee {self.mentee}")
				return True
			else:
				error_details = str(message_data.get('errors', 'Unknown error'))
				frappe.log_error(f"HSM send failed for invalid request notification to mentee - {self.mentee}", message_data.get('errors'))
				self.add_comment("Comment", f"Invalid request notification failed: HSM send error - {error_details}")
				return False
		else:
			# Handle specific error cases
			if response and response.get("errors"):
				error_messages = [error.get("message", "Unknown error") for error in response["errors"]]
				error_text = "; ".join(error_messages)
				frappe.log_error(f"HSM send failed for invalid request notification to mentee - {self.mentee}: {error_text}")
				self.add_comment("Comment", f"Invalid request notification failed: {error_text}")
			else:
				frappe.log_error(f"Invalid HSM response for invalid request notification to mentee", response)
				self.add_comment("Comment", "Invalid request notification failed: Invalid HSM response")
			return False
	
	def send_completion_notification_to_both(self):
		"""
		Send WhatsApp notification to both mentor and mentee when mentorship is completed or mentee dropped out
		Uses separate templates for mentor and mentee
		"""
		# Get Solve Ninja Settings
		solve_ninja_settings = frappe.get_single("Solve Ninja Settings")
		
		# Check if Glific is enabled
		if solve_ninja_settings.channel != "Glific":
			frappe.log_error("Glific not enabled")
			self.add_comment("Comment", "Completion notification failed: Glific not enabled")
			return False
		
		# Get workflow state to determine which templates to use
		workflow_state = self.get("workflow_state")
		
		# Determine template IDs based on state - separate for mentor and mentee
		mentor_template_id = None
		mentee_template_id = None
		send_to_mentee = True  # Flag to control whether to send notification to mentee
		
		if workflow_state == "Mentorship Completed":
			# Check for state-specific templates, with fallbacks
			mentor_template_id = (
				solve_ninja_settings.mentor_completion_template
			)
			mentee_template_id = (
				solve_ninja_settings.mentee_completion_template
			)
			send_to_mentee = True  # Send to both mentor and mentee
		elif workflow_state == "Mentee Dropped-Out":
			# Only send notification to mentor, not to mentee
			# Use specific template for mentee dropout notification
			mentor_template_id = (
				solve_ninja_settings.mentee_dropout_notification_template
			)
			send_to_mentee = False  # Do not send to mentee when they drop out
		
		if not mentor_template_id:
			frappe.log_error("Template ID not configured for mentor completion notification")
			self.add_comment("Comment", "Completion notification failed: Mentor template ID not configured")
			return False
		
		# Only check mentee_template_id if we're sending to mentee
		if send_to_mentee and not mentee_template_id:
			frappe.log_error("Template ID not configured for mentee completion notification")
			self.add_comment("Comment", "Completion notification failed: Mentee template ID not configured")
			return False
		
		# Get Glific Settings
		glific_settings = frappe.get_doc("Glific Settings")
		
		# Prepare feedback URLs (separate for mentor and mentee)
		base_url = frappe.utils.get_url()
		mentor_feedback_url = f"{base_url}/mentor-feedback/new?request_id={self.name}"
		mentee_feedback_url = f"{base_url}/mentee-feedback/new?request_id={self.name}"
		
		# Track success for both notifications
		mentor_success = False
		mentee_success = False
		
		# Send notification to mentor with mentor-specific template
		assigned_mentor = self.get("assigned_mentor")
		if assigned_mentor:
			try:
				mentor_contact_id = self._get_mentor_contact_id(assigned_mentor)
				if mentor_contact_id:
					# Prepare parameters based on workflow state
					mentor_parameters = []
					
					if workflow_state == "Mentee Dropped-Out":
						# For mentee dropped out, pass mentee name and mentor feedback URL as parameters
						mentor_parameters = [
							self.mentee or "N/A",  # {{1}} Mentee name
							mentor_feedback_url  # {{2}} Mentor feedback URL
						]
					elif workflow_state == "Mentorship Completed":
						# For mentorship completed, pass mentor feedback URL as parameter
						mentor_parameters = [mentor_feedback_url]  # {{1}} Mentor feedback URL
					
					response = glific_settings.send_hsm_message(mentor_contact_id, mentor_template_id, mentor_parameters)
					if response and response.get("data") and response["data"].get("sendHsmMessage"):
						message_data = response["data"]["sendHsmMessage"]
						if message_data.get("message") and not message_data.get("errors"):
							mentor_success = True
							self.add_comment("Comment", f"Completion notification sent successfully to mentor {self.mentor_name}")
						else:
							error_details = str(message_data.get('errors', 'Unknown error'))
							frappe.log_error(f"HSM send failed for completion notification to mentor - {self.mentor_name}", message_data.get('errors'))
							self.add_comment("Comment", f"Completion notification to mentor failed: HSM send error - {error_details}")
					else:
						frappe.log_error(f"Invalid HSM response for completion notification to mentor", response)
						self.add_comment("Comment", "Completion notification to mentor failed: Invalid HSM response")
				else:
					frappe.log_error(f"Failed to get contact ID for mentor {assigned_mentor}")
					self.add_comment("Comment", f"Completion notification to mentor failed: Could not get contact ID")
			except Exception as e:
				frappe.log_error(f"Error sending completion notification to mentor: {str(e)}", "Completion Notification Error")
				self.add_comment("Comment", f"Completion notification to mentor failed: {str(e)}")
		else:
			frappe.log_error("No assigned mentor found for completion notification")
			self.add_comment("Comment", "Completion notification to mentor skipped: No assigned mentor")
		
		# Send notification to mentee with mentee-specific template (only if send_to_mentee is True)
		if send_to_mentee:
			if self.phone:
				try:
					mentee_contact_id = self._get_mentee_contact_id()
					if mentee_contact_id:
						# Prepare parameters for mentee notification
						mentee_parameters = []
						if workflow_state == "Mentorship Completed":
							# For mentorship completed, pass mentee feedback URL as parameter
							mentee_parameters = [mentee_feedback_url]  # {{1}} Mentee feedback URL
						
						response = glific_settings.send_hsm_message(mentee_contact_id, mentee_template_id, mentee_parameters)
						if response and response.get("data") and response["data"].get("sendHsmMessage"):
							message_data = response["data"]["sendHsmMessage"]
							if message_data.get("message") and not message_data.get("errors"):
								mentee_success = True
								self.add_comment("Comment", f"Completion notification sent successfully to mentee {self.mentee}")
							else:
								error_details = str(message_data.get('errors', 'Unknown error'))
								frappe.log_error(f"HSM send failed for completion notification to mentee - {self.mentee}", message_data.get('errors'))
								self.add_comment("Comment", f"Completion notification to mentee failed: HSM send error - {error_details}")
						else:
							frappe.log_error(f"Invalid HSM response for completion notification to mentee", response)
							self.add_comment("Comment", "Completion notification to mentee failed: Invalid HSM response")
					else:
						frappe.log_error(f"Failed to get contact ID for mentee {self.mentee}")
						self.add_comment("Comment", f"Completion notification to mentee failed: Could not get contact ID")
				except Exception as e:
					frappe.log_error(f"Error sending completion notification to mentee: {str(e)}", "Completion Notification Error")
					self.add_comment("Comment", f"Completion notification to mentee failed: {str(e)}")
			else:
				frappe.log_error("No phone number found for mentee completion notification")
				self.add_comment("Comment", "Completion notification to mentee skipped: No phone number")
		else:
			# Skip mentee notification when workflow state is "Mentee Dropped-Out"
			self.add_comment("Comment", "Completion notification to mentee skipped: Mentee dropped out")
		
		# Return True if at least one notification was sent successfully
		return mentor_success or mentee_success
	
	def _get_mentor_contact_id(self, assigned_mentor):
		"""
		Helper method to get mentor contact ID
		Returns contact_id or None
		"""
		if not frappe.db.exists("Ninja Profile", assigned_mentor):
			return None
		
		ninja_profile = frappe.get_doc("Ninja Profile", assigned_mentor, for_update=False)
		
		# Use existing wa_id if available
		if ninja_profile.wa_id:
			return ninja_profile.wa_id
		
		# Get contact by phone if wa_id not stored
		if not frappe.db.exists("User Metadata", assigned_mentor):
			return None
		
		user_metadata = frappe.get_doc("User Metadata", assigned_mentor)
		user_name = user_metadata.user
		
		user = frappe.get_doc("User", user_name)
		if not user.mobile_no:
			return None
		
		glific_settings = frappe.get_doc("Glific Settings")
		mobile_no = validate_and_normalize_mobile(user.mobile_no)
		response = glific_settings.get_contact_by_phone(mobile_no)
		contact_id = (
			response
			.get('data', {})
			.get('contactByPhone', {})
			.get('contact', {})
			.get('id')
		)
		
		if contact_id:
			# Store wa_id in ninja profile for future use
			ninja_profile.db_set("wa_id", contact_id, commit=True)
			ninja_profile.reload()
		
		return contact_id
	
	def _get_mentee_contact_id(self):
		"""
		Helper method to get mentee contact ID
		Returns contact_id or None
		"""
		# First, try to use mentee_whatsapp_id if available
		if self.mentee_whatsapp_id:
			return self.mentee_whatsapp_id
		
		# Get contact by phone if wa_id not stored
		glific_settings = frappe.get_doc("Glific Settings")
		mobile_no = validate_and_normalize_mobile(self.phone)
		response = glific_settings.get_contact_by_phone(mobile_no)
		contact_id = (
			response
			.get('data', {})
			.get('contactByPhone', {})
			.get('contact', {})
			.get('id')
		)
		
		# If we got contact_id, store it in mentee_whatsapp_id for future use
		if contact_id:
			self.db_set("mentee_whatsapp_id", contact_id, commit=False)
		
		return contact_id
	
	def auto_assign_mentor(self):
		if (
			self.workflow_state == "Valid Request"
			and self.assigned_mentor
		):
			frappe.db.commit()
			apply_workflow(self, "Assign Mentor")

def get_permission_query_conditions(user):
	"""
	Get permission query conditions for Mentorship Request
	"""
	roles = frappe.get_roles(user)
	
	# Allow full access for Administrator, System Manager, and Mentorship Manager
	if any(role in roles for role in ["Administrator", "System Manager", "Mentorship Manager"]):
		return None
	
	return """(`tabMentorship Request`.assigned_mentor = '{0}')""".format(user)
	
def has_permission(doc, user):
	"""
	Check if user has permission to read Mentorship Request
	"""
	roles = frappe.get_roles(user)
	
	# Allow full access for Administrator, System Manager, and Mentorship Manager
	if any(role in roles for role in ["Administrator", "System Manager", "Mentorship Manager"]):
		return True
	
	return doc.assigned_mentor == user