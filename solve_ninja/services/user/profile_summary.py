# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

"""
Profile summary service: builds user portfolio from Events + Energy Point Log,
generates AI summary via ai_manager, and updates User Metadata.
"""

import asyncio
import frappe
from datetime import datetime
from solve_ninja.services.ai_manager import _load_prompt, run_llm_responses_with_instructor, AIManager
from solve_ninja.models.ai import ProfileSummaryOutput
from solve_ninja.api.profile import get_user_profile

PROFILE_SUMMARY_SYSTEM_PROMPT = _load_prompt("profile_summary.md")

class ProfileSummary:
    def get_user_portfolio(user: str) -> dict:
        """
        Build portfolio from profile.get_user_actions (Events) + Energy Point Log (skills).
        Uses same event source as get_user_profile API.
        """
        if not user or not frappe.db.exists("User", user):
            return {"first_name": "", "actions": []}

        from solve_ninja.api.profile import get_user_actions

        user_doc = frappe.db.get_value("User", user, ["first_name"], as_dict=True)
        first_name = (user_doc and user_doc.get("first_name")) or ""

        # Use same events source as profile API (get_user_profile)
        actions_raw, _ = get_user_actions(user)

        # Get Energy Point Logs for skills (badge, reason) per event
        eps = frappe.get_all(
            "Energy Point Log",
            filters={
                "user": user,
                "type": "Auto",
                "reverted": 0,
                "reference_doctype": "Events",
            },
            fields=["reference_name", "badge", "reason"],
        )
        skills_by_event = {}
        for ep in eps:
            ref = ep.get("reference_name")
            if ref not in skills_by_event:
                skills_by_event[ref] = []
            skills_by_event[ref].append({
                "name": ep.get("badge") or "",
                "label": ep.get("badge") or "",
                "relevance": ep.get("reason") or "",
            })

        # Build user_portfolio.actions to match cmp_backend / get_user_profile structure
        actions = []
        total_hours_invested = 0
        for action in actions_raw:
            action_skills = [
                {"name": s["name"], "label": s["label"], "relevance": s["relevance"]}
                for s in skills_by_event.get(action.get("event_id"), [])
            ]
            actions.append({
                "title": action.get("title") or "",
                "description": (action.get("description") or "")[:500],
                "hours_invested": float(action.get("hours_invested") or 0),
                "category": action.get("category") or "",
                "type": action.get("type") or "",
                "skills": action_skills,
            })
            total_hours_invested += actions[-1]["hours_invested"]

        return {
            "first_name": first_name,
            "actions": actions,
            "total_hours_invested": total_hours_invested,
            "total_actions": len(actions),
        }

    @staticmethod
    def generate_profile_summary(user_name: str) -> str:
        """
        Generate AI summary for user from their portfolio.
        Returns summary string; raises on error.
        """
        profile = get_user_profile(user_name)
        if not profile.get("actions"):
            return ""

        actions = []
        total_hours_invested = 0

        for action in profile["actions"]:
            action_skills = [
                {
                    "name": skill["name"],
                    "label": skill["label"],
                    "relevance": skill["relevance"],
                }
                for skill in action["skills"]
            ]
            actions.append(
                {
                    "title": action["title"],
                    "description": action["description"],
                    "hours_invested": action["hours_invested"],
                    "category": action["category"],
                    "type": action["type"],
                    "skills": action_skills,
                }
            )
            total_hours_invested += action["hours_invested"]
        

        messages = [
            {"role": "system", "content": PROFILE_SUMMARY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"user name: {profile.get('first_name', '')}\n"
                    f"total hours invested: {total_hours_invested}\n"
                    f"total number of actions: {len(actions)}\n"
                    f"today's date: {datetime.now().strftime('%Y-%m-%d')}\n"
                    f"all_actions: {str(actions)}"
                ),
            },
        ]

        response = asyncio.run(run_llm_responses_with_instructor(
            input=messages,
            response_model=ProfileSummaryOutput,
            temperature=AIManager.TEMPERATURE,
        ))
        return response.summary

    

    def process_user_summary_update_queue():
        """
        Hourly job: process all Pending users in User Summary Update Queue.
        For each user: generate summary, update User Metadata, create Log, mark queue Completed/Failed.
        """
        if not frappe.db.exists("DocType", "User Summary Update Queue"):
            return

        queue_records = frappe.get_all(
            "User Summary Update Queue",
            filters={"status": "Pending"},
            fields=["name", "user", "trigger_event_id"],
        )
        # Dedupe by user (multiple events = multiple queue entries for same user)
        users_seen = set()
        for rec in queue_records:
            user = rec.get("user")
            if not user or user in users_seen:
                continue
            users_seen.add(user)

            # Process each user (enqueue to avoid blocking)
            frappe.enqueue(
                _process_single_user_summary,
                queue="default",
                user=user,
                queue_record_names=[r["name"] for r in queue_records if r.get("user") == user],
            )

    def _process_single_user_summary(user: str, queue_record_names: list):
        """Process summary for one user; update queue and create log."""
        from frappe.utils import now_datetime

        portfolio = get_user_portfolio(user)
        events_count = portfolio.get("total_actions", 0)
        hours_invested = portfolio.get("total_hours_invested", 0)

        for qname in queue_record_names:
            try:
                frappe.db.set_value("User Summary Update Queue", qname, "status", "Processing")
            except Exception:
                pass
        frappe.db.commit()

        try:
            summary = generate_profile_summary(user)
            update_user_summary_in_metadata(user, summary)

            # Create log
            frappe.get_doc({
                "doctype": "User Summary Update Log",
                "user": user,
                "status": "Success",
                "summary_preview": (summary or "")[:200],
                "events_count": events_count,
                "hours_invested": hours_invested,
                "processed_at": now_datetime(),
            }).insert(ignore_permissions=True)

            for qname in queue_record_names:
                frappe.db.set_value(
                    "User Summary Update Queue", qname,
                    {"status": "Completed", "processed_at": now_datetime(), "error_message": ""}
                )
        except Exception as e:
            frappe.log_error(f"User summary update failed for {user}: {str(e)}", "User Summary Update Error")
            frappe.get_doc({
                "doctype": "User Summary Update Log",
                "user": user,
                "status": "Failed",
                "error_message": str(e),
                "events_count": events_count,
                "hours_invested": hours_invested,
                "processed_at": now_datetime(),
            }).insert(ignore_permissions=True)
            for qname in queue_record_names:
                frappe.db.set_value(
                    "User Summary Update Queue", qname,
                    {"status": "Failed", "processed_at": now_datetime(), "error_message": str(e)}
                )
        frappe.db.commit()
