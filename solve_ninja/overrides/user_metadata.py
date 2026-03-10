# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from samaaja.samaaja.doctype.user_metadata.user_metadata import UserMetadata as BaseUserMetadata


class CustomUserMetadata(BaseUserMetadata):
    @frappe.whitelist()
    def generate_ai_summary(self):
        """Generate AI summary from user's events and skills, update this doc's summary field."""
        from solve_ninja.services.profile_summary import generate_profile_summary, update_user_summary_in_metadata

        user = self.name
        if not user:
            frappe.throw("User is required")

        summary = generate_profile_summary(user)
        update_user_summary_in_metadata(user, summary)
        self.reload()
        return {"summary": summary}
