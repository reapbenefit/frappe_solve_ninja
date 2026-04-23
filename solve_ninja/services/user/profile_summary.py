# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

"""
Profile summary service: builds user portfolio from Events + Energy Point Log,
generates AI summary via ai_manager, and updates User Metadata.
"""

import asyncio
import json
import frappe
from datetime import datetime
from solve_ninja.services.ai_manager import _load_prompt, run_llm_responses_with_instructor, AIManager
from solve_ninja.models.ai import ProfileSummaryOutput
from solve_ninja.models.user_portfolio import ProfileSummaryWithPortfolio, UserPortfolio
from solve_ninja.api.profile import _build_user_portfolio

PROFILE_SUMMARY_SYSTEM_PROMPT = _load_prompt("profile_summary.md")
PROFILE_SUMMARY_INCREMENTAL_PROMPT = _load_prompt("profile_summary_incremental.md")


def _empty_portfolio() -> UserPortfolio:
    return UserPortfolio(
        first_name="",
        actions=[],
        total_hours_invested=0.0,
        total_actions=0,
    )


def _portfolio_stats_block(profile) -> str:
    return (
        f"user name: {profile.first_name}\n"
        f"total hours invested: {profile.total_hours_invested}\n"
        f"total number of actions: {profile.total_actions}\n"
        f"today's date: {datetime.now().strftime('%Y-%m-%d')}\n"
    )


def _generate_profile_summary(
    user_name: str,
    *,
    previous_summary: str | None = None,
    incremental_since=None,
    events_user: str | None = None,
    force_full: bool = False,
) -> ProfileSummaryWithPortfolio:
    """
    Generate AI summary. When force_full is False, previous_summary and
    incremental_since enable incremental (token-light) updates.
    """
    existing = (previous_summary or "").strip()
    if not user_name or not frappe.db.exists("User", user_name):
        return ProfileSummaryWithPortfolio(
            portfolio=_empty_portfolio(),
            summary="",
            existing_summary=existing,
        )

    use_incremental = (
        not force_full
        and bool(existing)
        and incremental_since is not None
    )

    if use_incremental:
        profile = _build_user_portfolio(
            user_name,
            since_creation=incremental_since,
            events_user=events_user,
        )
        if not profile.actions:
            return ProfileSummaryWithPortfolio(
                portfolio=profile,
                summary=existing,
                existing_summary=existing,
            )

        system_prompt = PROFILE_SUMMARY_INCREMENTAL_PROMPT
        user_content = (
            f"{_portfolio_stats_block(profile)}"
            f"previous_summary:\n{existing}\n"
            f"new_actions_since_last_summary: {json.dumps(profile.model_dump()['actions'])}"
        )
    else:
        profile = _build_user_portfolio(user_name, events_user=events_user)
        if not profile.actions:
            return ProfileSummaryWithPortfolio(
                portfolio=profile,
                summary="",
                existing_summary=existing,
            )

        system_prompt = PROFILE_SUMMARY_SYSTEM_PROMPT
        user_content = (
            f"{_portfolio_stats_block(profile)}"
            f"all_actions: {json.dumps(profile.model_dump()['actions'])}"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    response = asyncio.run(run_llm_responses_with_instructor(
        input=messages,
        response_model=ProfileSummaryOutput,
        temperature=AIManager.TEMPERATURE,
    ))
    return ProfileSummaryWithPortfolio(
        portfolio=profile,
        summary=response.summary,
        existing_summary=existing,
    )
