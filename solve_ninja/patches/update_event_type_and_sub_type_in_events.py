import frappe

def execute():
    # Step 1: Event Type → Top-Level Type Mapping
    events_type = frappe.get_all(
        "Event Type",
        filters={"is_group": 0},
        fields=["name", "parent_event_type"]
    )

    event_type_map = {
        row.name: row.parent_event_type or row.name
        for row in events_type
    }

    # Step 2: Fetch All Events with Type
    events = frappe.get_all(
        "Events",
        filters={"type": ("is", "set")},
        fields=["name", "type"]
    )

    batch_size = 500
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        for row in batch:
            current_type = row.type
            top_level_type = event_type_map.get(current_type, current_type)
            frappe.db.set_value("Events", row.name, {
                "sub_type": current_type,
                "type": top_level_type
            })
        frappe.db.commit()
