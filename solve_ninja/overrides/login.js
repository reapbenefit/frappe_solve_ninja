// Custom mobile OTP login for Solve Ninja
// Override the default login functionality

window.disable_signup = false;

window.login = {};

login.bind_events = function () {
	console.log("Binding events...");
	
	$(window).on("hashchange", function () {
		login.route();
	});

	// Send OTP button click - using document delegation for better reliability
	$(document).on("click", ".btn-send-otp", function (event) {
		console.log("Send OTP button clicked");
		event.preventDefault();
		
		var mobile = $("#login_mobile").val().trim();
		
		if (!mobile) {
			frappe.msgprint("Mobile number is required");
			return false;
		}
		
		// Validate mobile number format (10 or 12 digits)
		var cleanMobile = mobile.replace(/[^0-9]/g, '');
		if (!/^[0-9]{10}$/.test(cleanMobile) && !/^[0-9]{12}$/.test(cleanMobile)) {
			frappe.msgprint("Please enter a valid 10 or 12-digit mobile number");
			return false;
		}
		
		// Send OTP
		login.send_otp(mobile);
		return false;
	});

	// Verify OTP button click - using document delegation
	$(document).on("click", ".btn-verify-otp", function (event) {
		console.log("Verify OTP button clicked");
		event.preventDefault();
		
		var mobile = $("#login_mobile").val().trim();
		var otp = $("#login_otp").val().trim();
		
		if (!mobile) {
			frappe.msgprint("Mobile number is required");
			return false;
		}
		
		if (!otp) {
			frappe.msgprint("OTP is required");
			return false;
		}
		
		if (!/^[0-9]{6}$/.test(otp)) {
			frappe.msgprint("Please enter a valid 6-digit OTP");
			return false;
		}
		
		login.verify_otp(mobile, otp);
		return false;
	});

	// Handle Enter key press in mobile input
	$("#login_mobile").on("keypress", function (event) {
		if (event.which === 13) { // Enter key
			event.preventDefault();
			$(".btn-send-otp").click();
		}
	});

	// Handle Enter key press in OTP input
	$("#login_otp").on("keypress", function (event) {
		if (event.which === 13) { // Enter key
			event.preventDefault();
			$(".btn-verify-otp").click();
		}
	});

	// Resend OTP functionality - using document delegation
	$(document).on("click", "#resend_otp", function () {
		console.log("Resend OTP button clicked");
		var mobile = $("#login_mobile").val().trim();
		if (mobile) {
			login.send_otp(mobile);
		}
	});

	// Auto-format mobile number input - using document delegation
	$(document).on("input", "#login_mobile", function () {
		var value = this.value.replace(/[^0-9]/g, '');
		if (value.length > 12) {
			value = value.substring(0, 12);
		}
		this.value = value;
	});

	// Auto-format OTP input - using document delegation
	$(document).on("input", "#login_otp", function () {
		var value = this.value.replace(/[^0-9]/g, '');
		if (value.length > 6) {
			value = value.substring(0, 6);
		}
		this.value = value;
	});
};

login.route = function () {
	var route = window.location.hash.slice(1);
	if (!route) route = "login";
	route = route.replaceAll("-", "_");
	login[route]();
};

login.reset_sections = function (hide) {
	if (hide || hide === undefined) {
		$("section.for-login").toggle(false);
		$("section.for-signup").toggle(false);
	}
	$('section:not(.signup-disabled) .indicator').each(function () {
		$(this).removeClass().addClass('indicator').addClass('blue')
			.text($(this).attr('data-text'));
	});
};

login.login = function () {
	login.reset_sections();
	$(".for-login").toggle(true);
	login.reset_button_states();
	$("#login_mobile").focus();
};

login.signup = function () {
	login.reset_sections();
	$(".for-signup").toggle(true);
	$("#signup_fullname").focus();
};

