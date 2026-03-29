# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from samaaja.samaaja.doctype.user_metadata.user_metadata import UserMetadata as BaseUserMetadata
from solve_ninja.services.user.user_manager import UserManager

class CustomUserMetadata(BaseUserMetadata):
    @frappe.whitelist()
    def generate_ai_summary(self):
        """Generate AI summary from user's events and skills, update this doc's summary field."""
        user = self.user
        if not user:
            frappe.throw("User is required")

        return UserManager.generate_summary_for_user(user)
