// Copyright (c) 2025, ReapBenefit and contributors
// For license information, please see license.txt

frappe.ui.form.on('Ninja Profile', {
	onload: function (frm) {
		frm.set_query("last_action_type", function (doc) {
			return {
				filters: {
					is_group: 1,
				},
			};
		});
	},
	refresh: function(frm) {
		frm.set_query("last_action_sub_type", function (doc) {
			return {
				filters: {
					is_group: 0,
					parent_event_type: doc.last_action_type
				},
			};
		});
	}
});
