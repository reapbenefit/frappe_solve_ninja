import frappe

# Default autovacuum_analyze_scale_factor is 0.10, so a 158k-row table is only
# auto-analyzed after ~15.9k changes. After an RDS restore or stats reset that
# is too late: missing stats make vw_ninja_listing pick nested-loop joins.
TABLES = ("tabUser Metadata", "tabUser badge")


def execute():
	if frappe.db.db_type != "postgres":
		return

	for table in TABLES:
		frappe.db.sql_ddl(
			f'ALTER TABLE "{table}" SET (autovacuum_analyze_scale_factor = 0.02)'
		)
