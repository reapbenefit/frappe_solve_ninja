// Custom client script for User form
// Adds View dropdown button with options for Events, Ninja Profile, and User Metadata

frappe.ui.form.on('User', {
    refresh: function(frm) {
        // Only show buttons for existing User records (not new)
        if (!frm.is_new()) {
            // Add Events button (first)
            frm.add_custom_button(__('Events'), function() {
                // Open Events list filtered by this user in a new tab
                const route = `/app/events?user=${encodeURIComponent(frm.doc.name)}`;
                window.open(route, '_blank');
            }, __('View'));

            // Add Ninja Profile button (second)
            frm.add_custom_button(__('Ninja Profile'), function() {
                // Check if Ninja Profile exists for this user
                frappe.db.exists('Ninja Profile', frm.doc.name).then(exists => {
                    if (exists) {
                        // Open Ninja Profile in a new tab
                        const route = `/app/ninja-profile/${encodeURIComponent(frm.doc.name)}`;
                        window.open(route, '_blank');
                    } else {
                        frappe.msgprint({
                            title: __('Not Found'),
                            message: __('Ninja Profile does not exist for this user.'),
                            indicator: 'orange'
                        });
                    }
                });
            }, __('View'));

            // Add User Metadata button (third)
            frm.add_custom_button(__('User Metadata'), function() {
                // Check if User Metadata exists for this user
                frappe.db.exists('User Metadata', frm.doc.name).then(exists => {
                    if (exists) {
                        // Open User Metadata in a new tab
                        const route = `/app/user-metadata/${encodeURIComponent(frm.doc.name)}`;
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
