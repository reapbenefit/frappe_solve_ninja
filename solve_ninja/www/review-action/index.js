frappe.ready(function() {
	console.log(frappe.ui.FieldGroup)
	$("#web-form").submit(function(){
		let form_data = get_form_data()

		frappe.call({
			method: "solve_ninja.api.events.submit_event_review",
			args: {
				action: form_data,
			},
			freeze: true,
			freeze_message: __("Submitting Review..."),
			callback: function(r) {
				if(r.message) {
					console.log(r)
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
	
	// this.get_form_data = function() {
	// 	let reviewer_name = $("input[data-fieldname='reviewer_name']").val()
	// 	let desigantion = $("input[data-fieldname='desigantion']").val()
	// 	let organisation = $("input[data-fieldname='organisation']").val()
	// 	let email = $("input[data-fieldname='email']").val()
	// 	let status = $("select[data-fieldname='status']").val()
	// 	let comment = $("textarea[data-fieldname='comment']").html()
	// 	let data = {
	// 		"reviewer_name": reviewer_name,
	// 		"desigantion": desigantion,
	// 		"organisation": organisation,
	// 		"email": email,
	// 		"status": status,
	// 		"comment": comment,
	// 	}
	// 	console.log(data)
	// }
});

var get_form_data = function() {
	let reviewer_name = $("input[data-fieldname='reviewer_name']").val()
	let desigantion = $("input[data-fieldname='desigantion']").val()
	let organisation = $("input[data-fieldname='organisation']").val()
	let email = $("input[data-fieldname='email']").val()
	let status = $("select[data-fieldname='status']").val()
	let comment = $("textarea[data-fieldname='comment']").val()
	let data = {
		"review": event_review,
		"reviewer_name": reviewer_name,
		"desigantion": desigantion,
		"organisation": organisation,
		"email": email,
		"status": status,
		"comment": comment,
	}
	return data
	// console.log(data)
}