# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import pretty_date
from frappe import _
from frappe.utils import logger

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

@frappe.whitelist()
def get_user_profile(username=None):
	user = load_user(username)
	disallow_special_users(user.name)

	user_detail = frappe._dict()
	user_detail.current_user = user
	user_detail.current_user.is_verified = True if frappe.db.exists("User Review", {"user": user.name, "status": "Accepted"}) else False
	user_detail.current_user.profile_url = f"{frappe.utils.get_url()}/user-profile/{user.username}"
	user_detail.current_user.user_image = f"{frappe.utils.get_url()}{user.user_image}" if user.user_image else None
	
	user_detail.ninja_profile, user_detail.user_metadata, partner = get_user_related_docs(user.name)
	user_detail.current_user.is_logged_in, user_detail.current_user.is_system_manager = get_user_flags(user)
	user_detail.actions, user_detail.current_user.highlighted_action = get_user_actions(user.name)
	user_detail.skills, user_detail.current_user.partners = get_user_badges(user.name)
	user_detail.reviews = get_user_reviews(user.name)
	user_detail.superheroes = get_user_superheroes(user.name)
	user_detail.skill_assignment_log = get_skill_assignment_log(user.name)
	if partner and user_detail.user_metadata:
		user_detail.current_user.partner = {
			"partner_name": partner.partner_name if partner.partner_name else "",
			"partner_logo": partner.partner_logo if partner.partner_logo else ""
		}
	else:
		user_detail.current_user.partner = None
	return user_detail

def load_user(username):
	user_fields = ["name", "first_name", "last_name", "full_name", "email", "username", "enabled", "user_image", "username", "birth_date", "gender", "banner_image", "mobile_no", "bio", "location"]
	if not username or username == "me":
		username = frappe.session.user

	# Frappe uses email as `User.name`. Support both email and custom `username`.
	if "@" in username and frappe.db.exists("User", username):
		return frappe.db.get_value("User", username, user_fields, as_dict=True)

	if frappe.db.exists("User", {"username": username}):
		return frappe.db.get_value("User", {"username": username}, user_fields, as_dict=True)

	raise frappe.DoesNotExistError(f"User '{username}' not found")


def disallow_special_users(user_name):
	if user_name in ["Administrator", "Guest"]:
		raise frappe.PermissionError(_("User not found or not allowed"))


def get_user_flags(user):
	session_user = frappe.session.user
	is_logged_in = session_user == user.name
	is_system_manager = frappe.db.exists("Has Role", {"parent": session_user, "role": "System Manager"})
	return is_logged_in, bool(is_system_manager)


def get_user_related_docs(user_name):
	ninja_profile = frappe.get_doc("Ninja Profile", user_name) if frappe.db.exists("Ninja Profile", user_name) else None
	user_metadata = frappe.get_doc("User Metadata", user_name) if frappe.db.exists("User Metadata", user_name) else None
	partner = None
	
	if user_metadata:
		user_metadata.summary = user_metadata.summary if user_metadata.summary else ""
		if user_metadata.partner:
			partner = frappe.get_doc("Partner", user_metadata.partner) if frappe.db.exists("Partner", user_metadata.partner) else None
	
	return ninja_profile, user_metadata, partner


def get_user_actions(user_name):
	actions = frappe.db.sql("""
		SELECT e.name AS event_id, e.title, e.type, e.category, e.description, e.location,
		       e.creation, e.highlight, e.verified_by, e.hours_invested,
		       l.district AS location_name
		FROM `tabEvents` e
		LEFT JOIN `tabLocation` l ON l.name = e.location
		WHERE e.user = %s
		ORDER BY e.creation DESC
	""", user_name, as_dict=True)

	highlighted = {'title': '', 'description': ''}
	for action in actions:
		action.review_exists = frappe.db.exists("Events Review", {"events": action.event_id, "status": "Accepted"})
		if action.review_exists:
			action.review = frappe.get_doc("Events Review", action.review_exists)
		if action.highlight == '1':
			highlighted = {'title': action.title, 'description': action.description}

	return actions, highlighted

def get_skill_assignment_log(user):
	skill_assignment_logs = frappe.get_all("Energy Point Log",
		filters={"user": user, "type": "Auto", "reverted": 0, "reference_doctype": "Events"},
		fields=["name", "points", "reason", "reference_doctype","reference_name", "badge", "microskill", "microskill", "creation"])
	
	for skill_assignment_log in skill_assignment_logs:
		if skill_assignment_log.microskill:
			skill_assignment_log.microskill = frappe.db.get_value("Microskill", skill_assignment_log.microskill, ["title", "level", "description"], as_dict=1)
	
	return skill_assignment_logs

def get_user_badges(user_name):
	user_badges = frappe.db.get_all(
		'User badge',
		filters={'user': user_name, 'active': 1},
		fields=['badge', 'badge_count']
	)

	skills = []
	partners = []

	for user_badge in user_badges:
		badge_doc = frappe.get_doc('Badge', user_badge.badge)
		tags = badge_doc.get_tags()

		if 'skill' in tags:
			skills.append({
				"name": badge_doc.title,
				"image": badge_doc.icon,
				"badge_count": user_badge.badge_count
			})
		if 'Partners' in tags:
			partners.append({
				"name": badge_doc.title,
				"image": badge_doc.icon,
				"badge_count": user_badge.badge_count
			})

	return skills, partners


def get_user_reviews(user_name):
    reviews = frappe.get_all(
        "User Review",
        filters={"user": user_name, "status": "Accepted"},
        fields=["review_title", "reviewer_name", "desigantion", "comment", "organisation"]
    )

    # Replace empty/None values with "Not Available"
    for review in reviews:
        for field in review:
            if not review[field]:
                review[field] = "Not Available"
    return reviews


def get_user_superheroes(user_name):
	categories = frappe.db.sql("""
		SELECT e.category AS category, COUNT(*) 
		FROM `tabEvents` e
		WHERE e.user = %s
		GROUP BY 1
		ORDER BY 2 DESC
		LIMIT 3
	""", user_name, as_dict=True)

	superheroes = []
	for cat in categories:
		if cat.category:
			cat_doc = frappe.get_doc('Event Category', cat.category)
			superheroes.append({
				'name': cat_doc.name,
				'image': cat_doc.icon
			})

	return superheroes


@frappe.whitelist()
def update_user_summary(username, summary):
	"""
	Update the summary field in User Metadata for a given user.
	
	Args:
		username (str): Username or email of the user
		summary (str): Summary text to update
	
	Returns:
		dict: Success response with updated summary
	"""
	try:
		# Validate input parameters
		if not username:
			frappe.throw(_("Username is required"))
		
		if not summary:
			frappe.throw(_("Summary is required"))
		
		# Load user to validate existence and permissions
		user = load_user(username)
		
		# Get or create User Metadata
		if frappe.db.exists("User Metadata", user.name):
			user_metadata = frappe.get_doc("User Metadata", user.name)
		else:
			user_metadata = frappe.get_doc({
				"doctype": "User Metadata",
				"user": user.name
			})
		
		# Update summary
		user_metadata.summary = summary
		user_metadata.save(ignore_permissions=True)
		
		return {
			"success": True,
			"message": _("Summary updated successfully"),
			"summary": summary,
			"user": user.name
		}
		
	except frappe.DoesNotExistError:
		frappe.throw(_("User not found"))
	except frappe.PermissionError:
		frappe.throw(_("Permission denied"))
	except Exception as e:
		frappe.log_error(f"Error updating user summary: {str(e)}")
		frappe.throw(_("An error occurred while updating the summary"))
