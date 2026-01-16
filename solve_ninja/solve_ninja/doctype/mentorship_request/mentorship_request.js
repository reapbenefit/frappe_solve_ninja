// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mentorship Request', {
	refresh: function(frm) {
		frm.set_query("assigned_mentor", function() {
			return {
				filters: {
					"is_mentor": 1,
					"mentor_status": "Available"
				}
			}
		});
	}
});
