import frappe

def execute():
    # find users with at least one event (Postgres quoting)
    rows = frappe.db.sql("""
        SELECT 
            "user"              AS user,
            SUM(hours_invested) AS total_hours,
            COUNT(*)            AS total_events
        FROM "tabEvents"
        GROUP BY "user"
        HAVING COUNT(*) >= 1
    """, as_dict=1)

    for r in rows:
        user = r.user
        total_hours = r.total_hours or 0
        total_events = r.total_events or 0

        if frappe.db.exists("Ninja Profile", user):
            frappe.db.set_value(
                "Ninja Profile", user,
                {
                    "hours_invested": total_hours,
                    "contributions":  total_events
                }
            )