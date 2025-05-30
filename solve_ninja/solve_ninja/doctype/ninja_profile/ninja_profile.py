# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class NinjaProfile(Document):
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
