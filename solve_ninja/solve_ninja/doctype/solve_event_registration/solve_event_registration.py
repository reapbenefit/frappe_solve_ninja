# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class SolveEventRegistration(Document):
	def validate(self):
		"""
		Handle user creation/linking and prevent duplicate registrations.
		"""
		# Check if user is logged in
		if frappe.session.user and frappe.session.user not in ['Guest', 'Administrator']:
			# User is logged in, use their account
			if not self.user:
				self.user = frappe.session.user
			
				# Populate user data from logged-in user
				self.populate_user_data_from_session()

		else:
			# User is not logged in, handle user creation/linking
			if not self.user and self.mobile:
				self.user = self.create_or_link_user()
		
		# Then check for duplicate registrations
		if self.user:
			self.check_duplicate_registration()

	def populate_user_data_from_session(self):
		"""
		Populate user data from the logged-in user's session.
		"""
		try:
			# Get current user data
			user_doc = frappe.get_doc("User", frappe.session.user)
			
			# Populate fields if not already set
			if not self.full_name:
				self.full_name = user_doc.full_name or user_doc.first_name
			
			if not self.mobile:
				self.mobile = user_doc.mobile_no
			
			# Get user metadata for additional info
			user_metadata = frappe.get_value("User Metadata", {"user": frappe.session.user}, 
											["city", "year_of_birth"], as_dict=True)
			
			if user_metadata:
				if not self.city and user_metadata.city:
					self.city = user_metadata.city
				
				if not self.year_of_birth and user_metadata.year_of_birth:
					self.year_of_birth = user_metadata.year_of_birth
					
		except Exception as e:
			frappe.log_error(f"Error populating user data from session: {str(e)}")
			# Don't throw error, just log it

	def create_or_link_user(self):
		"""
		Create a new user or link to existing user based on mobile number.
		Checks for existing users with both mobile formats (with and without country code).
		Returns the user ID.
		"""
		try:
			# Normalize mobile number
			mobile = self.validate_and_normalize_mobile(self.mobile)
			
			# Check if user already exists with both mobile formats
			existing_user = self.find_existing_user_by_mobile(mobile)
			
			if existing_user:
				return existing_user
			else:
				# Create new user
				user_data = self.build_user_data_from_registration()
				user_doc = self.build_user_doc(user_data, mobile)
				user_doc.append("roles", {"role": "Solve Ninja"})
				user_doc.insert(ignore_permissions=True)
				
				# Enqueue background tasks for profile and metadata updates
				frappe.enqueue(
					"solve_ninja.api.user.update_ninja_profile",
					user=user_doc.name,
					user_data=user_data,
					queue='default',
					job_name=f"Update ninja profile for {user_doc.name}",
					now=False
				)
				frappe.enqueue(
					"solve_ninja.api.user.update_user_metadata",
					user=user_doc.name,
					user_data=user_data,
					queue='default',
					job_name=f"Update user metadata for {user_doc.name}",
					now=False
				)
				
				return user_doc.name
				
		except Exception as e:
			frappe.log_error(f"Error creating/linking user", str(e))
			frappe.throw(_("Failed to create or link user. Please contact support."))

	def find_existing_user_by_mobile(self, mobile):
		"""
		Find existing user by checking both mobile formats:
		1. With country code (e.g., 919876543210)
		2. Without country code (e.g., 9876543210)
		"""
		# Check with country code first
		existing_user = frappe.db.exists("User", {"mobile_no": mobile})
		if existing_user:
			return existing_user
		
		# If mobile has country code, also check without it
		if len(mobile) == 12 and mobile.startswith("91"):
			mobile_without_code = mobile[2:]  # Remove "91" prefix
			existing_user = frappe.db.exists("User", {"mobile_no": mobile_without_code})
			if existing_user:
				return existing_user
		
		# If mobile is 10 digits, also check with country code
		elif len(mobile) == 10:
			mobile_with_code = "91" + mobile
			existing_user = frappe.db.exists("User", {"mobile_no": mobile_with_code})
			if existing_user:
				return existing_user
		
		return None

	def build_user_data_from_registration(self):
		"""
		Build user data dictionary from registration fields.
		"""
		user_data = {
			"mobile": self.mobile,
			"first_name": self.full_name or "User",
		}
		
		# Add city if provided
		if self.city:
			user_data["city"] = self.city
		
		# Add age if year of birth is provided
		if self.year_of_birth:
			from datetime import datetime
			current_year = datetime.now().year
			age = current_year - self.year_of_birth
			user_data["age"] = age
		
		return user_data

	def build_user_doc(self, user_data, mobile):
		"""
		Create a new User Doc with provided user_data and mobile.
		Based on the build_user_doc function from common.py
		"""
		user_doc = frappe.get_doc({
			'doctype': 'User',
			'mobile': mobile,
			'email': f"{mobile}@solveninja.org",
			'mobile_no': mobile,
			'first_name': user_data.get("first_name"),
			'new_password': mobile
		})
		
		# Assign city if provided
		if user_data.get("city"):
			self.assign_city_to_user(user_doc, user_data.get("city"))
		
		return user_doc

	def assign_city_to_user(self, user_doc, city_name):
		"""
		Assign city to user based on city name.
		"""
		try:
			city_exists = frappe.get_all('Samaaja Cities', filters={'city_name': city_name}, fields=['name'])
			if city_exists:
				user_doc.city = city_exists[0].name
		except Exception as e:
			frappe.log_error(f"Error assigning city {city_name} to user: {str(e)}")

	def validate_and_normalize_mobile(self, mobile):
		"""
		Validate and normalize mobile number.
		Based on the validate_and_normalize_mobile function from common.py
		"""
		if not mobile:
			frappe.throw(_("Mobile number is required."))
		
		# Remove any non-digit characters
		mobile = ''.join(filter(str.isdigit, str(mobile)))
		
		if len(mobile) not in [10, 12] or not mobile.isdigit():
			frappe.throw(_("Mobile number must be either 10 or 12 digits and numeric."))

		if len(mobile) == 10:
			mobile = "91" + mobile

		return mobile

	def check_duplicate_registration(self):
		"""
		Prevent duplicate Solve Event Registrations by the same user.
		If a duplicate is found, automatically mark this registration as Rejected
		and show a message explaining why.
		"""
		# Check for existing registration by the same user for the same event
		existing = frappe.get_all(
			"Solve Event Registration",
			filters={
				"user": self.user,
				"solve_event": self.solve_event,
				"name": ["!=", self.name],
			},
			fields=["name"],
			limit_page_length=1,
		)

		if existing:
			# Automatically reject this registration
			self.status = "Rejected"
			self.reason = "Duplicate registration: user already registered for this event."

			# Notify user in UI
			frappe.msgprint(
				title=_("Registration Rejected"),
				msg=_("You have already registered for this event. "
					  "Duplicate registrations are not allowed. "
					  "Your new registration has been marked as <b>Rejected</b>."),
				indicator="red"
			)
