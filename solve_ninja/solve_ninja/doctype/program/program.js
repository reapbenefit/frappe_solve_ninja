// Copyright (c) 2025, ReapBenefit and contributors
// For license information, please see license.txt

frappe.ui.form.on('Program', {
	onload: function(frm) {
		if (frm.doc.program_source) {
			frm.trigger("program_source");
		}
	},
	program_source: function(frm) {
		frm.set_query("program_sub_source", function() {
			return {
				filters: {
					program_source: frm.doc.program_source
				}
			}
		});
	}
});
