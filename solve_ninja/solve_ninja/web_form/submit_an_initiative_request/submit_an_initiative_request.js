frappe.ready(function() {
	// Capture referrer URL on page load for redirect after submit/discard
	var referrerUrl = document.referrer;
	// Use referrer if it exists and is different from current page, otherwise fallback to home
	var redirectUrl = referrerUrl && referrerUrl !== window.location.href ? referrerUrl : '/';
	// Phone number validation - similar to login.html
	var phoneField = null;
	
	// Wait for form to be ready
	frappe.web_form.after_load = function() {
		// Get the phone number field
		phoneField = frappe.web_form.get_field('phone_number');
		
		if (phoneField && phoneField.$input) {
			// Auto-format phone number input - only allow digits, max 12 digits
			phoneField.$input.on('input', function() {
				var value = this.value.replace(/[^0-9]/g, '');
				if (value.length > 12) {
					value = value.substring(0, 12);
				}
				this.value = value;
				
				// Remove error styling if valid
				var cleanPhone = value.replace(/[^0-9]/g, '');
				if (cleanPhone.length === 0 || /^[0-9]{10}$/.test(cleanPhone) || /^[0-9]{12}$/.test(cleanPhone)) {
					phoneField.$input.removeClass('input-error');
				}
			});
		}
	};
	
	// Validate phone number before form submission
	frappe.web_form.validate = function() {
		var phone = frappe.web_form.get_value('phone_number');
		
		if (!phone) {
			frappe.msgprint({
				title: 'Phone Number Required',
				message: 'Please enter your phone number',
				indicator: 'red'
			});
			if (phoneField && phoneField.$input) {
				phoneField.$input.addClass('input-error');
			}
			frappe.validated = false;
			return false;
		}
		
		// Validate mobile number format (10 or 12 digits)
		var cleanPhone = phone.replace(/[^0-9]/g, '');
		if (!/^[0-9]{10}$/.test(cleanPhone) && !/^[0-9]{12}$/.test(cleanPhone)) {
			frappe.msgprint({
				title: 'Invalid Phone Number',
				message: 'Please enter a valid 10 or 12-digit mobile number (e.g., 9876543210 or 919876543210)',
				indicator: 'red'
			});
			if (phoneField && phoneField.$input) {
				phoneField.$input.addClass('input-error');
			}
			frappe.validated = false;
			return false;
		}
		
		// Store the cleaned phone number
		frappe.web_form.set_value('phone_number', cleanPhone);
		
		// Remove error styling if valid
		if (phoneField && phoneField.$input) {
			phoneField.$input.removeClass('input-error');
		}
		
		frappe.validated = true;
		return true;
	};
	
	// Redirect to referrer (same source) after form discard
	frappe.web_form.discard_form = function() {
		if (frappe.form_dirty) {
			frappe.confirm(
				'Are you sure you want to discard changes?',
				function() {
					window.location.href = redirectUrl;
				}
			);
		} else {
			window.location.href = redirectUrl;
		}
		return false;
	};
	
	// Redirect to referrer (same source) after successful form submission
	frappe.web_form.after_save = function() {
		// Small delay to show success message before redirect
		setTimeout(function() {
			window.location.href = redirectUrl;
		}, 1000);
	};
})