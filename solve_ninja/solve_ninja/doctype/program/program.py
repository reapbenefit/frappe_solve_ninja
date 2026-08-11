# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
import io
from frappe.model.document import Document
from solve_ninja.utils import is_unique_id_duplicate

class Program(Document):
	def validate(self):
		"""Generate unique ID, update checkin_url from settings and generate QR code when URL changes"""
		doc_before_save = self.get_doc_before_save()

		# Ensure User Organization exists with the same ID as this Program
		self.ensure_user_organization()
		
		# Check if fields that affect unique_id have changed
		should_regenerate_id = False
		if doc_before_save:
			# Check if any field that affects unique_id generation has changed
			fields_to_check = ["program_sub_source", "program_source", "college_name", "city", "start_date"]
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

	def ensure_user_organization(self):
		"""Create User Organization with the same document ID as this Program (on Program save only)."""
		org_id = self.name or self.program_name
		if not org_id:
			return None

		if frappe.db.exists("User Organization", org_id):
			if not frappe.db.get_value("User Organization", org_id, "org_id"):
				frappe.db.set_value(
					"User Organization", org_id, "org_id", org_id, update_modified=False
				)
			return org_id

		org_doc = frappe.get_doc({
			"doctype": "User Organization",
			"org_name": org_id,
			"org_id": org_id,
		})
		org_doc.insert(ignore_permissions=True)

		if org_doc.name != org_id:
			frappe.rename_doc(
				"User Organization",
				org_doc.name,
				org_id,
				force=True,
				merge=False,
			)

		return org_id
	
	def update_checkin_url(self):
		"""Update checkin_url from Solve Ninja Settings with unique_id"""
		
		# Get base URL from Solve Ninja Settings
		base_url = frappe.get_doc("Solve Ninja Settings").get("checkin_url")
		
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
				f"Error updating flow keyword for Program {self.name}: {error_msg}",
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
		try:
			from pyqrcode import create as qrcreate
			from frappe.utils.file_manager import save_file
			
			# Get document name - autoname "field:program_name" ensures name is available in validate()
			doc_name = self.name or (self.get("program_name") if self.get("program_name") else frappe.generate_hash(length=10))
			
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
			
		except ImportError:
			frappe.log_error(
				"pyqrcode library not found. Please install it using: pip install pyqrcode[png]",
				"QR Code Generation Error"
			)
			frappe.throw("QR code generation failed: pyqrcode library not installed")
		except Exception as e:
			frappe.log_error(
				f"Error generating QR code for Program {self.name}: {str(e)}",
				"QR Code Generation Error"
			)
			# Don't throw error, just log it so document can still be saved
			frappe.msgprint(f"Failed to generate QR code: {str(e)}", alert=True, indicator="orange")
	
	def program_source_code(self, value):
		"""Convert program_source or program_sub_source to code (3 letters)"""
		if not value:
			return "XXX"
		
		# If value is a link field, get the actual name/value
		# For Link fields, value is the name of the linked document
		# Try to get the program_source field from the linked document
		try:
			# Check if it's a Program Source document
			if frappe.db.exists("Program Source", value):
				source_doc = frappe.get_doc("Program Source", value)
				v = str(source_doc.get("program_source") or value).strip().lower()
			# Check if it's a Program Sub Source document
			elif frappe.db.exists("Program Sub Source", value):
				sub_source_doc = frappe.get_doc("Program Sub Source", value)
				v = str(sub_source_doc.get("sub_source") or value).strip().lower()
			else:
				v = str(value).strip().lower()
		except:
			v = str(value).strip().lower()
		
		# Manual alphanumeric strip (Internal Logic)
		letters = ""
		i = 0
		while i < len(v) and len(letters) < 3:
			ch = v[i]
			if ("a" <= ch <= "z"):
				letters = letters + ch
			i = i + 1
		letters = letters.upper()
		
		# Pad with X if less than 3 letters
		if len(letters) >= 3:
			return letters[:3]
		elif len(letters) > 0:
			return letters + "X" * (3 - len(letters))
		return "XXX"
	
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
	
	def college_two_letters(self, value):
		"""Extract two letters from college name"""
		if not value:
			return "XX"
		
		# Manual alphanumeric strip (Internal Logic)
		text = str(value)
		letters = ""
		i = 0
		while i < len(text) and len(letters) < 2:
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
	
	def extract_date_parts(self, date_value):
		"""Extract day, month, year from date"""
		if not date_value:
			return None
		
		# If it is already a date object
		if hasattr(date_value, "day") and hasattr(date_value, "month") and hasattr(date_value, "year"):
			d_str = str(date_value.day)
			m_str = str(date_value.month)
			y_str = str(date_value.year)
			
			if len(d_str) == 1:
				d_str = "0" + d_str
			if len(m_str) == 1:
				m_str = "0" + m_str
				
			result = {}
			result["dd"] = d_str
			result["mm"] = m_str
			result["yyyy"] = y_str
			result["yy"] = y_str[-2:]  # Last 2 digits of year
			return result
		
		# If it is a string
		s = str(date_value).strip()
		date_part = s.replace("/", "-").replace(".", "-")
		parts = date_part.split("-")
		
		# Case 1: DD-MM-YYYY
		if len(parts) == 3 and len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
			result = {}
			result["dd"] = parts[0]
			result["mm"] = parts[1]
			result["yyyy"] = parts[2]
			result["yy"] = parts[2][-2:]  # Last 2 digits of year
			return result
		
		# Case 2: YYYY-MM-DD
		if len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
			result = {}
			result["yyyy"] = parts[0]
			result["mm"] = parts[1]
			result["dd"] = parts[2]
			result["yy"] = parts[0][-2:]  # Last 2 digits of year
			return result
		
		# Fallback: try frappe util
		try:
			dt = frappe.utils.getdate(date_value)
			result = {}
			result["dd"] = dt.strftime("%d")
			result["mm"] = dt.strftime("%m")
			result["yyyy"] = dt.strftime("%Y")
			result["yy"] = dt.strftime("%y")  # 2-digit year
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
		"""Generate unique ID based on orientation format: O<program>_<college>_<city>_<date>_<year>
		Format: OCCLDUDEL230825
		- O: Orientation prefix (fixed)
		- CCL: Program code (3 letters from program_source/program_sub_source)
		- DU: College code (2 letters from college_name)
		- DEL: City code (3 letters from city)
		- 23: Day (DD)
		- 08: Month (MM)
		- 25: Year (YY, last 2 digits)
		"""
		
		# Use program_sub_source first, fallback to program_source
		source_value = self.get("program_sub_source") or self.get("program_source")
		program_code = self.program_source_code(source_value)
		
		# Get college code (2 letters)
		college_code = self.college_two_letters(self.get("college_name"))
		
		# Get city code (3 letters)
		city_code = self.city_three_letters(self.get("city"))
		
		# Get date parts
		date_parts = self.extract_date_parts(self.get("start_date"))
		
		dd = None
		mm = None
		yy = None
		
		if date_parts:
			dd = date_parts.get("dd")
			mm = date_parts.get("mm")
			yy = date_parts.get("yy")
		
		if program_code and college_code and city_code and dd and mm and yy:
			# Format: O + program_code (3) + college_code (2) + city_code (3) + DD + MM + YY
			base = "O" + program_code + college_code + city_code + dd + mm + yy
			self.unique_id = self.make_unique(base, self.doctype, "unique_id")
		else:
			msg = "ID Gen Failed. Program: {0}, College: {1}, City: {2}, DateParts: {3}".format(
				program_code, college_code, city_code, date_parts
			)
			frappe.log_error(msg, "Unique ID Generation Error")
		
