frappe.ready(function() {
	let form_wrapper = $("#web-form");
	$("#web-form").submit(function(){
		let form_data = get_form_data()
		console.log(form_data)
		frappe.call({
			method: "solve_ninja.api.user.submit_user_review",
			args: {
				review: form_data,
			},
			freeze: true,
			freeze_message: __("Submitting Review..."),
			callback: function(r) {
				if(r.message) {
					$(".web-form-container").addClass("hide")
					$(".success-page").removeClass("hide")
					setTimeout(function() {
						window.close();
					}, 5000);
				}
			}
		});
		return false
	})
});

var get_form_data = function() {
	let reviewer_name = $("input[data-fieldname='reviewer_name']").val()
	let desigantion = $("input[data-fieldname='desigantion']").val()
	let organisation = $("input[data-fieldname='organisation']").val()
	let email = $("input[data-fieldname='email']").val()
	let status = $("select[data-fieldname='status']").val()
	let comment = $("textarea[data-fieldname='comment']").val()
	let data = {
		"review": user_review,
		"reviewer_name": reviewer_name,
		"organisation": organisation,
		"desigantion": desigantion,
		"email": email,
		"status": status,
		"comment": comment,
	}
	return data
	// console.log(data)
}