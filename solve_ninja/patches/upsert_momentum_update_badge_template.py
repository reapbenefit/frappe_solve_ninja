import frappe

TEMPLATE_ID = "877458"
TEMPLATE_NAME = "Momentum Update"
PARAMETERS_JSON = """[
  "{{ user.full_name }}",
  "{{ event.title }}",
  "{{ action_hours }}",
  "{{ skills }}",
  "{{ microskills }}",
  "{{ total_hours }}"
]"""


def execute():
	"""Upsert Momentum Update Badge Template and set it as default."""
	if frappe.db.exists("Badge Template", TEMPLATE_ID):
		frappe.db.set_value(
			"Badge Template",
			TEMPLATE_ID,
			{
				"template_name": TEMPLATE_NAME,
				"channel": "Glific",
				"active": 1,
				"parameters_json": PARAMETERS_JSON,
			},
			update_modified=True,
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Badge Template",
				"template_id": TEMPLATE_ID,
				"template_name": TEMPLATE_NAME,
				"channel": "Glific",
				"active": 1,
				"parameters_json": PARAMETERS_JSON,
			}
		).insert(ignore_permissions=True)

	frappe.db.set_single_value("Solve Ninja Settings", "default_badge_template", TEMPLATE_ID)
