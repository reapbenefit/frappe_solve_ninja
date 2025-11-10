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
		
		# Validate mobile number length (10 or 12 digits)
		if len(mobile) not in [10, 12]:
			return {
				"success": False,
				"message": "Please enter a valid 10 or 12-digit mobile number"
			}
		
		# Check if user exists with this mobile number
		user = frappe.db.get_value("User", {"mobile_no": mobile}, ["name", "enabled"], as_dict=True)
		
		# If 10-digit number and no user found, try with 91 prefix
		if not user and len(mobile) == 10:
			mobile_with_prefix = "91" + mobile
			user = frappe.db.get_value("User", {"mobile_no": mobile_with_prefix}, ["name", "enabled"], as_dict=True)
			if user:
				mobile = mobile_with_prefix  # Use the 12-digit version for consistency
		
		# If 12-digit number and no user found, try without country code (last 10 digits)
		if not user and len(mobile) == 12:
			mobile_without_prefix = mobile[-10:]  # Get last 10 digits
			user = frappe.db.get_value("User", {"mobile_no": mobile_without_prefix}, ["name", "enabled"], as_dict=True)
			if user:
				mobile = mobile_without_prefix  # Use the 10-digit version for consistency
		
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
		frappe.cache().set_value(cache_key, {
			"otp": otp,
			"user": user.name,
			"timestamp": time.time()
		}, expires_in_sec=300)  # 5 minutes
		
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
		frappe.log_error(f"Error sending OTP", e)
		return {
			"success": False,
			"message": "Failed to send OTP. Please try again."
		}


@frappe.whitelist(allow_guest=True)
def verify_otp_login(mobile, otp, redirect_to=None):
	"""
	Verify OTP and login user
	"""
	try:
		# Clean mobile number
		mobile = ''.join(filter(str.isdigit, mobile))
		
		# Validate mobile number length (10 or 12 digits)
		if len(mobile) not in [10, 12]:
			return {
				"success": False,
				"message": "Invalid mobile number"
			}
		
		if not otp or len(otp) != 6:
			return {
				"success": False,
				"message": "Please enter a valid 6-digit OTP"
			}
		
		# Find the correct mobile number format that was used to store OTP
		# Check if user exists with this mobile number
		user = frappe.db.get_value("User", {"mobile_no": mobile}, ["name", "enabled"], as_dict=True)
		
		# If 10-digit number and no user found, try with 91 prefix
		if not user and len(mobile) == 10:
			mobile_with_prefix = "91" + mobile
			user = frappe.db.get_value("User", {"mobile_no": mobile_with_prefix}, ["name", "enabled"], as_dict=True)
			if user:
				mobile = mobile_with_prefix  # Use the 12-digit version for consistency
		
		# If 12-digit number and no user found, try without country code (last 10 digits)
		if not user and len(mobile) == 12:
			mobile_without_prefix = mobile[-10:]  # Get last 10 digits
			user = frappe.db.get_value("User", {"mobile_no": mobile_without_prefix}, ["name", "enabled"], as_dict=True)
			if user:
				mobile = mobile_without_prefix  # Use the 10-digit version for consistency
		
		if not user:
			return {
				"success": False,
				"message": "No account found with this mobile number"
			}
		
		# Get OTP from cache using the normalized mobile number
		cache_key = f"login_otp:{mobile}"
		otp_data = frappe.cache().get_value(cache_key)
		
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
		frappe.cache().delete_value(cache_key)
		
		# Login the user
		frappe.local.login_manager.user = user_name
		frappe.local.login_manager.post_login()
		
		# Determine redirect URL
		default_redirect = "/app"
		if user.user_type == "Website User":
			default_redirect = "/user-profile/me"
		
		# Check for redirect-to parameter
		if redirect_to:
			import urllib.parse
			# Decode the redirect URL
			decoded_redirect = urllib.parse.unquote(redirect_to)
			# Validate that it's a safe redirect (same domain or allowed external domains)
			if decoded_redirect.startswith('/') or decoded_redirect.startswith(frappe.utils.get_url()):
				redirect_to = decoded_redirect
			elif any(allowed_domain in decoded_redirect for allowed_domain in ['solveninja.org', 'vercel.app']):
				redirect_to = decoded_redirect
			else:
				redirect_to = default_redirect
		else:
			redirect_to = default_redirect
		
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
		print(response)
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
		# Handle specific error cases
		if response and response.get("errors"):
			error_messages = [error.get("message", "Unknown error") for error in response["errors"]]
			error_text = "; ".join(error_messages)
			frappe.log_error(f"HSM send failed for {mobile}: {error_text}")
			
			# Check for specific BSP status error and try fallback
			if "invalid BSP status" in error_text.lower():
				frappe.log_error(f"Contact {mobile} has invalid BSP status - trying fallback regular message")
				
				# Try sending a regular message as fallback
				try:
					fallback_message = f"Your OTP for Solve Ninja login is: {otp}. This OTP is valid for 5 minutes."
					fallback_response = glific_settings.send_whatsapp_message(contact_id, fallback_message)
					
					if fallback_response and fallback_response.get("data") and fallback_response["data"].get("sendMessage"):
						fallback_data = fallback_response["data"]["sendMessage"]
						if fallback_data.get("message") and not fallback_data.get("errors"):
							frappe.log_error(f"Fallback OTP sent successfully to {mobile}")
							return True
						else:
							frappe.log_error(f"Fallback message failed", fallback_data.get('errors'))
					else:
						frappe.log_error(f"Fallback message failed", fallback_response)
				except Exception as e:
					frappe.log_error(f"Fallback message error for {mobile}: {str(e)}")
			
			return False
		else:
			frappe.log_error(f"Invalid HSM response for {mobile}", response)
			return False
