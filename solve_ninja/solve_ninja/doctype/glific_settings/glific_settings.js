// Copyright (c) 2025, ReapBenefit and contributors
// For license information, please see license.txt

frappe.ui.form.on('Glific Settings', {
	refresh: function(frm) {
		frm.trigger("setup_connect_btn");
	},
	setup_connect_btn: function(frm) {
    if (frm.doc.phone && frm.doc.password && !frm.is_dirty()) {
        frm.add_custom_button(__('Connect to Glific'), function() {
            frappe.call({
                method: "solve_ninja.solve_ninja.doctype.glific_settings.glific_settings.connect_to_glific",
                callback: function(response) {
                    if (!response.exec) {
						frm.refresh();
                        frappe.show_alert({
                            message: __('Connected to Glific successfully!'),
                            indicator: 'green'
                        });
                    } else {
                        frappe.show_alert({
                            message: __('Failed to connect to Glific. Please check your credentials.'),
                            indicator: 'red'
                        });
                    }
                }
            });
        });
    }	
	}
});
