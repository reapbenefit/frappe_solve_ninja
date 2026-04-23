import frappe


def execute():
    """Composite index for queries filtering by user and ordering by creation."""
    frappe.db.add_index(
        "Events",
        ["user", "creation"],
        index_name="events_user_creation_idx",
    )
