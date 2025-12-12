# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EventSourceMetadata(Document):
	def after_insert(self):
		"""
		Hook that runs after Event Source Metadata is created.
		Checks for Solve Event Participation and Program Participation records and populates relevant fields.
		"""
		self.populate_solve_event_participation_data()
		self.populate_program_participation_data()
		self.save()
		# Fallback: if no source determined, mark as Chatbot Nudge
		if not self.action_source:
			self.action_source = "Chatbot Nudge"
			self.flags.ignore_permissions = True
			self.save()
	
	def populate_solve_event_participation_data(self):
		"""
		Checks for Solve Event Participation records for the same user as the Events
		and populates the Events Metadata with relevant data if found.
		Only considers participation records created within 30 days.
		"""
		try:
			# Don't proceed if action_source is already set
			if self.action_source:
				return
			
			if not self.event_id:
				return
			
			# Get the Events document to find the user
			events_doc = frappe.get_doc("Events", self.event_id)
			if not events_doc.user:
				return
			
			# Calculate date 30 days ago
			thirty_days_ago = frappe.utils.add_days(frappe.utils.today(), -30)
			
			# Check for Solve Event Participation records for the same user
			# where creation date is within the last 30 days
			solve_event_participation = frappe.db.get_all(
				"Solve Event Participation",
				filters={
					"user": events_doc.user,
					"creation": [">=", thirty_days_ago]
				},
				fields=["name"],
				order_by="creation desc",
				limit=1
			)
			
			if solve_event_participation:
				participation = solve_event_participation[0]
				
				# Update Events Metadata with Solve Event Participation data
				self.action_source = "Solve Event Participation"
				self.source_link = participation.name
		
		except Exception as e:
			frappe.log_error(f"Error populating Solve Event Participation data for Events Metadata {self.name}: {str(e)}")
	
	def populate_program_participation_data(self):
		"""
		Checks for Program Participation records for the same user as the Events
		and populates the Events Metadata with relevant data if found.
		Only considers participation records created within 30 days.
		"""
		try:
			# Don't proceed if action_source is already set
			if self.action_source:
				return
			
			if not self.event_id:
				return
			
			# Get the Events document to find the user
			events_doc = frappe.get_doc("Events", self.event_id)
			if not events_doc.user:
				return
			
			# Calculate date 30 days ago
			thirty_days_ago = frappe.utils.add_days(frappe.utils.today(), -30)
			
			# Check for Program Participation records for the same user
			# where creation date is within the last 30 days
			program_participant = frappe.db.get_all(
				"Program Participation",
				filters={
					"user": events_doc.user,
					"creation": [">=", thirty_days_ago]
				},
				fields=["name"],
				order_by="creation desc",
				limit=1
			)
			
			if program_participant:
				participant = program_participant[0]
				
				# Update Events Metadata with Program Participation data
				self.action_source = "Program Participation"
				self.source_link = participant.name
		
		except Exception as e:
			frappe.log_error(f"Error populating Program Participation data for Events Metadata {self.name}: {str(e)}")