// Send OTP to mobile number
login.send_otp = function (mobile) {
	login.set_status("Sending OTP...", 'blue');
	
	return frappe.call({
		type: "POST",
		method: "solve_ninja.api.auth.send_otp",
		args: {
			mobile: mobile
		},
		callback: function (response) {
			if (response.message && response.message.success) {
				login.set_status("OTP sent successfully", 'green');
				login.show_otp_section();
				login.start_countdown();
			} else {
				login.set_status(response.message.message || "Failed to send OTP", 'red');
			}
		},
		error: function (xhr, data) {
			login.set_status("Failed to send OTP", 'red');
		}
	});
};

// Verify OTP and login
login.verify_otp = function (mobile, otp) {
	login.set_status("Verifying OTP...", 'blue');
	
	return frappe.call({
		type: "POST",
		method: "solve_ninja.api.auth.verify_otp_login",
		args: {
			mobile: mobile,
			otp: otp
		},
		callback: function (response) {
			if (response.message && response.message.success) {
				login.set_status("Login successful", 'green');
				// Redirect to home page or dashboard
				setTimeout(function () {
					window.location.href = response.message.redirect_to || "/app";
				}, 1000);
			} else {
				login.set_status(response.message.message || "Invalid OTP", 'red');
				$("#login_otp").val("").focus();
			}
		},
		error: function (xhr, data) {
			login.set_status("Verification failed", 'red');
		}
	});
};

// Show OTP input section
login.show_otp_section = function () {
	$(".otp-section").show();
	$(".btn-send-otp").hide();
	$(".btn-verify-otp").show();
	$("#login_otp").focus();
};

// Reset button states to initial state
login.reset_button_states = function () {
	$(".btn-send-otp").show().text("Send OTP");
	$(".btn-verify-otp").hide().text("Verify");
	$(".otp-section").hide();
	$("#login_otp").val("");
	$("#resend_otp").prop('disabled', true);
	$("#countdown").text("60");
};

// Start countdown for resend OTP
login.start_countdown = function () {
	var countdown = 60;
	var countdownElement = $("#countdown");
	var resendButton = $("#resend_otp");
	
	resendButton.prop('disabled', true);
	
	var timer = setInterval(function () {
		countdown--;
		countdownElement.text(countdown);
		
		if (countdown <= 0) {
			clearInterval(timer);
			resendButton.prop('disabled', false);
			countdownElement.text("0");
		}
	}, 1000);
};

login.set_status = function (message, color) {
	// Create or update status message area
	var statusArea = $('.status-message');
	if (statusArea.length === 0) {
		statusArea = $('<div class="status-message text-center mt-2"></div>');
		$('.page-card-actions').after(statusArea);
	}
	
	statusArea.text(message);
	
	// Set color based on status
	if (color == "red") {
		statusArea.removeClass('text-success text-info').addClass('text-danger');
		$('section:visible .page-card-body').addClass("invalid");
	} else if (color == "green") {
		statusArea.removeClass('text-danger text-info').addClass('text-success');
		$('section:visible .page-card-body').removeClass("invalid");
	} else if (color == "blue") {
		statusArea.removeClass('text-danger text-success').addClass('text-info');
		$('section:visible .page-card-body').removeClass("invalid");
	} else {
		statusArea.removeClass('text-danger text-success text-info');
		$('section:visible .page-card-body').removeClass("invalid");
	}
	
	// Auto-hide success messages after 3 seconds
	if (color == "green") {
		setTimeout(function() {
			statusArea.fadeOut();
		}, 3000);
	} else {
		statusArea.show();
	}
};

login.set_invalid = function (message) {
	$(".login-content.page-card").addClass('invalid-login');
	setTimeout(() => {
		$(".login-content.page-card").removeClass('invalid-login');
	}, 500);
	login.set_status(message, 'red');
};

frappe.ready(function () {
	console.log("Mobile login script loaded");
	
	// Debug: Check if elements exist
	console.log("Send OTP button exists:", $(".btn-send-otp").length);
	console.log("Mobile input exists:", $("#login_mobile").length);
	
	login.bind_events();

	if (!window.location.hash) {
		window.location.hash = "#login";
	} else {
		$(window).trigger("hashchange");
	}

	$(".form-signup").removeClass("hide");
	$(document).trigger('login_rendered');
	
	console.log("Mobile login initialization complete");
});
