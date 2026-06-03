// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

frappe.ui.form.on('Glific WA Group', {
	refresh(frm) {
		if (frm.doc.__islocal || !frm.doc.glific_group_id) {
			return;
		}

		frm.add_custom_button(__('Sync from Glific'), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__('Save the document before syncing.'));
				return;
			}
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.pull_glific_wa_group_from_glific',
				args: { doc_name: frm.doc.name, include_members: 1, refresh_from_maytapi: 0 },
				freeze: true,
				freeze_message: __('Pulling from Glific...'),
				callback(r) {
					if (!r.exc) {
						const m = r.message || {};
						const msg =
							m.members != null
								? __('Synced. Members in Glific: {0}', [String(m.members)])
								: __('Synced.');
						frappe.show_alert({ message: msg, indicator: 'green' });
						frm.reload_doc();
					}
				},
			});
		}, 'Sync');

		frm.add_custom_button(__('Metadata Only'), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__('Save the document before syncing.'));
				return;
			}
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.pull_glific_wa_group_from_glific',
				args: { doc_name: frm.doc.name, include_members: 0 },
				freeze: true,
				freeze_message: __('Pulling group metadata...'),
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({
							message: __('Metadata updated.'),
							indicator: 'green',
						});
						frm.reload_doc();
					}
				},
			});
		}, 'Sync');

		frm.add_custom_button(__('Sync Members'), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__('Save the document before syncing.'));
				return;
			}
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.sync_glific_wa_group_members',
				args: { doc_name: frm.doc.name, refresh_from_maytapi: 0, source: 'bigquery' },
				freeze: true,
				freeze_message: __('Pulling members from BigQuery...'),
				callback(r) {
					if (!r.exc) {
						const m = r.message || {};
						frappe.show_alert({
							message: __('Members updated: {0}', [String(m.members || 0)]),
							indicator: 'green',
						});
						frm.reload_doc();
					}
				},
			});
		}, 'Sync');

		frm.add_custom_button(__('Sync Members (Glific API)'), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__('Save the document before syncing.'));
				return;
			}
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.sync_glific_wa_group_members_from_api',
				args: { doc_name: frm.doc.name, refresh_from_maytapi: 0 },
				freeze: true,
				freeze_message: __('Pulling members from Glific API...'),
				callback(r) {
					if (!r.exc) {
						const m = r.message || {};
						frappe.show_alert({
							message: __('Members updated: {0}', [String(m.members || 0)]),
							indicator: 'green',
						});
						frm.reload_doc();
					}
				},
			});
		}, 'Sync');

		frm.add_custom_button(__('Refresh from WhatsApp'), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__('Save the document before syncing.'));
				return;
			}
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_wa_group.glific_wa_group.pull_glific_wa_group_from_glific',
				args: {
					doc_name: frm.doc.name,
					include_members: 1,
					refresh_from_maytapi: 1,
				},
				freeze: true,
				freeze_message: __(
					'Refreshing from WhatsApp via Glific (this may take a few minutes)...',
				),
				callback(r) {
					if (!r.exc) {
						const m = r.message || {};
						const msg =
							m.members != null
								? __('Synced. Members in Glific: {0}', [String(m.members)])
								: __('Synced.');
						frappe.show_alert({ message: msg, indicator: 'green' });
						frm.reload_doc();
					}
				},
			});
		}, 'Sync');
	},
});
