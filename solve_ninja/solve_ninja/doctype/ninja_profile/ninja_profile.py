# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from solve_ninja.utils import get_doc_by_unique_id

class NinjaProfile(Document):
	def validate(self):
		if self.acquisition_source_unique_id:
			self.acquisition_source_unique_id = self.acquisition_source_unique_id.upper()
			self.update_acquisition_source_category()

	def on_update(self):
		self.update_action_details()

	def update_action_details(self):
		"""
		Updates the Ninja Profile with the latest action details when an Event is created or modified.
		"""
		if not self.last_action and self.name and frappe.db.exists("Events", {"user": self.name}):
			# Get the latest event associated with the user
			event = frappe.get_last_doc("Events", filters={"user": self.name})

			if event:
				# Set the latest action metadata
				self.last_action = event.name
				self.last_action_date = event.creation
				self.last_action_type = event.type
				self.last_action_sub_type = event.sub_type
				self.last_action_category = event.category

				# Save with ignore_permission in case it's triggered from background or guest
				self.flags.ignore_permissions = True
				# self.save()

	def update_acquisition_source_category(self):
		"""
		Updates acquisition_source_category and acquisition_source_name based on acquisition_source_unique_id.
		Uses get_doc_by_unique_id utility to check if acquisition_source_unique_id exists in Solve Event, Social Media, or Program doctypes.
		"""
		if not self.acquisition_source_unique_id:
			return

		# Normalize acquisition_source_unique_id to uppercase for consistency
		unique_id_upper = self.acquisition_source_unique_id.upper() if self.acquisition_source_unique_id else None
		if not unique_id_upper:
			return

		# Check if acquisition_source_unique_id has changed
		doc_before_save = self.get_doc_before_save()
		if doc_before_save:
			old_unique_id = doc_before_save.get("acquisition_source_unique_id")
			old_unique_id_upper = old_unique_id.upper() if old_unique_id else None
			if old_unique_id_upper == unique_id_upper and self.acquisition_source_category and self.acquisition_source_name:
				# acquisition_source_unique_id hasn't changed and both category and name are already set, skip update
				return

		# Use utility function to find document by acquisition_source_unique_id
		doc_info = get_doc_by_unique_id(unique_id_upper)
		
		if doc_info:
			self.acquisition_source_category = doc_info.get("doctype")
			self.acquisition_source_name = doc_info.get("name")
		else:
			# Clear fields if acquisition_source_unique_id not found in any doctype
			self.acquisition_source_category = None
			self.acquisition_source_name = None
