# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count
from pypika.terms import Order
from frappe.utils import now_datetime, add_to_date

def update_subcategory(doc, method):
    if not doc.subcategory and doc.category:
        subcategory = frappe.db.exists("Event Sub Category", doc.category)
        if not subcategory:
            subcategory = frappe.get_doc({
                "doctype": "Event Sub Category",
                "subcategory": doc.category
            }).insert(ignore_permissions=True)
            doc.subcategory = doc.category

def after_insert(doc, method=None):
    """
    Hook that runs after an Events document is inserted.
    - Updates last action metadata on the linked Ninja Profile.
    - Updates top 3 event categories in the User's interest field.
    """
    update_action_detail_in_ninja_profile(doc)
    update_user_interest_from_top_categories(doc.user)

def update_action_detail_in_ninja_profile(doc):
    """
    Updates the Ninja Profile with the latest action details when an Event is created or modified.

    Args:
        doc (Document): The Event document that triggered the hook.
        method (str): The name of the hook method (e.g. "after_insert" or "on_update").
    """
    if doc.user and frappe.db.exists("Ninja Profile", doc.user):
        ninja_profile = frappe.get_doc("Ninja Profile", doc.user)

        # Set latest action metadata
        ninja_profile.last_action = doc.name
        ninja_profile.last_action_date = doc.creation
        ninja_profile.last_action_type = doc.type
        ninja_profile.last_action_sub_type = doc.sub_type
        ninja_profile.last_action_category = doc.category

        # Save with ignore_permission in case it's triggered from background or guest
        ninja_profile.flags.ignore_permissions = True
        ninja_profile.save()

def update_user_interest_from_top_categories(user: str):
    """
    Updates the User's 'interest' field with a comma-separated list of their
    top 3 event categories.

    Args:
        user (str): User ID (email or mobile-based username).
    """
    if not user or not frappe.db.exists("User", user):
        return

    top_categories = get_top_user_event_categories(user)
    frappe.db.set_value("User", user, "interest", top_categories)

def get_top_user_event_categories(user: str, limit: int = 3) -> str:
    """
    Returns a comma-separated string of top event categories for the given user,
    based on the number of events per category. Only categories that are set (not null)
    are considered.

    Args:
        user (str): The user ID (usually the user's email or mobile identifier).
        limit (int): The maximum number of top categories to return. Default is 3.

    Returns:
        str: Comma-separated string of category names (e.g., "Health, Education, Environment").
    """
    Events = DocType("Events")

    # Alias for COUNT(*) to use in select and order by
    count_alias = Count("*").as_("count")

    # Step 1: Query top N categories where category is not null for the given user
    category_data = (
        frappe.qb.from_(Events)
        .select(Events.category.as_("category"), count_alias)
        .where((Events.user == user) & Events.category.isnotnull())
        .groupby(Events.category)
        .orderby(count_alias, order=Order.desc)
        .limit(limit)
    ).run(as_dict=True)

    # Step 2: Extract category names from the result
    category_list = [row["category"] for row in category_data]

    # Step 3: Convert the list to a comma-separated string
    return ", ".join(category_list)

def update_ninja_profile(user: str):
    if not user:
        return

    # Aggregate event data
    result = frappe.db.get_all(
        "Events",
        filters={"user": user},
        fields=["sum(hours_invested) as total_hours", "count(*) as total_events"],
        group_by="user"
    )

    if result:
        total_hours = result[0].get("total_hours") or 0
        total_events = result[0].get("total_events") or 0
    else:
        total_hours = 0
        total_events = 0

    if frappe.db.exists("Ninja Profile", user):
        frappe.db.set_value("Ninja Profile", user, {
            "hours_invested": total_hours,
            "contributions": total_events
        }, update_modified=False)


def update_ninja_profile_hook(doc, method=None):
    if doc.user:
        frappe.enqueue("solve_ninja.doc_events.events.update_ninja_profile", queue='default', user=doc.user)

def process_manualupload_events():
    """Batch job to save Events created in the last 25 hours with source=manualupload"""
    from_date = add_to_date(now_datetime(), hours=-25)

    events = frappe.get_all(
        "Events",
        filters={
            "source": "manualupload",
            "creation": [">=", from_date]
        },
        fields=["name"]
    )

    for event in events:
        try:
            doc = frappe.get_doc("Events", event.name)
            doc.save(ignore_permissions=True)  # Triggers Energy Points
        except Exception as e:
            frappe.log_error(f"Failed to save Event: {event.name} - {str(e)}")
