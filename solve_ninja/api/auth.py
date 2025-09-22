import frappe
import random
import time
import json
from frappe.utils import now_datetime, add_to_date
from solve_ninja.utils import validate_and_normalize_mobile


@frappe.whitelist(allow_guest=True)
def send_otp(mobile):
	"""
	Send OTP to mobile number for login
	"""
	try:
		# Clean mobile number (remove any non-digit characters)
		mobile = ''.join(filter(str.isdigit, mobile))
		
		if len(mobile) != 10:
			return {
				"success": False,
				"message": "Please enter a valid 10-digit mobile number"
			}
		
		# Check if user exists with this mobile number
		user = frappe.db.get_value("User", {"mobile_no": mobile}, ["name", "enabled"], as_dict=True)
		
		if not user:
			return {
				"success": False,
				"message": "No account found with this mobile number. Please sign up first."
			}
		
		if not user.enabled:
			return {
				"success": False,
				"message": "Your account is disabled. Please contact administrator."
			}
		
		# Generate 6-digit OTP
		otp = str(random.randint(100000, 999999))
		
		# Store OTP in cache with expiry (5 minutes)
		cache_key = f"login_otp:{mobile}"
		frappe.cache.set_value(cache_key, {
			"otp": otp,
			"user": user.name,
			"timestamp": time.time()
		}, expires_in_sec=300)  # 5 minutes
		
		frappe.errprint(f"OTP for {mobile}: {otp}")
		
		# Send OTP via WhatsApp using Glific HSM template
		whatsapp_sent = send_hsm_otp(mobile, otp)
		
		if whatsapp_sent:
			return {
				"success": True,
				"message": "OTP sent successfully to your WhatsApp"
			}
		else:
			return {
				"success": False,
				"message": "Your OTP was not sent to your WhatsApp. Please try again."
			}
		
	except Exception as e:
		return {
			"success": False,
			"message": "Failed to send OTP. Please try again."
		}


@frappe.whitelist(allow_guest=True)
def verify_otp_login(mobile, otp):
	"""
	Verify OTP and login user
	"""
	try:
		# Clean mobile number
		mobile = ''.join(filter(str.isdigit, mobile))
		
		if len(mobile) != 10:
			return {
				"success": False,
				"message": "Invalid mobile number"
			}
		
		if not otp or len(otp) != 6:
			return {
				"success": False,
				"message": "Please enter a valid 6-digit OTP"
			}
		
		# Get OTP from cache
		cache_key = f"login_otp:{mobile}"
		otp_data = frappe.cache.get_value(cache_key)
		
		if not otp_data:
			return {
				"success": False,
				"message": "OTP has expired. Please request a new one."
			}
		
		# Verify OTP
		if otp_data.get("otp") != otp:
			return {
				"success": False,
				"message": "Invalid OTP. Please try again."
			}
		
		# Get user details
		user_name = otp_data.get("user")
		user = frappe.get_doc("User", user_name)
		
		if not user.enabled:
			return {
				"success": False,
				"message": "Your account is disabled. Please contact administrator."
			}
		
		# Clear OTP from cache
		frappe.cache.delete_value(cache_key)
		
		# Login the user
		frappe.local.login_manager.user = user_name
		frappe.local.login_manager.post_login()
		
		# Determine redirect URL
		redirect_to = "/app"
		if user.user_type == "Website User":
			redirect_to = "/user-profile/me"
		
		return {
			"success": True,
			"message": "Login successful",
			"redirect_to": redirect_to,
			"user": user_name
		}
		
	except Exception as e:
		frappe.log_error(f"Error verifying OTP", e)
		return {
			"success": False,
			"message": "Login failed. Please try again."
		}


def send_hsm_otp(mobile, otp):
	"""
	Send OTP via WhatsApp using Glific HSM template
	"""
	# Get Solve Ninja Settings
	solve_ninja_settings = frappe.get_single("Solve Ninja Settings")

	# Check if Glific is enabled and login OTP template ID is configured
	if solve_ninja_settings.channel != "Glific" or not solve_ninja_settings.login_otp_template_id:
		frappe.log_error("Glific not enabled or login OTP template ID not configured")
		return False

	# Get user by mobile number
	user = frappe.db.get_value("User", {"mobile_no": mobile}, ["name"], as_dict=True)
	if not user:
		frappe.throw(f"User not found for mobile {mobile}")
		return False
	
	# Get Glific Settings
	glific_settings = frappe.get_doc("Glific Settings")

	# Get ninja profile to check for existing wa_id
	ninja_profile = frappe.get_doc("Ninja Profile", user.name, for_update=False)
	
	# Get contact ID - same pattern as badge notification
	contact_id = None

	if not ninja_profile.wa_id:
		# Get contact by phone if wa_id not stored
		mobile_no = validate_and_normalize_mobile(mobile)
		response = glific_settings.get_contact_by_phone(mobile_no)
		contact_id = (
			response
			.get('data', {})
			.get('contactByPhone', {})
			.get('contact', {})
			.get('id')
		)
		if contact_id:
			# Store wa_id in ninja profile for future use
			ninja_profile.db_set("wa_id", contact_id, commit=True)
			ninja_profile.reload()
	else:
		# Use existing wa_id
		contact_id = ninja_profile.wa_id

	if not contact_id:
		frappe.log_error(f"Failed to get Glific contact for {mobile}")
		return False
	
	parameters = [f"{otp}"]

	# Send HSM message using the existing method
	response = glific_settings.send_hsm_message(contact_id, solve_ninja_settings.login_otp_template_id, parameters)
	
	# Check if message was sent successfully
	if response and response.get("data") and response["data"].get("sendHsmMessage"):
		message_data = response["data"]["sendHsmMessage"]
		if message_data.get("message") and not message_data.get("errors"):
			frappe.log_error(f"HSM OTP sent successfully to {mobile}")
			return True
		else:
			frappe.log_error(f"HSM send failed", message_data.get('errors'))
			return False
	else:
		frappe.log_error(f"Invalid HSM response", response)
		return False
