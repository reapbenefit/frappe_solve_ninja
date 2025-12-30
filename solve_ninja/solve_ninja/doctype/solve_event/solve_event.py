# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
import io
from frappe.model.document import Document
from solve_ninja.utils import is_unique_id_duplicate

class SolveEvent(Document):
	def validate(self):
		"""Generate unique ID, update checkin_url from settings and generate QR code when URL changes"""
		doc_before_save = self.get_doc_before_save()
		
		# Check if fields that affect unique_id have changed
		should_regenerate_id = False
		if doc_before_save:
			# Check if any field that affects unique_id generation has changed
			fields_to_check = ["type", "sub_type", "city", "start_date_time"]
			for field in fields_to_check:
				if doc_before_save.get(field) != self.get(field):
					should_regenerate_id = True
					break
		
		# Generate unique_id if not already set or if relevant fields have changed
		if not self.unique_id or should_regenerate_id:
			self.generate_unique_id()
		
		# Check if unique_id has changed or if we need to update URL
		unique_id_changed = False
		
		if doc_before_save:
			old_unique_id = doc_before_save.get("unique_id")
			new_unique_id = self.get("unique_id")
			unique_id_changed = old_unique_id != new_unique_id
		else:
			# New document
			unique_id_changed = bool(self.get("unique_id"))
		
		# Update checkin_url if unique_id is set/changed
		if self.get("unique_id"):
			self.update_checkin_url()
		
		# Update flow keywords if unique_id has changed
		if unique_id_changed and self.get("unique_id"):
			self.update_flow_keyword()
		
		# Check if checkin_url has changed and generate QR code
		if doc_before_save:
			old_url = doc_before_save.get("checkin_url")
			new_url = self.get("checkin_url")
			
			# Generate QR code if URL has changed and is not empty
			if old_url != new_url and new_url or (not self.checkin_qr and self.checkin_url):
				self.generate_qr_code(new_url)
		elif self.get("checkin_url"):
			# New document with checkin_url set
			self.generate_qr_code(self.get("checkin_url"))
	
	def update_checkin_url(self):
		"""Update checkin_url from Solve Ninja Settings with unique_id"""
		try:
			# Get base URL from Solve Ninja Settings
			base_url = frappe.db.get_single_value("Solve Ninja Settings", "checkin_url")
			
			if not base_url:
				frappe.msgprint(
					"CheckIn URL not configured in Solve Ninja Settings",
					alert=True,
					indicator="orange"
				)
				return
			
			# Build URL with unique_id: {base_url}&code={unique_id}
			unique_id = self.get("unique_id")
			if unique_id:
				# Use & if base_url already has query parameters, otherwise use ?
				separator = "&" if "?" in base_url else "?"
				checkin_url = f"{base_url}{separator}text={unique_id}"
				self.checkin_url = checkin_url
			else:
				# If unique_id is empty, just use base URL
				self.checkin_url = base_url
				
		except Exception as e:
			frappe.log_error(
				f"Error updating checkin_url for Solve Event {self.name}: {str(e)}",
				"Update CheckIn URL Error"
			)
			frappe.msgprint(
				f"Failed to update checkin URL: {str(e)}",
				alert=True,
				indicator="orange"
			)
	
	def update_flow_keyword(self):
		"""Update flow keywords in Glific with unique_id when unique_id changes"""
		try:
			# Get event_checkin_flow_id from Solve Ninja Settings
			flow_id = frappe.db.get_single_value("Solve Ninja Settings", "event_checkin_flow_id")
			
			if not flow_id:
				frappe.msgprint(
					"Event Checkin Flow ID not configured in Solve Ninja Settings",
					alert=True,
					indicator="orange"
				)
				# Add comment about configuration issue
				try:
					self.add_comment("Comment", "Flow keyword update skipped: Flow ID not configured")
				except:
					pass  # Skip if document not saved yet
				return
			
			# Get GlificSettings document
			glific_settings = frappe.get_doc("Glific Settings")
			
			# Update flow with unique_id as keyword (Glific stores keywords in lowercase)
			unique_id = self.get("unique_id")
			if unique_id:
				response = glific_settings.update_flow(
					flow_id=flow_id,
					keywords=[unique_id.lower()]
				)
				
				# Check for errors in response
				if response and "data" in response:
					data = response.get("data", {})
					update_flow_data = data.get("updateFlow", {})
					errors = update_flow_data.get("errors", [])
					
					if errors:
						error_messages = [err.get("message", "") for err in errors if err.get("message")]
						if error_messages:
							error_msg = ', '.join(error_messages)
							frappe.log_error(
								f"Error updating flow keywords: {error_msg}",
								"Update Flow Keyword Error"
							)
							frappe.msgprint(
								f"Failed to update flow keywords: {error_msg}",
								alert=True,
								indicator="orange"
							)
							# Add comment about failure
							try:
								self.add_comment("Comment", f"Flow keyword update failed: {error_msg}")
							except:
								pass  # Skip if document not saved yet
					else:
						# Success - no errors in response
						try:
							self.add_comment("Comment", f"Flow keyword updated successfully: {unique_id}")
						except:
							pass  # Skip if document not saved yet
		except Exception as e:
			error_msg = str(e)
			frappe.log_error(
				f"Error updating flow keyword for Solve Event {self.name}: {error_msg}",
				"Update Flow Keyword Error"
			)
			frappe.msgprint(
				f"Failed to update flow keyword: {error_msg}",
				alert=True,
				indicator="orange"
			)
			# Add comment about exception
			try:
				self.add_comment("Comment", f"Flow keyword update failed: {error_msg}")
			except:
				pass  # Skip if document not saved yet
	
	def generate_qr_code(self, url):
		"""Generate QR code from URL and save it to checkin_qr field"""
		
		from pyqrcode import create as qrcreate
		from frappe.utils.file_manager import save_file
		
		# Get document name - autoname "hash" ensures name is available in validate()
		doc_name = self.name or frappe.generate_hash(length=10)
		
		# Generate unique file name
		file_name = f"qr_{doc_name}.png"
		
		# Generate QR code to BytesIO buffer
		qr = qrcreate(url)
		buffer = io.BytesIO()
		qr.png(buffer, scale=8, module_color=[0, 0, 0, 180], background=[0xFF, 0xFF, 0xFF])
		buffer.seek(0)
		file_content = buffer.read()
		
		# Delete old QR code file if exists
		if self.checkin_qr:
			old_file = frappe.db.get_value("File", {"file_url": self.checkin_qr}, "name")
			if old_file:
				try:
					frappe.delete_doc("File", old_file, ignore_permissions=True, force=True)
				except:
					pass  # Ignore errors when deleting old file
		
		# Save and attach file using Frappe's save_file utility
		# This will create the File document and attach it to the document
		file_doc = save_file(
			fname=file_name,
			content=file_content,
			dt=self.doctype,
			dn=doc_name,
			folder=None,
			is_private=0,
			df="checkin_qr"  # Attach to checkin_qr field
		)
		
		# Set the checkin_qr field to the file URL
		self.checkin_qr = file_doc.file_url
	
	def subtype_code(self, value):
		"""Convert subtype to code"""
		v = str(value or "").strip().lower()
		
		# 1. Check Explicit Mappings
		if v == "solver jam":
			return "SJ"
		if v == "solve con":
			return "SC"
		if v == "changemaker adda":
			return "CMA"
		
		# 2. Fallback: Manual alphanumeric strip (Internal Logic)
		letters = ""
		i = 0
		while i < len(v):
			ch = v[i]
			if ("a" <= ch <= "z"):
				letters = letters + ch
			i = i + 1
		letters = letters.upper()
		
		if len(letters) >= 3:
			return letters[:3]
		if len(letters) > 0:
			return letters
		return "XX"
	
	def city_two_letters(self, value):
		"""Extract two letters from city name"""
		# Manual alphanumeric strip (Internal Logic)
		text = str(value or "")
		letters = ""
		i = 0
		while i < len(text):
			ch = text[i]
			if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
				letters = letters + ch
			i = i + 1
		letters = letters.upper()
		
		if len(letters) >= 2:
			return letters[:2]
		if len(letters) == 1:
			return letters + "X"
		return "XX"
	
	def extract_date_parts(self, dt_value):
		"""Extract day, month, year from datetime"""
		if not dt_value:
			return None
		
		# If it is already a datetime object
		if hasattr(dt_value, "day") and hasattr(dt_value, "month") and hasattr(dt_value, "year"):
			d_str = str(dt_value.day)
			m_str = str(dt_value.month)
			y_str = str(dt_value.year)
			
			if len(d_str) == 1:
				d_str = "0" + d_str
			if len(m_str) == 1:
				m_str = "0" + m_str
				
			result = {}
			result["dd"] = d_str
			result["mm"] = m_str
			result["yyyy"] = y_str
			return result
		
		# If it is a string
		s = str(dt_value).strip()
		
		if " " in s:
			date_part = s.split(" ")[0]
		else:
			date_part = s
		date_part = date_part.replace("/", "-").replace(".", "-")
		parts = date_part.split("-")
		
		# Case 1: DD-MM-YYYY
		if len(parts) == 3 and len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
			result = {}
			result["dd"] = parts[0]
			result["mm"] = parts[1]
			result["yyyy"] = parts[2]
			return result
		
		# Case 2: YYYY-MM-DD
		if len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
			result = {}
			result["yyyy"] = parts[0]
			result["mm"] = parts[1]
			result["dd"] = parts[2]
			return result
		
		# Fallback: try frappe util
		try:
			dt = frappe.utils.get_datetime(dt_value)
			result = {}
			result["dd"] = dt.strftime("%d")
			result["mm"] = dt.strftime("%m")
			result["yyyy"] = dt.strftime("%Y")
			return result
		except Exception:
			return None
	
	def make_unique(self, base, doctype, fieldname):
		"""Ensure unique ID by appending number if needed, checking across all doctypes"""
		if not base:
			return None
		
		# Check if the exact base exists across all doctypes
		exclude_name = None if self.is_new() else self.name
		duplicate = is_unique_id_duplicate(base, exclude_doctype=doctype, exclude_name=exclude_name)
		
		if duplicate:
			# Base exists, append number suffix and check again
			i = 2
			while True:
				candidate = base + "-" + str(i)
				duplicate = is_unique_id_duplicate(candidate, exclude_doctype=doctype, exclude_name=exclude_name)
				if not duplicate:
					return candidate
				i = i + 1
		
		return base
	
	def generate_unique_id(self):
		"""Generate unique ID based on subtype, city, and start_date_time"""
		try:
			# Use type field (or sub_type if it exists)
			subtype_value = self.get("sub_type") or self.get("type")
			code = self.subtype_code(subtype_value)
			
			city_code = self.city_two_letters(self.get("city"))
			
			date_parts = self.extract_date_parts(self.get("start_date_time"))
			
			dd = None
			mm = None
			yyyy = None
			
			if date_parts:
				dd = date_parts.get("dd")
				mm = date_parts.get("mm")
				yyyy = date_parts.get("yyyy")
			
			if code and city_code and dd and mm and yyyy:
				# Format: SCMY22102025
				base = code + city_code + dd + mm + yyyy
				self.unique_id = self.make_unique(base, self.doctype, "unique_id")
			else:
				msg = "ID Gen Failed. Code: {0}, City: {1}, DateParts: {2}".format(code, city_code, date_parts)
				frappe.log_error(msg, "Unique ID Script")
		except Exception as e:
			frappe.log_error(
				f"Error generating unique ID for Solve Event {self.name}: {str(e)}",
				"Unique ID Generation Error"
			)


