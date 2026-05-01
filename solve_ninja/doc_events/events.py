# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
import time
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count
from pypika.terms import Order
from frappe.utils import now_datetime, add_to_date, cint, flt
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
    - Ensures date_of_action is set (defaults to creation time when omitted).
    - Updates last action metadata on the linked Ninja Profile.
    - Creates Event Source Metadata document.
    """
    if not doc.get("date_of_action") and doc.creation:
        dt = frappe.utils.get_datetime(doc.creation)
        doc.db_set("date_of_action", dt, update_modified=False)
        doc.date_of_action = dt

    update_action_detail_in_ninja_profile(doc)
    create_events_metadata(doc)

def update_action_detail_in_ninja_profile(doc):
    """
    Updates the Ninja Profile with the latest action details when an Event is created or modified.

    Uses db.set_value (atomic) instead of get_doc/save to avoid TimestampMismatchError when
    multiple Events for the same user are processed concurrently or alongside update_ninja_profile.
    """
    if not doc.user or not frappe.db.exists("Ninja Profile", doc.user):
        return
    frappe.db.set_value(
        "Ninja Profile",
        doc.user,
        {
            "last_action": doc.name,
            "last_action_date": doc.date_of_action,
            "last_action_type": doc.type,
            "last_action_sub_type": doc.sub_type,
            "last_action_category": doc.category,
        },
        update_modified=False,
    )


def _last_event_name_for_user(user: str):
    """Latest Events.name by creation (same ordering as frappe.get_last_doc)."""
    names = frappe.get_all(
        "Events",
        filters={"user": user},
        order_by="creation desc",
        limit_page_length=1,
        pluck="name",
    )
    return names[0] if names else None

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
        total_hours = flt(result[0].get("total_hours")) or 0
        total_events = cint(result[0].get("total_events")) or 0
    else:
        total_hours = 0
        total_events = 0

    if frappe.db.exists("Ninja Profile", user):
        # Retry logic for database update to handle transient errors
        max_retries = 3
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            try:
                frappe.db.set_value(
                    "Ninja Profile",
                    user,
                    {
                        "hours_invested": total_hours,
                        "contributions": total_events,
                        "last_action": _last_event_name_for_user(user),
                    }
                )
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    # Last attempt failed, log error
                    frappe.log_error(
                        message=f"Failed to update Ninja Profile for user {user} after {max_retries} attempts: {str(e)}",
                        title="Update Ninja Profile Error"
                    )

def _enqueue_update_ninja_profile(user: str):
    if not user:
        return
    frappe.enqueue(
        "solve_ninja.doc_events.events.update_ninja_profile",
        queue="default",
        user=user,
        enqueue_after_commit=True,
    )


def on_trash(doc, method=None):
    records = frappe.get_all("Event Source Metadata", filters={"event_id": doc.name})
    for r in records:
        frappe.delete_doc("Event Source Metadata", r.name, force=True)
    if doc.user:
        _enqueue_update_ninja_profile(doc.user)


def update_ninja_profile_hook(doc, method=None):
    if doc.user:
        _enqueue_update_ninja_profile(doc.user)


def create_events_metadata(doc):
    """
    Creates Event Source Metadata document after Events is created.
    
    Args:
        doc (Document): The Events document that was just created.
    """
    if not doc.user:
        return
    
    try:
        # Create Event Source Metadata document
        events_metadata = frappe.get_doc({
            "doctype": "Event Source Metadata",
            "event_id": doc.name,
        })
        
        # Save the Event Source Metadata document
        events_metadata.flags.ignore_permissions = True
        events_metadata.insert()
        
        frappe.logger().info(f"Created Event Source Metadata for Event: {doc.name}")
        
    except Exception as e:
        frappe.log_error(f"Error creating Event Source Metadata for Event {doc.name}: {str(e)}")


def process_manualupload_events():
    """Batch job to save Events created in the last 25 hours with source=manualupload"""
    from_date = add_to_date(now_datetime(), hours=-25)

    events = frappe.get_all(
        "Events",
        filters={
            "source": ("in", ["manualupload", "snbot"]),
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


import frappe
from frappe.query_builder import DocType, functions as fn

def update_user_headline(user: str):
    """Update a user's headline field based on their top 3 event categories."""
    if not user or not frappe.db.exists('User', user):
        return

    Events = DocType('Events')
    
    # Fetch top 3 event categories for this user
    top_categories = (
        frappe.qb.from_(Events)
        .select(Events.category)
        .where(Events.user == user)
        .where(Events.category.isnotnull())
        .groupby(Events.category)
        .orderby(Count(Events.name), order=frappe.qb.desc)
        .limit(3)
    ).run(pluck=True)

    headline = ', '.join(top_categories) if top_categories else ''
    current_headline = frappe.db.get_value('User', user, 'headline')

    if headline and headline != current_headline:
        frappe.db.set_value('User', user, 'headline', headline)
        frappe.db.commit()


def get_all_event_users(days: int = None):
    """
    Return a list of unique users referenced in Events.
    
    Args:
        days (int, optional): Number of days to look back. If None, considers all events.
    
    Returns:
        list: List of unique user IDs who have events (optionally filtered by days).
    """
    filters = {"user": ("is", "set")}
    
    # Filter by creation date if days parameter is provided
    if days is not None:
        from_date = add_to_date(now_datetime(), days=-days)
        filters["creation"] = [">=", from_date]
    
    users = frappe.get_all("Events", filters=filters, pluck="user")
    return list(set(users))  # remove duplicates safely


def update_all_user_headlines(enqueue: bool = False, days: int = None):
    """
    Update headline for all unique users found in Events.
    
    Args:
        enqueue (bool): If True, enqueue the updates. If False, run synchronously.
        days (int, optional): Number of days to look back for filtering users. If None, considers all events.
    """
    users = get_all_event_users(days=days)
    if not users:
        frappe.logger().info("No users found in Events.")
        return

    if enqueue:
        for user in users:
            frappe.enqueue(update_user_headline, user=user, queue="default")
        frappe.logger().info(f"Enqueued headline update for {len(users)} users.")
    else:
        for user in users:
            try:
                update_user_headline(user)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Failed updating headline for user {user}")
        frappe.logger().info(f"Updated headlines for {len(users)} users.")


def update_all_user_headlines_daily():
    """
    Daily batch job to update headlines for users who have events in the last 2 days.
    This method is called by the scheduler.
    """
    update_all_user_headlines(enqueue=False, days=2)
