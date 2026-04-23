# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from solve_ninja.services.user.profile_summary import _generate_profile_summary
from datetime import timedelta


def _incremental_profile_summary_allowlist() -> set:
    """
    User names in this site-config list get incremental (force=False) on the scheduler; others
    get full regen (force=True). See incremental_profile_summary_users in site config.
    """
    raw = frappe.get_site_config().get("incremental_profile_summary_users")
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        return set(str(x) for x in raw if x)
    return {str(raw)}


class UserManager:

    @staticmethod
    def generate_user_summary_scheduler() -> None:
        allow = _incremental_profile_summary_allowlist()
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
            FROM `tabEvents` e
            LEFT JOIN `tabUser` u ON u.email = e.user
            LEFT JOIN `tabUser Metadata` um ON um.name = u.name
            WHERE e.creation > COALESCE(um.ai_summary_last_updated, '1970-01-01')
            GROUP BY
                e.user, u.name, u.email,
                um.name,
                um.ai_summary_status,
                um.ai_summary_last_updated,
                um.ai_summary_processing_started_at
        """, as_dict=True)
        for u in users:
            user_name = u.user_name
            status = u.ai_summary_status
            user_metadata_name = u.user_metadata_name
            user_email = u.user_email
            ai_summary_processing_started_at = u.ai_summary_processing_started_at
            ai_summary_last_updated = u.ai_summary_last_updated
            latest_event_creation = u.latest_event_creation

            if not user_name or not user_metadata_name:
                continue

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

            # Allowlist: users in incremental_profile_summary_users get scheduled incremental;
            # everyone else gets full (force=True). If allowlist is empty, all get full.
            schedule_force = user_name not in allow if allow else True

            frappe.db.set_value(
                "User Metadata",
                user_metadata_name,
                {
                    "ai_summary_status": "Pending"
                }
            )

            frappe.enqueue(
            "solve_ninja.services.user.user_manager.generate_summary_for_user_",
                user_name=user_name,
                user_email=user_email,
                user_metadata_name=user_metadata_name,
                force=schedule_force,
                queue="long",
                timeout=600
            )

    @staticmethod
    def generate_summary_for_user(
        user_name: str,
        user_email: str|None = None,
        user_metadata_name: str|None = None,
        force: bool = True,
    ) -> None:
        try:

            if not user_email:
                user_email = frappe.db.get_value("User", user_name, "email")

            if not user_metadata_name:
                user_metadata_name = frappe.db.get_value("User Metadata", user_name, "name")

                if not user_metadata_name:
                    return

            last_event_creation = frappe.db.get_value(
                "Events",
                filters={"user": user_email},
                fieldname="creation",
                order_by="creation desc",
            )
            if not last_event_creation and not force:
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
            frappe.db.commit()
            md = frappe.db.get_value(
                "User Metadata",
                user_metadata_name,
                ["summary", "ai_summary_last_updated"],
                as_dict=True,
            ) or {}
            prev = (md.get("summary") or "").strip()
            since = None if force else md.get("ai_summary_last_updated")
            summary_result = _generate_profile_summary(
                user_name,
                previous_summary=prev or None,
                incremental_since=since,
                events_user=user_email,
                force_full=force,
            )

            frappe.db.set_value(
                "User Metadata", user_metadata_name,
                {
                    "summary": summary_result.summary,
                    "ai_summary_last_updated": last_event_creation or frappe.utils.now_datetime(),
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

def generate_user_summary_scheduler_():
    UserManager.generate_user_summary_scheduler()

def generate_summary_for_user_(
        user_name: str,
        user_email: str|None = None,
        user_metadata_name: str|None = None,
        force: bool = True,
    ):
    UserManager.generate_summary_for_user(user_name=user_name, user_email=user_email, user_metadata_name=user_metadata_name, force=force)