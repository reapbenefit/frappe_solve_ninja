# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint
from samaaja.samaaja.doctype.user_metadata.user_metadata import UserMetadata as BaseUserMetadata
from solve_ninja.services.user.user_manager import UserManager

class CustomUserMetadata(BaseUserMetadata):
    @frappe.whitelist()
    def generate_ai_summary(self, force=1):
        """
        Generate AI summary from the user's events and skills; updates this doc's summary field.

        force: 1 (default) = full portfolio regen. 0 = incremental (previous summary + new events only).
        Omitted args use default ``force=1`` (full).         The ``incremental_profile_summary_users`` site config key controls which users get
        incremental (vs full) on the scheduled job; desk uses only ``force`` from this call.
        """
        if not self.name:
            frappe.throw("User is required")

        # bool(cint(0)) is False, bool(cint(1)) is True — pass through as UserManager "force" full-refresh flag
        full_refresh = bool(cint(force))
        return UserManager.generate_summary_for_user(self.name, force=full_refresh)
