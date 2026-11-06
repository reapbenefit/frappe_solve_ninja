// Shared signup form helpers for /login and /email-login
// Follows Frappe login.js patterns: button text status, freeze, delayed redirect
(function () {
	var SIGNUP_BTN_LABEL = __("Sign up");
	var SUCCESS_REDIRECT_MS = 2500;

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

	function getSignupButton($form) {
		return $form.find(".btn-signup").first();
	}

	function setSignupStatus(message, color) {
		// Prefer Frappe login.set_status (puts text on visible primary button)
		if (window.login && typeof login.set_status === "function") {
			login.set_status(message, color);
			return;
		}
		var $btn = $("section:visible .btn-signup").first();
		if ($btn.length) {
			$btn.text(message);
		}
		if (color === "red") {
			$("section:visible .page-card-body").addClass("invalid");
		}
	}

	function resetSignupButton($btn) {
		$btn.prop("disabled", false).text(SIGNUP_BTN_LABEL);
	}

	function showSignupError($btn, error) {
		var errMsg = error || __("Please connect with ReapBenefit team for help");
		// Frappe login puts status on the button; keep label short and re-enable for retry
		setSignupStatus(__("Sign up"), "red");
		resetSignupButton($btn);
		$("section:visible .page-card-body").addClass("invalid");
		frappe.show_alert({ message: errMsg, indicator: "red" }, 7);
		frappe.msgprint({
			title: __("Signup failed"),
			message: errMsg,
			indicator: "red",
		});
	}

	function parseAddUserPayload(r) {
		var payload = r || {};
		if (payload.message && typeof payload.message === "object" && payload.message.status) {
			payload = payload.message;
		}
		return payload;
	}

	function getCheckinCode() {
		// Website check-in link: ?code=<unique_id>, or redirect-to=/checkin?code=<unique_id>
		var code = frappe.utils.get_url_arg("code");
		if (code) {
			return code;
		}
		var redirectTo = frappe.utils.get_url_arg("redirect-to");
		if (!redirectTo) {
			return "";
		}
		try {
			var url = new URL(redirectTo, window.location.origin);
			return url.pathname === "/checkin" ? url.searchParams.get("code") || "" : "";
		} catch (e) {
			return "";
		}
	}

	function buildLoginUrl() {
		var params = new URLSearchParams();
		var code = frappe.utils.get_url_arg("code");
		var redirectTo = frappe.utils.sanitise_redirect(frappe.utils.get_url_arg("redirect-to"));
		if (code) {
			params.set("code", code);
		}
		if (redirectTo) {
			params.set("redirect-to", redirectTo);
		}
		var query = params.toString();
		return "/login" + (query ? "?" + query : "") + "#login";
	}

	function redirectAfterSuccess() {
		window.location.href = buildLoginUrl();
	}

	function isExistingUserError(message) {
		return /already exists/i.test(message || "");
	}

	function switchToLogin(mobile) {
		frappe.show_alert(
			{
				message: __("You already have an account. Please log in with OTP."),
				indicator: "blue",
			},
			7
		);
		window.location.hash = "#login";
		$("#login_mobile").val(mobile);
	}

	function enableSignupButton() {
		// Stock Frappe disables .btn-signup until email+name exist; our form has no email
		$(".form-signup .btn-signup").prop("disabled", false).text(SIGNUP_BTN_LABEL);
		$("section.for-signup .page-card-body").removeClass("invalid");
	}

	function patchSignupRoute() {
		if (!window.login || typeof login.signup !== "function") {
			return;
		}
		if (login._solve_ninja_signup_patched) {
			return;
		}
		login._solve_ninja_signup_patched = true;
		var originalSignup = login.signup;
		login.signup = function () {
			originalSignup.apply(this, arguments);
			enableSignupButton();
		};
	}

	function bindSignupSubmit() {
		// Replace stock Frappe signup submit (expects email) with our add_user flow
		$(".form-signup").off("submit");
		enableSignupButton();
		patchSignupRoute();

		// Stop stock handler that keeps the button disabled without signup_email
		$("#signup_fullname, #signup_email").off("input");

		$(document)
			.off("submit.signupForm", ".form-signup")
			.on("submit.signupForm", ".form-signup", function (event) {
				event.preventDefault();
				event.stopImmediatePropagation();

				var $form = $(this);
				var $btn = getSignupButton($form);
				if ($btn.prop("disabled")) {
					return false;
				}

				var full_name = ($("#signup_fullname").val() || "").trim();
				var mobile = ($("#signup_mobile").val() || "").trim();
				var state = ($("#signup_state").val() || "").trim();
				var city = ($("#signup_city").val() || "").trim();
				var gender = $("#signup_gender").val();
				var year_of_birth = ($("#signup_yob").val() || "").trim();

				var currentYear = new Date().getFullYear();

				if (!full_name) {
					showSignupError($btn, __("Full name is required."));
					$("#signup_fullname").focus();
					return false;
				}
				if (!mobile) {
					showSignupError($btn, __("Mobile number is required."));
					$("#signup_mobile").focus();
					return false;
				}
				if (!state) {
					showSignupError($btn, __("Please select a state."));
					$("#signup_state").focus();
					return false;
				}
				if (!city) {
					showSignupError($btn, __("Please select a city."));
					$("#signup_city").focus();
					return false;
				}
				if (!gender) {
					showSignupError($btn, __("Please select a gender."));
					$("#signup_gender").focus();
					return false;
				}
				if (!/^\d{4}$/.test(year_of_birth) || parseInt(year_of_birth, 10) >= currentYear) {
					$("#signup_yob").addClass("input-error").focus();
					showSignupError(
						$btn,
						__("Year of Birth must be 4 digits and less than {0}.", [currentYear])
					);
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
				var code = getCheckinCode();
				if (code) {
					args.code = code;
				}

				// Frappe login pattern: disable button + status on button + freeze
				$form.find(".page-card-body").removeClass("invalid");
				$btn.prop("disabled", true);
				setSignupStatus(__("Verifying..."), "blue");

				frappe.call({
					method: "solve_ninja.api.common.add_user",
					args: args,
					freeze: true,
					freeze_message: __("Creating your account..."),
					callback: function (r) {
						var payload = parseAddUserPayload(r);

						if (payload.status === "error") {
							if (isExistingUserError(payload.message)) {
								resetSignupButton($btn);
								switchToLogin(mobile);
								return;
							}
							showSignupError(
								$btn,
								payload.message || __("Please connect with ReapBenefit team for help")
							);
							return;
						}

						var successMsg = __(
							"Signup successful. Please login with OTP."
						);
						if (typeof payload.message === "string" && payload.message) {
							successMsg =
								payload.message.toLowerCase().indexOf("login") >= 0
									? payload.message
									: payload.message.replace(/\.\s*$/, "") +
									  ". " +
									  __("Please login with OTP.");
						}

						setSignupStatus(__("Success"), "green");
						frappe.show_alert({ message: successMsg, indicator: "green" }, 7);
						frappe.msgprint({
							title: __("Success"),
							message: successMsg,
							indicator: "green",
						});

						// Delay redirect so the success message is visible
						setTimeout(function () {
							redirectAfterSuccess();
						}, SUCCESS_REDIRECT_MS);
					},
					error: function (xhr) {
						var error = __("Please connect with ReapBenefit team for help");
						try {
							var body =
								(xhr && xhr.responseJSON) ||
								(xhr && xhr.responseText ? JSON.parse(xhr.responseText) : null);
							if (body && body.message) {
								error = body.message;
							}
						} catch (e) {}
						if (isExistingUserError(error)) {
							resetSignupButton($btn);
							switchToLogin(mobile);
							return;
						}
						showSignupError($btn, error);
					},
				});

				return false;
			});
	}

	$(function () {
		bindStateCityCascade();
		bindSignupSubmit();
		resetCitySelect();
		if ((window.location.hash || "").slice(1) === "signup") {
			enableSignupButton();
		}
	});
})();
