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

            if (frappe.user.has_role('System Manager')) {
                frm.add_custom_button(__('Merge & Disable Another User Into This'), function() {
                    show_user_merge_dialog(frm);
                }, __('Actions'));
            }
        }
    }
});

function show_user_merge_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Merge & Disable Another User Into This'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'intro',
                options: `<p>${__('This form is the surviving user. Pick the old user whose activity should be merged here. The selected user will be disabled, not deleted.')}</p>`
            },
            {
                fieldtype: 'Link',
                fieldname: 'source_user',
                label: __('Source User (will be disabled)'),
                options: 'User',
                reqd: 1,
                get_query: () => ({
                    filters: {
                        enabled: 1,
                        name: ['!=', frm.doc.name]
                    }
                })
            }
        ],
        primary_action_label: __('Preview Merge'),
        primary_action: function() {
            const source_user = dialog.get_value('source_user');
            if (!source_user) {
                frappe.msgprint(__('Please select a source user.'));
                return;
            }

            frappe.call({
                method: 'solve_ninja.api.user_merge.get_merge_preview',
                args: {
                    source_user: source_user,
                    target_user: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Loading merge preview...'),
                callback: function(r) {
                    if (!r.message) {
                        return;
                    }
                    show_merge_confirm_dialog(frm, r.message, dialog);
                }
            });
        }
    });

    dialog.show();
}

function show_merge_confirm_dialog(frm, preview, source_dialog) {
    const lines = [];
    const source = preview.source_user || {};
    const target = preview.target_user || {};

    lines.push(`<p><strong>${__('Source (will be disabled)')}:</strong> ${frappe.utils.escape_html(source.full_name || source.name)} (${frappe.utils.escape_html(source.username || '')})</p>`);
    lines.push(`<p><strong>${__('Target (surviving)')}:</strong> ${frappe.utils.escape_html(target.full_name || target.name)} (${frappe.utils.escape_html(target.username || '')})</p>`);
    lines.push('<hr>');
    lines.push(`<p><strong>${__('Records to reassign')}</strong></p><ul>`);

    Object.entries(preview.reassignments || {}).forEach(([key, count]) => {
        if (count) {
            lines.push(`<li>${frappe.utils.escape_html(key)}: ${count}</li>`);
        }
    });
    lines.push('</ul>');

    const badgeSummary = preview.badge_summary || {};
    if (badgeSummary.total_source_badges) {
        lines.push(`<p><strong>${__('User Badges')}</strong></p><ul>`);
        lines.push(`<li>${__('Total source badges')}: ${badgeSummary.total_source_badges}</li>`);
        lines.push(`<li>${__('Badges to reassign')}: ${badgeSummary.badges_to_reassign || 0}</li>`);
        lines.push(`<li>${__('Badge counts to sum into existing target badges')}: ${badgeSummary.badges_to_sum || 0}</li>`);
        lines.push('</ul>');
    }

    const statsSummary = preview.user_event_stats_summary || {};
    if (statsSummary.total_source_stats) {
        lines.push(`<p><strong>${__('User Event Stats')}</strong></p><ul>`);
        lines.push(`<li>${__('Stats to reassign')}: ${statsSummary.stats_to_reassign || 0}</li>`);
        lines.push(`<li>${__('Stats to sum into existing target rows')}: ${statsSummary.stats_to_sum || 0}</li>`);
        lines.push('</ul>');
    }

    const ninjaProfile = preview.ninja_profile || {};
    if (ninjaProfile.current || ninjaProfile.projected) {
        lines.push(`<p><strong>${__('Ninja Profile totals')}</strong></p><ul>`);
        lines.push(`<li>${__('Current actions')}: ${(ninjaProfile.current || {}).contributions || 0}</li>`);
        lines.push(`<li>${__('Projected actions after merge')}: ${(ninjaProfile.projected || {}).contributions || 0}</li>`);
        lines.push(`<li>${__('Current hours')}: ${(ninjaProfile.current || {}).hours_invested || 0}</li>`);
        lines.push(`<li>${__('Projected hours after merge')}: ${(ninjaProfile.projected || {}).hours_invested || 0}</li>`);
        lines.push('</ul>');
    }

    const profileFields = preview.profile_fields || {};
    const fillFields = [
        ...(profileFields.user || []).map(field => `User.${field}`),
        ...(profileFields.user_metadata || []).map(field => `User Metadata.${field}`),
        ...(profileFields.ninja_profile || []).map(field => `Ninja Profile.${field}`)
    ];
    if (fillFields.length) {
        lines.push(`<p><strong>${__('Profile fields to fill from source')}</strong></p><ul>`);
        fillFields.forEach(field => lines.push(`<li>${frappe.utils.escape_html(field)}</li>`));
        lines.push('</ul>');
    }

    lines.push(`<p class="text-danger"><strong>${__('Warning')}:</strong> ${__('The source user will be disabled after merge. This cannot be undone automatically.')}</p>`);

    const confirm_dialog = new frappe.ui.Dialog({
        title: __('Confirm User Merge'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'preview_html',
                options: lines.join('')
            }
        ],
        primary_action_label: __('Merge Users'),
        primary_action: function() {
            frappe.call({
                method: 'solve_ninja.api.user_merge.merge_users',
                args: {
                    source_user: source.name,
                    target_user: target.name
                },
                freeze: true,
                freeze_message: __('Merging users...'),
                callback: function(r) {
                    confirm_dialog.hide();
                    if (source_dialog) {
                        source_dialog.hide();
                    }
                    frm.reload_doc();
                    frappe.msgprint({
                        title: __('Merge Complete'),
                        message: r.message.message || __('User merge completed successfully.'),
                        indicator: 'green'
                    });
                }
            });
        }
    });

    confirm_dialog.show();
}
