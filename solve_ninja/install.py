import frappe

VIEW_NAME = "vw_ninja_listing"

VIEW_SQL = """
CREATE OR REPLACE VIEW `vw_ninja_listing` AS
SELECT
	u.name AS user_id,
	u.full_name,
	u.username,
	u.user_image,
	um.city,
	um.org_id,
	COALESCE(np.contributions, 0) AS contributions,
	COALESCE(np.hours_invested, 0) AS hours_invested,
	np.last_action_date
FROM `tabUser` u
INNER JOIN `tabUser Metadata` um ON um.name = u.name
INNER JOIN `tabNinja Profile` np ON np.name = u.name
WHERE u.enabled = 1
	AND um.publish_status = 'Publish'
"""


def ensure_ninja_listing_view():
	# PostgreSQL cannot replace a view when column order/names change; drop first.
	frappe.db.sql_ddl(f"DROP VIEW IF EXISTS {VIEW_NAME}")
	frappe.db.sql_ddl(VIEW_SQL)
