import frappe


def execute():
	"""
	Delete Events Metadata doctype and all its records from the database.
	This patch:
	1. Deletes all records from the Events Metadata table
	2. Deletes the doctype itself
	3. Drops the table from the database
	"""
	doctype_name = "Events Metadata"
	table_name = f"tab{doctype_name}"
	
	# Check if doctype exists
	if not frappe.db.exists("DocType", doctype_name):
		frappe.log_error(f"DocType '{doctype_name}' does not exist. Skipping deletion.")
		return
	
	# Step 1: Delete all records from Events Metadata table
	if frappe.db.has_table(table_name):
		try:
			# Get count of records before deletion
			count = frappe.db.count(table_name)
			frappe.log_error(f"Deleting {count} records from '{table_name}' table")
			
			# Delete all records
			frappe.db.delete(table_name)
			frappe.db.commit()
			
			frappe.log_error(f"Successfully deleted {count} records from '{table_name}' table")
		except Exception as e:
			frappe.log_error(f"Error deleting records from '{table_name}': {str(e)}")
			raise
	
	# Step 2: Delete the doctype
	try:
		frappe.delete_doc(
			"DocType",
			doctype_name,
			ignore_permissions=True,
			force=True,
			ignore_on_trash=True
		)
		frappe.db.commit()
		frappe.log_error(f"Successfully deleted DocType '{doctype_name}'")
	except Exception as e:
		frappe.log_error(f"Error deleting DocType '{doctype_name}': {str(e)}")
		raise
	
	# Step 3: Drop the table if it still exists
	if frappe.db.has_table(table_name):
		try:
			frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{table_name}`")
			frappe.db.commit()
			frappe.log_error(f"Successfully dropped table '{table_name}'")
		except Exception as e:
			frappe.log_error(f"Error dropping table '{table_name}': {str(e)}")
			# Don't raise here as the doctype is already deleted
			# The table can be dropped manually if needed
	
	# Clear cache
	frappe.clear_cache()

