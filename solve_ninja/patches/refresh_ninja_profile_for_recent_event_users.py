import frappe
from frappe.utils import add_to_date, now_datetime


def execute():
    """Refresh Ninja Profile aggregates for users with any Event created in the last 12 months.

    Uses lifetime totals per user (same as update_ninja_profile on save).
    """
    from solve_ninja.doc_events.events import update_ninja_profile

    cutoff = add_to_date(now_datetime(), months=-12, as_datetime=True)
    users = frappe.get_all(
        "Events",
        filters={
            "creation": (">=", cutoff),
            "user": ("is", "set"),
        },
        pluck="user",
    )
    for user in sorted(set(users)):
        update_ninja_profile(user)
