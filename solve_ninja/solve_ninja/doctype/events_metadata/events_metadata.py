# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EventsMetadata(Document):
	def after_insert(self):
		"""
		Hook that runs after Events Metadata is created.
		Checks for Solve Event Participation and Program Participant records and populates relevant fields.
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
		Gets field values from the linked Solve Event document.
		Only considers participation records where solve_event_date is within 30 days.
		"""
		try:
			# Don't proceed if action_source is already set
			if self.action_source:
				return
			
			if not self.events:
				return
			
			# Get the Events document to find the user
			events_doc = frappe.get_doc("Events", self.events)
			if not events_doc.user:
				return
			
			# Calculate date 30 days ago
			thirty_days_ago = frappe.utils.add_days(frappe.utils.today(), -30)
			
			# Check for Solve Event Participation records for the same user
			# where solve_event_date is within the last 30 days
			solve_event_participation = frappe.db.get_all(
				"Solve Event Participation",
				filters={
					"user": events_doc.user,
					"creation": [">=", thirty_days_ago]
				},
				fields=["name", "solve_event"],
				order_by="creation desc",
				limit=1
			)
			
			if solve_event_participation:
				participation = solve_event_participation[0]
				
				# Get Solve Event document to fetch the required fields
				solve_event_doc = frappe.get_doc("Solve Event", participation.solve_event)
				
				# Update Events Metadata with Solve Event Participation data
				self.action_source = "Solve Event Participation"
				self.source = participation.name
				self.solve_event_participation = participation.name
				
				# Get fields from Solve Event document
				self.solve_event_date = solve_event_doc.start_date_time
				self.sub_type = solve_event_doc.sub_type
				self.mode = solve_event_doc.mode
				self.solve_event = solve_event_doc.name
				self.city = solve_event_doc.city
		
		except Exception as e:
			frappe.log_error(f"Error populating Solve Event Participation data for Events Metadata {self.name}: {str(e)}")
	
	def populate_program_participation_data(self):
		"""
		Checks for Program Participant records for the same user as the Events
		and populates the Events Metadata with relevant data if found.
		Only considers participation records created within 30 days.
		"""
		try:
			# Don't proceed if action_source is already set
			if self.action_source:
				return
			
			if not self.events:
				return
			
			# Get the Events document to find the user
			events_doc = frappe.get_doc("Events", self.events)
			if not events_doc.user:
				return
			
			# Calculate date 30 days ago
			thirty_days_ago = frappe.utils.add_days(frappe.utils.today(), -30)
			
			# Check for Program Participant records for the same user
			# where creation date is within the last 30 days
			program_participant = frappe.db.get_all(
				"Program Participant",
				filters={
					"user": events_doc.user,
					"creation": [">=", thirty_days_ago]
				},
				fields=["name", "program", "specific_program"],
				order_by="creation desc",
				limit=1
			)
			
			if program_participant:
				participant = program_participant[0]
				
				# Get Program document to fetch city and mode
				program_doc = frappe.get_doc("Program", participant.program)
				
				# Update Events Metadata with Program Participant data
				self.action_source = "Program Participant"
				self.source = participant.name
				self.program_participant = participant.name
				self.program = participant.program
				
				# Get fields from Program document
				self.city = program_doc.city
				self.mode = program_doc.mode
				self.program_date = program_doc.start_date
				# Save the updated document
				self.flags.ignore_permissions = True
				
		
		except Exception as e:
			frappe.log_error(f"Error populating Program Participant data for Events Metadata {self.name}: {str(e)}")
