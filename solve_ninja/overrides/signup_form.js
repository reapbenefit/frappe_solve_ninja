// Shared signup form helpers for /login and /email-login
(function () {
	function resetCitySelect() {
		var $city = $("#signup_city");
		$city
			.empty()
			.append($("<option>").val("").text(__("Select City")))
			.prop("disabled", true);
	}

	function loadCitiesForState(state) {
		var $city = $("#signup_city");
		if (!state) {
			resetCitySelect();
			return;
		}

		$city.prop("disabled", true);
		frappe.call({
			method: "solve_ninja.api.common.get_cities_by_state",
			args: { state: state },
			callback: function (r) {
				var cities = (r && r.message) || [];
				$city.empty().append($("<option>").val("").text(__("Select City")));
				cities.forEach(function (city) {
					$city.append($("<option>").val(city).text(city));
				});
				$city.prop("disabled", cities.length === 0);
			},
			error: function () {
				resetCitySelect();
			},
		});
	}

	function bindStateCityCascade() {
		$(document)
			.off("change.signupCity", "#signup_state")
			.on("change.signupCity", "#signup_state", function () {
				loadCitiesForState($(this).val());
			});
	}

	function bindSignupSubmit() {
		// Replace stock Frappe signup submit (expects email) with our add_user flow
		$(".form-signup").off("submit");
		$(".form-signup .btn-signup").prop("disabled", false);

		$(document)
			.off("submit.signupForm", ".form-signup")
			.on("submit.signupForm", ".form-signup", function (event) {
				event.preventDefault();
				event.stopImmediatePropagation();

				var urlParams = new URLSearchParams(window.location.search);
				var redirectTo = urlParams.get("redirect-to");

				var full_name = ($("#signup_fullname").val() || "").trim();
				var mobile = ($("#signup_mobile").val() || "").trim();
				var state = ($("#signup_state").val() || "").trim();
				var city = ($("#signup_city").val() || "").trim();
				var gender = $("#signup_gender").val();
				var year_of_birth = ($("#signup_yob").val() || "").trim();

				var currentYear = new Date().getFullYear();
				var setStatus =
					window.login && typeof login.set_status === "function"
						? login.set_status.bind(login)
						: function (msg) {
								if (window.frappe && frappe.msgprint) {
									frappe.msgprint(msg);
								}
						  };

				if (!state) {
					setStatus("Please select a state.", "red");
					$("#signup_state").focus();
					return false;
				}
				if (!city) {
					setStatus("Please select a city.", "red");
					$("#signup_city").focus();
					return false;
				}

				if (!/^\d{4}$/.test(year_of_birth) || parseInt(year_of_birth, 10) >= currentYear) {
					setStatus(
						"Year of Birth must be 4 digits and less than " + currentYear + ".",
						"red"
					);
					$("#signup_yob").addClass("input-error").focus();
					return false;
				}
				$("#signup_yob").removeClass("input-error");

				var args = {
					redirect_to: frappe.utils.sanitise_redirect(
						frappe.utils.get_url_arg("redirect-to")
					),
					first_name: full_name,
					mobile: mobile,
					state: state,
					city: city,
					gender: gender,
					year_of_birth: year_of_birth,
					acquisition_source_category: "Website Direct",
				};

				setStatus("Verifying...", "blue");

				frappe
					.call({
						method: "solve_ninja.api.common.add_user",
						args: args,
					})
					.done(function (r) {
						// custom_response body: { message, status, data }
						// frappe.call may pass that object directly or nest under .message
						var payload = r || {};
						if (
							payload.message &&
							typeof payload.message === "object" &&
							payload.message.status
						) {
							payload = payload.message;
						}

						if (payload.status === "error") {
							var errMsg =
								payload.message ||
								"Please connect with ReapBenefit team for help";
							frappe.msgprint("Signup was not successful. " + errMsg);
							setStatus("Signup was not successful. " + errMsg, "red");
							return;
						}

						var successMsg = "Signup successful. Please login with OTP.";
						if (typeof payload.message === "string" && payload.message) {
							// Avoid duplicating "Please login..." if server message is already full
							successMsg =
								payload.message.indexOf("login") >= 0
									? payload.message
									: payload.message + ". Please login with OTP.";
						}

						frappe.show_alert({ message: successMsg, indicator: "green" }, 7);
						setStatus(successMsg, "green");
						frappe.msgprint(successMsg);

						if (redirectTo) {
							window.location.href =
								"/login?redirect-to=" +
								encodeURIComponent(
									frappe.utils.sanitise_redirect(
										frappe.utils.get_url_arg("redirect-to")
									)
								) +
								"#login";
							return;
						}

						// Stay on page and switch to OTP login via hash (no full reload)
						window.location.hash = "login";
						if (mobile) {
							$("#login_mobile").val(mobile);
						}
					})
					.fail(function (xhr) {
						var error = "Please connect with ReapBenefit team for help";
						try {
							var errorMessage = JSON.parse(xhr.responseText);
							if (errorMessage && errorMessage.message) {
								error = errorMessage.message;
							}
						} catch (e) {}
						frappe.msgprint("Signup was not successful. " + error);
						setStatus("Signup was not successful. " + error, "red");
					});

				return false;
			});
	}

	$(function () {
		bindStateCityCascade();
		bindSignupSubmit();
		resetCitySelect();
	});
})();
