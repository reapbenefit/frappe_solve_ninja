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

		// Add View dropdown buttons (only for existing records)
		if (!frm.is_new() && frm.doc.user) {
			// Add Events button (first)
			frm.add_custom_button(__('Events'), function() {
				// Open Events list filtered by the linked user in a new tab
				const route = `/app/events?user=${encodeURIComponent(frm.doc.user)}`;
				window.open(route, '_blank');
			}, __('View'));

			// Add User button (second)
			frm.add_custom_button(__('User'), function() {
				// Open User form in a new tab
				const route = `/app/user/${encodeURIComponent(frm.doc.user)}`;
				window.open(route, '_blank');
			}, __('View'));

			// Add User Metadata button (third)
			frm.add_custom_button(__('User Metadata'), function() {
				// Check if User Metadata exists for this user
				frappe.db.exists('User Metadata', frm.doc.user).then(exists => {
					if (exists) {
						// Open User Metadata in a new tab
						const route = `/app/user-metadata/${encodeURIComponent(frm.doc.user)}`;
						window.open(route, '_blank');
					} else {
						frappe.msgprint({
							title: __('Not Found'),
							message: __('User Metadata does not exist for this user.'),
							indicator: 'orange'
						});
					}
				});
			}, __('View'));
		}
	}
});
