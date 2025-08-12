from . import __version__ as app_version

app_name = "solve_ninja"
app_title = "Solve Ninja"
app_publisher = "ReapBenefit"
app_description = "This app is created to support ReapBenefit specific use cases"
app_email = "info@reapbenefit.org"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/solve_ninja/css/solve_ninja.css"
# app_include_js = "/assets/solve_ninja/js/solve_ninja.js"

# include js, css files in header of web template
# web_include_css = "/assets/solve_ninja/css/solve_ninja.css"
web_include_css = "/assets/samaaja/css/leaflet.css"
web_include_js = "/assets/solve_ninja/js/solve_ninja.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "solve_ninja/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
role_home_page = {
	"All": "/user-profile/me"
}

website_route_rules = [
    {"from_route": "/user-profile/<username>", "to_route": "user-profile"},
    {"from_route": "/campaign/<route>", "to_route": "campaign"},
    {"from_route": "/opportunity/<opportunity>", "to_route": "opportunity"}
   # {"from_route": "/application-for-opportunity/new/<opportunity>", "to_route": "application-for-opportunity/new"},
]

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "solve_ninja.utils.jinja_methods",
#	"filters": "solve_ninja.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "solve_ninja.install.before_install"
# after_install = "solve_ninja.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "solve_ninja.uninstall.before_uninstall"
# after_uninstall = "solve_ninja.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "solve_ninja.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"Energy Point Rule": "solve_ninja.overrides.energy_point_rule.CustomEnergyPointRule"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#	"*": {
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
#	"all": [
#		"solve_ninja.tasks.all"
#	],
    "daily_long": [
        "solve_ninja.doc_events.events.process_manualupload_events",
        "solve_ninja.api.leaderboard.update_user_rank"
    ]
#	"hourly": [
#		"solve_ninja.tasks.hourly"
#	],
#	"weekly": [
#		"solve_ninja.tasks.weekly"
#	],
#	"monthly": [
#		"solve_ninja.tasks.monthly"
#	],
}

# Testing
# -------

# before_tests = "solve_ninja.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "solve_ninja.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "solve_ninja.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"solve_ninja.auth.validate"
# ]
doc_events = {
    "Events": {
        "on_update": [
            "solve_ninja.doc_events.events.update_subcategory",
            "solve_ninja.doc_events.events.update_ninja_profile_hook",
        ],
        "after_insert": [
			"solve_ninja.doc_events.events.after_insert",
            "solve_ninja.doc_events.events.update_ninja_profile_hook",
            "solve_ninja.doc_events.energy_point_log.send_badge_notification_after_insert",
		],
        "on_trash": "solve_ninja.doc_events.events.update_ninja_profile_hook",
    },
    "User": {
       "after_insert": "solve_ninja.doc_events.user.after_insert",
        "on_trash": "solve_ninja.doc_events.user.on_trash"
    },
    "Organization":{
        
        "before_save":"solve_ninja.api.common.update_organization_id_case"
    },
    "User Metadata": {
        "validate": "solve_ninja.doc_events.user_metadata.on_save"
    },
    # "Energy Point Log": {
    #     "after_insert": "solve_ninja.doc_events.energy_point_log.handle_energy_point_log"
    # }
}

has_permission = {
    "Events": "solve_ninja.api.common.has_permission"
}

add_action_url = "https://solveninja.vercel.app"