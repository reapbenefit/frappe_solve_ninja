# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.core.doctype.user.user import User as BaseUser


class CustomUser(BaseUser):
	def on_trash(self):
		"""
		Delete related records before calling parent's on_trash.
		Deletes: Login OTP, Events, Solve Event Participation, Ninja Profile, User Metadata
		"""
		# Check if running in production environment
		is_production = not frappe.conf.get("developer_mode", 0)
		
		# In production, validate against approved list
		if is_production:
			approved_list = frappe.conf.get("approved_user_deletion_list", [])
			if not approved_list:
				frappe.throw(
					"No approved user deletion list configured. Please add 'approved_user_deletion_list' to site_config.json",
					frappe.ValidationError
				)
			
			if frappe.session.user not in approved_list:
				frappe.throw(
					f"User '{frappe.session.user}' is not authorized to delete users. "
					f"Only users in the approved deletion list can delete users in production.",
					frappe.ValidationError
				)
		# Delete Login OTP records if they exist
		frappe.db.delete("Login OTP", filters={"user": self.name})
		
		events = frappe.get_all("Events", filters={"user": self.name}, pluck="name")
		# Delete Events Reviews records if they exist
		frappe.db.delete("Events Review", filters={"events": ("in", events)})

		# Delete Events records if they exist
		frappe.db.delete("Events", filters={"user": self.name})

		frappe.db.delete("Mentorship Request", filters={"mentee_user": self.name})
		frappe.db.delete("Mentorship Request", filters={"assigned_mentor": self.name})
		
		frappe.db.delete("OAuth Bearer Token", filters={"user": self.name})
		# Delete Solve Event Participation records if they exist
		frappe.db.delete("Solve Event Participation", filters={"user": self.name})
		frappe.db.delete("Solve Event Registration", filters={"user": self.name})
		frappe.db.delete("User Review", filters={"user": self.name})
		frappe.db.delete("User Profile QR", filters={"user": self.name})
		frappe.db.delete("User badge", filters={"user": self.name})
		frappe.db.delete("Notification Settings", filters={"user": self.name})
		# Delete Ninja Profile if it exists
		if frappe.db.exists("Ninja Profile", self.name):
			frappe.delete_doc("Ninja Profile", self.name, ignore_permissions=True)
		
		# Delete User Metadata if it exists
		if frappe.db.exists("User Metadata", self.name):
			frappe.delete_doc("User Metadata", self.name, ignore_permissions=True)
		
		# Call parent's on_trash to handle standard User deletion logic
		super().on_trash()