def cleanup_completed_event_keywords():
	"""
	Daily scheduled task to remove keywords from Glific checkin flow for completed solve events.
	An event is considered complete when its end_date_time has passed.
	"""
	try:
		from frappe.utils import now_datetime
		
		# Get event_checkin_flow_id from Solve Ninja Settings
		flow_id = frappe.db.get_single_value("Solve Ninja Settings", "event_checkin_flow_id")
		
		if not flow_id:
			frappe.log_error(
				"Event Checkin Flow ID not configured in Solve Ninja Settings",
				"Cleanup Completed Event Keywords Error"
			)
			return
		
		# Find all solve events that are complete (end_date_time < now) and have a unique_id
		current_time = now_datetime()
		completed_events = frappe.get_all(
			"Solve Event",
			filters={
				"end_date_time": ["<", current_time],
				"unique_id": ["!=", ""]
			},
			fields=["name", "unique_id", "title"]
		)
		
		if not completed_events:
			frappe.logger("scheduler").info("No completed solve events found for keyword cleanup")
			return
		
		# Get GlificSettings document
		glific_settings = frappe.get_doc("Glific Settings")
		
		# Collect all unique_ids to remove (convert to lowercase for Glific)
		keywords_to_remove = []
		event_names = []
		
		for event in completed_events:
			if event.get("unique_id"):
				# Glific stores keywords in lowercase
				keywords_to_remove.append(event["unique_id"].lower())
				event_names.append(f"{event['name']} ({event.get('title', 'N/A')})")
		
		if not keywords_to_remove:
			frappe.logger("scheduler").info("No keywords to remove from completed solve events")
			return
		
		# Remove keywords from flow
		response = glific_settings.update_flow(
			flow_id=flow_id,
			remove_keywords=keywords_to_remove
		)
		
		# Check for errors in response
		if response and "data" in response:
			data = response.get("data", {})
			update_flow_data = data.get("updateFlow", {})
			errors = update_flow_data.get("errors", [])
			
			if errors:
				error_messages = [err.get("message", "") for err in errors if err.get("message")]
				if error_messages:
					frappe.log_error(
						f"Error removing keywords from flow: {', '.join(error_messages)}\n"
						f"Events processed: {', '.join(event_names)}",
						"Cleanup Completed Event Keywords Error"
					)
			else:
				# Success - log the cleanup
				frappe.logger("scheduler").info(
					f"Successfully removed keywords for {len(keywords_to_remove)} completed solve events: "
					f"{', '.join(event_names)}"
				)
		else:
			frappe.log_error(
				f"Unexpected response format when removing keywords from flow. "
				f"Events attempted: {', '.join(event_names)}",
				"Cleanup Completed Event Keywords Error"
			)
			
	except Exception as e:
		frappe.log_error(
			f"Error cleaning up completed event keywords: {str(e)}\n{frappe.get_traceback()}",
			"Cleanup Completed Event Keywords Error"
		)
