# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from solve_ninja.services.user.profile_summary import ProfileSummary
from datetime import timedelta

class UserManager:

    @staticmethod
    def generate_user_summary_scheduler() -> None:
        users = frappe.db.sql("""
            SELECT 
                e.user,
                MAX(e.creation) as latest_event_creation,
                um.name as user_metadata_name,
                um.ai_summary_status,
                um.ai_summary_last_updated,
                um.ai_summary_processing_started_at,
                u.name as user_name,
                u.email as user_email
            FROM `tabEvent` e
            LEFT JOIN `tabUser` u ON u.email = e.user
            LEFT JOIN `tabUser Metadata` um ON um.name = u.name
            WHERE e.creation > COALESCE(um.ai_summary_last_updated, '1970-01-01')
            GROUP BY e.user
        """, as_dict=True)
        for u in users:
            user_name = u.user_name
            status = u.ai_summary_status
            user_metadata_name = u.user_metadata_name
            user_email = u.user_email
            ai_summary_processing_started_at = u.ai_summary_processing_started_at
            ai_summary_last_updated = u.ai_summary_last_updated
            latest_event_creation = u.latest_event_creation

            now = frappe.utils.now_datetime()

            if status == "Pending":
                continue

            if (
                status == "Processing"
                and ai_summary_processing_started_at
                and ai_summary_processing_started_at > now - timedelta(hours=2)
            ):
                continue
            
            if ai_summary_last_updated and latest_event_creation <= ai_summary_last_updated:
                continue

            frappe.db.set_value(
                "User Metadata",
                user_metadata_name,
                {   
                    "ai_summary_status": "Pending"
                }
            )
                        
            frappe.enqueue(
            "solve_ninja.services.user.user_manager.generate_summary_for_user",
                user_name=user_name,
                user_email=user_email,
                user_metadata_name=user_metadata_name,
                queue="long",
                timeout=600
            )   

    @staticmethod
    def generate_summary_for_user(
        user_name: str, 
        user_email: str|None = None,
        user_metadata_name: str|None = None
    ) -> None:
        try:

            if not user_email:
                user_email = frappe.db.get_value("User", user_name, "email")
            
            if not user_metadata_name:
                result = frappe.db.sql("""
                                    SELECT name
                                    FROM `tabUser Metadata`
                                    WHERE user = %s
                                """, (user_name,), as_dict=True)
                
                if not result or len(result) == 0:
                    return
                user_metadata_name = result[0]["name"]
            
            result = frappe.db.sql("""
                                    SELECT MAX(creation) as last_event_creation
                                    FROM `tabEvent`
                                    WHERE user = %s
                                """, (user_email,), as_dict=True)
            
            last_event_creation = result[0]["last_event_creation"]
            if not last_event_creation:
                frappe.db.set_value(
                    "User Metadata",
                    user_metadata_name,
                    "ai_summary_status",
                    "Success"
                )
                frappe.db.commit()
                return
            
            frappe.db.set_value(
                "User Metadata",
                user_metadata_name,
                {
                    "ai_summary_status": "Processing",
                    "ai_summary_processing_started_at": frappe.utils.now_datetime()
                }
            )
            summary = ProfileSummary.generate_profile_summary(user_name)
            
            frappe.db.set_value(
                "User Metadata", user_metadata_name,
                {
                    "summary": summary, 
                    "ai_summary_last_updated": last_event_creation,
                    "ai_summary_status": "Success",
                    "ai_summary_processing_started_at": None
                }
            )
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "User Summary Generation Error")
            if user_metadata_name is not None:
                frappe.db.set_value(
                    "User Metadata",
                    user_metadata_name,
                    {
                        "ai_summary_status": "Failed",
                        "ai_summary_processing_started_at": None
                    }
                )
                frappe.db.commit()
            return