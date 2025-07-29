# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import pretty_date
from frappe import _


@frappe.whitelist()
def get_user_profile(username=None):
	user = load_user(username)
	disallow_special_users(user.name)

	user_detail = frappe._dict()
	user_detail.current_user = user
	user_detail.current_user.profile_url = f"{frappe.utils.get_url()}/user-profile/{user.username}"
	
	user_detail.ninja_profile, user_detail.user_metadata = get_user_related_docs(user.name)
	user_detail.current_user.is_logged_in, user_detail.current_user.is_system_manager = get_user_flags(user)
	user_detail.actions, user_detail.current_user.highlighted_action = get_user_actions(user.name)
	user_detail.skills, user_detail.current_user.partners = get_user_badges(user.name)
	user_detail.reviews = get_user_reviews(user.name)
	user_detail.superheroes = get_user_superheroes(user.name)
	user_detail.skill_assignment_log = get_skill_assignment_log(user.name)

	return user_detail

def load_user(username):
	user_fields = ["name", "first_name", "last_name", "full_name", "email", "username", "enabled", "user_image", "username", "birth_date", "gender", "banner_image", "mobile_no", "bio", "location"]
	if not username or username == "me":
		username = frappe.session.user

	if "@" in username:
		if not frappe.db.exists("User", username):
			raise frappe.DoesNotExistError(f"User '{username}' not found")
		return frappe.db.get_value("User", username, user_fields, as_dict=True)

	if not frappe.db.exists("User", {"username": username}):
		raise frappe.DoesNotExistError(f"User '{username}' not found")
	return frappe.get_value("User", {"username": username}, "*", as_dict=True)


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
	return ninja_profile, user_metadata


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
		action.creation = pretty_date(action.creation)
		action.review_exists = frappe.db.exists("Events Review", {"events": action.event_id, "status": "Accepted"})
		if action.review_exists:
			action.review = frappe.get_doc("Events Review", action.review_exists)
		if action.highlight == '1':
			highlighted = {'title': action.title, 'description': action.description}

	return actions, highlighted

def get_skill_assignment_log(user):
	return frappe.get_all("Energy Point Log",
		filters={"user": user, "type": "Auto", "reverted": 0, "reference_doctype": "Events"},
		fields=["name", "points", "reason", "reference_doctype","reference_name", "badge", "creation"])
	

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
	return frappe.get_all(
		"User Review",
		filters={"user": user_name, "status": "Accepted"},
		fields=["review_title", "reviewer_name", "desigantion", "comment", "organisation"]
	)


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
