# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
import io
from frappe.model.document import Document
from frappe.utils import now_datetime
from solve_ninja.utils import is_unique_id_duplicate

class SocialMedia(Document):
	def validate(self):
		"""Generate unique ID and generate QR code when unique_id changes"""
		doc_before_save = self.get_doc_before_save()
		
		# Check if fields that affect unique_id have changed
		# Note: date is always current date, so we only check platform and city
		should_regenerate_id = False
		if doc_before_save:
			# Check if any field that affects unique_id generation has changed
			fields_to_check = ["platform", "city"]
			for field in fields_to_check:
				if doc_before_save.get(field) != self.get(field):
					should_regenerate_id = True
					break
		
		# Generate unique_id if not already set or if relevant fields have changed
		if not self.unique_id or should_regenerate_id:
			self.generate_unique_id()
		
		# Check if unique_id has changed
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
			if old_url != new_url and new_url or (not self.qr and self.checkin_url):
				self.generate_qr_code(self.checkin_url)
		elif self.get("checkin_url"):
			# New document with checkin_url set
			self.generate_qr_code(self.get("checkin_url"))
	
	def platform_code(self, platform):
		"""Convert platform name to code"""
		if not platform:
			return "X"
		
		platform_lower = str(platform).strip().lower()
		
		# Platform mappings
		if platform_lower == "linkedin":
			return "L"
		elif platform_lower == "instagram":
			return "I"
		elif platform_lower == "facebook":
			return "F"
		
		# Fallback: return first letter uppercase
		return platform_lower[0].upper() if platform_lower else "X"
	
	def city_three_letters(self, city_link):
		"""Extract three letters from city name"""
		if not city_link:
			return "XXX"
		
		# Get city_name from Samaaja Cities doctype
		city_name = frappe.db.get_value("Samaaja Cities", city_link, "city_name")
		if not city_name:
			return "XXX"
		
		# Extract first 3 alphabetic letters
		text = str(city_name)
		letters = ""
		i = 0
		while i < len(text) and len(letters) < 3:
			ch = text[i]
			if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
				letters = letters + ch
			i = i + 1
		
		letters = letters.upper()
		
		# Pad with X if less than 3 letters
		if len(letters) >= 3:
			return letters[:3]
		elif len(letters) > 0:
			return letters + "X" * (3 - len(letters))
		return "XXX"
	
	def get_current_date_parts(self):
		"""Get current date parts: YY, MM, DD"""
		now = now_datetime()
		return {
			"yy": str(now.year)[-2:],  # Last 2 digits of year
			"mm": str(now.month).zfill(2),  # 2-digit month
			"dd": str(now.day).zfill(2)  # 2-digit day
		}
	
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
		"""Generate unique ID based on platform, city, and current date"""
		# Get platform code
		platform_code = self.platform_code(self.get("platform"))
		
		# Get city code (3 letters)
		city_code = self.city_three_letters(self.get("city"))
		
		# Get current date parts
		date_parts = self.get_current_date_parts()
		
		yy = date_parts.get("yy")
		mm = date_parts.get("mm")
		dd = date_parts.get("dd")
		
		if platform_code and city_code and yy and mm and dd:
			# Format: SM + platform_code + city_code + YY + MM + DD
			base = "SM" + platform_code + city_code + yy + mm + dd
			self.unique_id = self.make_unique(base, self.doctype, "unique_id")
		else:
			frappe.throw(f"ID Gen Failed. Platform: {platform_code}, City: {city_code}, DateParts: {date_parts}")
	
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
			
			# Build URL with unique_id: {base_url}&text={unique_id}
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
				f"Error updating checkin_url for Social Media {self.name}: {str(e)}",
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
			# Get program_checkin_flow_id from Solve Ninja Settings
			flow_id = frappe.db.get_single_value("Solve Ninja Settings", "program_checkin_flow_id")
			
			if not flow_id:
				frappe.msgprint(
					"Program Checkin Flow ID not configured in Solve Ninja Settings",
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
				f"Error updating flow keyword for Social Media {self.name}: {error_msg}",
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
	
	def generate_qr_code(self, data):
		"""Generate QR code from data (unique_id or URL) and save it to qr field"""
		from pyqrcode import create as qrcreate
		from frappe.utils.file_manager import save_file
		
		if not data:
			return
		
		# Get document name - autoname ensures name is available in validate()
		doc_name = self.name or frappe.generate_hash(length=10)
		
		# Generate unique file name
		file_name = f"qr_social_{doc_name}.png"
		
		# Generate QR code to BytesIO buffer
		qr = qrcreate(data)
		buffer = io.BytesIO()
		qr.png(buffer, scale=8, module_color=[0, 0, 0, 180], background=[0xFF, 0xFF, 0xFF])
		buffer.seek(0)
		file_content = buffer.read()
		
		# Delete old QR code file if exists
		if self.qr:
			old_file = frappe.db.get_value("File", {"file_url": self.qr}, "name")
			if old_file:
				frappe.delete_doc("File", old_file, ignore_permissions=True, force=True)
		
		# Save and attach file using Frappe's save_file utility
		file_doc = save_file(
			fname=file_name,
			content=file_content,
			dt=self.doctype,
			dn=doc_name,
			folder=None,
			is_private=0,
			df="qr"  # Attach to qr field
		)
		
		# Set the qr field to the file URL
		self.qr = file_doc.file_url
