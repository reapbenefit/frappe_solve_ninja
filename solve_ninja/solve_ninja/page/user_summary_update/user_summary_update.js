frappe.pages['user-summary-update'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'User Summary Update',
		single_column: true
	});
	const $input = $('<input type="text" class="form-control" placeholder="Enter 10 digit mobile number">');
    const $btn = $('<button class="btn btn-primary mt-2">Run</button>');

    $(page.body).append($input, $btn);

    $btn.on('click', function() {
        const mobile = String($input.val() || '').trim();
        if (!/^\d{10}$/.test(mobile)) {
            frappe.msgprint('Please enter a valid 10 digit mobile number.');
            return;
        }

        frappe.dom.freeze('Updating user summary...');
        frappe.call({
            method: 'solve_ninja.api.user.update_user_summary',
            args: { mobile },
            callback: function(r) {
                frappe.show_alert('Success!');
            },
            error: function() {
                frappe.msgprint('Failed to update user summary.');
            },
            always: function() {
                frappe.dom.unfreeze();
            }
        });
    });
}