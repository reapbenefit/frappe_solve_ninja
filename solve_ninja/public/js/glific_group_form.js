// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

(function () {
	const Cf = solve_ninja.glific_cohort_filters;

	function normalize_glific_filters_from_dialog(raw) {
		return Cf.normalize_glific_filters_from_dialog(raw);
	}

	function filters_have_any_criteria_glific(f) {
		return Cf.filters_have_any_criteria_glific(f);
	}

	frappe.ui.form.on('Glific Group', {
		refresh(frm) {
			const isMonthlyCohort =
				(frm.doc.cohort_type === 'Monthly Cohort' ||
					frm.doc.cohort_type === 'Automated Cohort') &&
				frm.doc.automated_cohort_bucket;
			const isMonthlyCohortType =
				frm.doc.cohort_type === 'Monthly Cohort' ||
				frm.doc.cohort_type === 'Automated Cohort';

			if (isMonthlyCohort) {
				const period = [frm.doc.cohort_month, frm.doc.cohort_year].filter(Boolean).join(' ');
				frm.set_intro(
					__(
						'Monthly Cohort: {0} ({1}). Glific Sync: {2}. Use Manage Cohort → Create Monthly Collections to re-run.',
						[
							frm.doc.automated_cohort_bucket,
							period || '—',
							frm.doc.glific_sync_status || __('Not started'),
						],
					),
				);
			} else if (isMonthlyCohortType) {
				frm.set_intro(
					__(
						'Use Manage Cohort → Monthly Cohorts to generate monthly cohort records.',
					),
				);
			} else {
				frm.set_intro('');
			}

			if (!frm.doc.__islocal) {
				frm.add_custom_button(
					__('Open in Manage Cohort'),
					() => {
						frappe.set_route('manage-cohort', { cohort: frm.doc.name });
					},
					__('Manage Cohort'),
				);
			}

			if (!frm.doc.__islocal && frm.doc.glific_group_id) {
				frm.add_custom_button(__('Sync Members to Glific'), () => {
					if (frm.is_dirty()) {
						frappe.msgprint(__('Save the document before syncing.'));
						return;
					}
					frappe.call({
						method:
							'solve_ninja.solve_ninja.doctype.glific_group.glific_group.sync_members_to_glific',
						args: { doc_name: frm.doc.name },
						freeze: true,
						freeze_message: __('Syncing members...'),
						callback(r) {
							if (!r.exc) {
								const payload = r.message || {};
								let alert_msg;
								if (payload.queued) {
									alert_msg =
										payload.message ||
										__(
											'Sync queued in background. Refresh later to see status.',
										);
								} else {
									alert_msg = payload.added
										? __('Synced {0} member(s).', [String(payload.added)])
										: payload.message || __('Done.');
								}
								frappe.show_alert({
									message: alert_msg,
									indicator: 'green',
								});
								frm.reload_doc();
							}
						},
					});
				});
			}

			if (!frm.doc.__islocal) {
				frm.add_custom_button(__('Add members from filters'), () => {
					show_member_filter_modal(frm);
				});
			}

			if (
				!frm.doc.__islocal &&
				frm.doc.audience_mode === 'Filtered' &&
				!(frm.doc.glific_group_id || '').trim()
			) {
				frm.add_custom_button(
					__('Create Glific collection'),
					() => {
						if (frm.is_dirty()) {
							frappe.msgprint(__('Save before creating collection.'));
							return;
						}
						frappe.confirm(
							__(
								'Create an empty Glific collection for this cohort? Contacts are added later via Sync Members.',
							),
							() => {
								frappe.call({
									method:
										'solve_ninja.api.v1.glific_audience.create_filtered_glific_collection',
									args: {
										doc_name: frm.doc.name,
									},
									freeze: true,
									callback(r) {
										if (!r.exc) {
											const payload = r.message || {};
											frappe.show_alert({
												message:
													payload.message ||
													__('Glific collection created.'),
												indicator: 'green',
											});
											frm.reload_doc();
										}
									},
								});
							},
						);
					},
					__('Filtered'),
				);
			}
		},
	});

	function show_member_filter_modal(frm) {
		if (frm.is_new()) {
			frappe.msgprint(__('Save the Glific Group document before adding members from filters.'));
			return;
		}

		const state = { filters: {}, users: [], start: 0, selectedRows: {} };

		const d = new frappe.ui.Dialog({
			title: __('Filter users'),
			size: 'large',
			fields: [
				{
					fieldtype: 'Check',
					fieldname: 'filter_wa_community',
					label: __('Restrict to WhatsApp communities'),
					description: __(
						'Uses Glific memberships from selected Glific WA Group records.',
					),
					default: frm.doc.filter_wa_community ? 1 : 0,
				},
				{
					fieldtype: 'Table MultiSelect',
					fieldname: 'filter_glific_wa_groups',
					options: 'Glific Group Filter WA Group',
					label: __('Glific WA groups'),
					description: __('Members of any selected group are included (union).'),
					default: (frm.doc.filter_glific_wa_groups || []).map((r) => ({
						glific_wa_group: r.glific_wa_group,
					})),
					depends_on: 'eval:doc.filter_wa_community',
				},
				{
					fieldtype: 'Table MultiSelect',
					fieldname: 'filter_cities',
					options: 'Glific Group Filter City',
					label: __('Cities'),
					description: __('Profile city matches any selected city.'),
					default: (frm.doc.filter_cities || []).map((r) => ({
						samaaja_city: r.samaaja_city,
					})),
				},
				{
					fieldtype: 'Link',
					fieldname: 'filter_gender',
					options: 'Gender',
					label: __('Gender'),
					default: frm.doc.filter_gender,
				},
				{ fieldtype: 'Column Break', fieldname: 'col_filters_right' },
				{
					fieldtype: 'Int',
					fieldname: 'filter_contributions_min',
					label: __('Number of actions (min)'),
					description: __('Uses Ninja Profile "contributions" (count).'),
					default: frm.doc.filter_contributions_min,
				},
				{
					fieldtype: 'Int',
					fieldname: 'filter_contributions_max',
					label: __('Number of actions (max)'),
					description: __('Uses Ninja Profile "contributions" (count).'),
					default: frm.doc.filter_contributions_max,
				},
				{
					fieldtype: 'DateRange',
					fieldname: 'filter_last_action_date_range',
					label: __('Last Action Date'),
					default: Cf.date_range_from_stored(
						frm.doc.filter_last_action_date_from,
						frm.doc.filter_last_action_date_to,
					),
				},
				{
					fieldtype: 'DateRange',
					fieldname: 'filter_last_active_date_range',
					label: __('Last Active Date'),
					default: Cf.date_range_from_stored(
						frm.doc.filter_last_active_date_from,
						frm.doc.filter_last_active_date_to,
					),
				},
				{
					fieldtype: 'Data',
					fieldname: 'filter_acquisition_source_unique_id',
					label: __('Acquisition Source Unique ID'),
					default: frm.doc.filter_acquisition_source_unique_id,
				},
				{
					fieldtype: 'Link',
					fieldname: 'filter_user_organization',
					options: 'User Organization',
					label: __('User Organization'),
					default: frm.doc.filter_user_organization,
				},
				{ fieldtype: 'Section Break', fieldname: 'sec_results' },
				{
					fieldtype: 'HTML',
					fieldname: 'results_area',
					label: __('Results'),
				},
			],
			primary_action_label: __('Apply filters'),
			primary_action(values) {
				const raw = values || this.get_values();
				if (!raw) return;
				const v = normalize_glific_filters_from_dialog(raw);
				if (!filters_have_any_criteria_glific(v)) {
					frappe.msgprint(
						__(
							'Select at least one filter. For WhatsApp communities, enable the checkbox and pick at least one Glific WA group.',
						),
					);
					return;
				}
				state.filters = v;
				state.start = 0;
				load_users_page(d, frm, true);
			},
		});

		d.show();

		function load_users_page(dialog, form, replace) {
			if (!state.filters || !filters_have_any_criteria_glific(state.filters)) {
				frappe.msgprint(
					__(
						'Click Apply filters (select at least one filter). For WhatsApp communities, select at least one Glific WA group.',
					),
				);
				return;
			}
			frappe.call({
				method: 'solve_ninja.api.v1.glific_audience.search_users_for_glific_group',
				args: {
					filters_json: JSON.stringify(state.filters),
					start: state.start,
					page_length: 50,
				},
				freeze: true,
				freeze_message: __('Searching users...'),
				callback(r) {
					if (r.exc) return;
					const msg = r.message || {};
					state.users = msg.users || [];
					const total = msg.total_count || 0;
					render_table(dialog, form, total, replace);
				},
			});
		}

		function render_table(dialog, form, total, replace) {
			const rows = state.users || [];
			let html = `<p class="text-muted">${__('Total matching')}: <b>${total}</b></p>`;
			html += '<div style="max-height:260px;overflow:auto;border:1px solid var(--border-color);">';
			html += '<table class="table table-bordered"><thead><tr>';
			html += `<th></th><th>${__('User')}</th><th>${__('Name')}</th><th>${__('Mobile')}</th><th>${__(
				'Number of actions',
			)}</th></tr></thead><tbody>`;
			rows.forEach((u) => {
				const checked = state.selectedRows[u.user] ? 'checked' : '';
				html += `<tr data-user="${frappe.utils.escape_html(u.user)}">
				<td><input type="checkbox" class="gg-modal-pick" data-user="${frappe.utils.escape_html(
					u.user,
				)}" ${checked}></td>
				<td>${frappe.utils.escape_html(u.user)}</td>
				<td>${frappe.utils.escape_html(u.full_name || '')}</td>
				<td>${frappe.utils.escape_html(u.mobile_no || '')}</td>
				<td>${u.contributions != null ? u.contributions : ''}</td>
			</tr>`;
			});
			html += '</tbody></table></div>';
			html += `<button class="btn btn-xs btn-default" type="button" data-action="more">${__(
				'Load next page',
			)}</button> `;
			html += `<button class="btn btn-xs btn-default" type="button" data-action="add">${__(
				'Add selected to members',
			)}</button>`;

			const $container = dialog.fields_dict.results_area.$wrapper;
			$container.off('.ggmodal');
			$container.html(html);
			$container.on('change.ggmodal', '.gg-modal-pick', function () {
				const uid = $(this).data('user');
				if ($(this).is(':checked')) {
					const hit = rows.find((x) => x.user === uid);
					if (hit) state.selectedRows[uid] = hit;
				} else {
					delete state.selectedRows[uid];
				}
			});
			$container.on('click.ggmodal', '[data-action="more"]', () => {
				state.start += 50;
				load_users_page(d, frm, false);
			});
			$container.on('click.ggmodal', '[data-action="add"]', () => {
				add_selected_to_members(frm, state);
				d.hide();
			});
		}

		function add_selected_to_members(form, st) {
			const existingUsers = new Set(
				(form.doc.members || []).map((r) => r.user).filter(Boolean),
			);
			const existingMobile = new Set(
				(form.doc.members || [])
					.map((r) => (r.mobile_no || '').trim())
					.filter(Boolean),
			);
			let added = 0;
			Object.keys(st.selectedRows).forEach((userId) => {
				if (existingUsers.has(userId)) return;
				const row = st.selectedRows[userId];
				const mob = (row && row.mobile_no) || '';
				if (mob && existingMobile.has(mob.trim())) return;
				const child = frm.add_child('members', {
					user: userId,
					status: 'Pending',
				});
				if (row) {
					child.mobile_no = row.mobile_no;
					child.contact_name = row.full_name;
				}
				if (mob) existingMobile.add(mob.trim());
				existingUsers.add(userId);
				added += 1;
			});
			form.refresh_field('members');
			frappe.show_alert({
				message: __('Added {0} row(s). Save the document.', [String(added)]),
				indicator: 'green',
			});
		}
	}
})();
