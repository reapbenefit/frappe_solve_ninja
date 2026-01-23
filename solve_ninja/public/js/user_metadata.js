// Custom client script for User Metadata form
// Adds View dropdown button with options for Events, User, and Ninja Profile

frappe.ui.form.on('User Metadata', {
    refresh: function(frm) {
        // Only show buttons for existing User Metadata records (not new)
        // User Metadata document name is the user ID
        if (!frm.is_new() && frm.doc.name) {
            // Add Events button (first)
            frm.add_custom_button(__('Events'), function() {
                // Open Events list filtered by the user in a new tab
                const route = `/app/events?user=${encodeURIComponent(frm.doc.name)}`;
                window.open(route, '_blank');
            }, __('View'));

            // Add User button (second)
            frm.add_custom_button(__('User'), function() {
                // Open User form in a new tab
                const route = `/app/user/${encodeURIComponent(frm.doc.name)}`;
                window.open(route, '_blank');
            }, __('View'));

            // Add Ninja Profile button (third)
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
        }
    }
});
