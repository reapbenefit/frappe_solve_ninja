frappe.pages['user-summary-update'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'User Summary Update',
		single_column: true
	});
	const $input = $('<input type="text" class="form-control" placeholder="Enter 10 digit mobile number">');
	const $username = $('<input type="text" class="form-control" placeholder="Enter username">');
	const $fields = $('<div class="d-flex flex-column"></div>');
	$input.css('width', '40%');
	$username.css({ width: '40%', marginTop: '10px' });
	const $hint = $('<div class="text-muted mb-2">Enter either mobile number or username to update the ai summary</div>');
    const $btn = $('<button class="btn btn-primary mt-2">Run</button>');

	$fields.append($input, $username);
    $(page.body).append($hint, $fields, $btn);

    $btn.on('click', function() {
        const mobile = String($input.val() || '').trim();
		const username = String($username.val() || '').trim();
		if (mobile && username) {
			frappe.msgprint('Please enter either mobile number or username, not both.');
			return;
		}
		if (!mobile && !username) {
			frappe.msgprint('Please enter a mobile number or username.');
			return;
		}
        if (mobile && !/^\d{10}$/.test(mobile)) {
            frappe.msgprint('Please enter a valid 10 digit mobile number.');
            return;
        }

        frappe.dom.freeze('Updating user summary...');
        frappe.call({
            method: 'solve_ninja.api.user.update_user_summary',
            args: { mobile, username },
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