# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class GlificFlow(Document):
	def validate(self):
		self.validate_flow_id()
		# self.validate_flow_exists()
	
	def validate_flow_id(self):
		"""
		Validate the flow ID.
		"""
		if not self.glific_flow_id:
			frappe.throw("Flow ID is required")
		
		try:
			frappe.utils.cint(self.glific_flow_id)
		except:
			frappe.throw("Flow ID must be an integer")
	
	def validate_flow_exists(self):
		"""
		Check if this flow exists in Glific.
		Returns True if exists, False otherwise.
		"""
		if self.is_active:
			glific_settings = frappe.get_doc("Glific Settings")
			response = glific_settings.get_flow(self.glific_flow_id)
			if response and "data" in response:
				flow_data = response.get("data", {}).get("flow", {}).get("flow")
				return flow_data is not None and flow_data.get("id")
			return False
		

	def add_keyword(self, keyword):
		"""Add a keyword to this flow in Glific"""
		glific_settings = frappe.get_doc("Glific Settings")
		return glific_settings.update_flow(
			flow_id=frappe.utils.cint(self.glific_flow_id),
			keywords=[keyword]
		)
	
	def delete_keyword(self, keyword):
		"""Remove a keyword from this flow in Glific"""
		glific_settings = frappe.get_doc("Glific Settings")
		return glific_settings.update_flow(
			flow_id=self.glific_flow_id,
			remove_keywords=[keyword]
		)
	
	def validate_flow_exists(self):
		"""
		Check if this flow exists in Glific.
		Returns True if exists, False otherwise.
		"""
		try:
			glific_settings = frappe.get_doc("Glific Settings")
			response = glific_settings.get_flow(self.glific_flow_id)
			
			if response and "data" in response:
				flow_data = response.get("data", {}).get("flow", {}).get("flow")
				return flow_data is not None and flow_data.get("id")
			return False
		except Exception as e:
			frappe.log_error(f"Error validating flow: {str(e)}", "Flow Validation Error")
			return False
	
	def replace_keywords(self, new_keywords):
		"""
		Replace all existing keywords with new keywords.
		Args:
			new_keywords (list or str): New keywords to set
		Returns:
			dict: API response
		"""
		if not isinstance(new_keywords, list):
			new_keywords = [new_keywords]
		
		glific_settings = frappe.get_doc("Glific Settings")
		
		# First get existing keywords
		existing_flow = glific_settings.get_flow(self.glific_flow_id)
		existing_keywords = []
		
		if existing_flow and "data" in existing_flow:
			flow_data = existing_flow.get("data", {}).get("flow", {}).get("flow")
			if flow_data:
				existing_keywords = flow_data.get("keywords") or []
		
		# Remove all existing and add new ones
		return glific_settings.update_flow(
			flow_id=self.glific_flow_id,
			remove_keywords=existing_keywords,
			keywords=new_keywords
		)
	
	def get_flow_details(self):
		"""
		Fetch flow details from Glific.
		Returns:
			dict: Flow details including id, name, and keywords
		"""
		glific_settings = frappe.get_doc("Glific Settings")
		response = glific_settings.get_flow(self.glific_flow_id)
		
		if response and "data" in response:
			flow_data = response.get("data", {}).get("flow", {}).get("flow")
			if flow_data:
				return {
					"success": True,
					"id": flow_data.get("id"),
					"name": flow_data.get("name"),
					"keywords": flow_data.get("keywords", [])
				}
		
		return {
			"success": False,
			"error": "Flow not found or invalid response",
			"response": response
		}
