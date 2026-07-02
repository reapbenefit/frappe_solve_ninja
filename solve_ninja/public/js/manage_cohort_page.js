// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

(function () {
	const PAGE = 'manage-cohort';

	const AUTOMATED_COHORT_BUCKETS = [
		'Dormants',
		'High Potentials',
		'Potentials',
		'Engaged Actors',
		'Change Champions',
		'Passive Actors',
		'Others Active',
	];

	/** Display order in modal (two columns, matches design). */
	const AUTOMATED_BUCKET_COLUMNS = [
		['Dormants', 'Potentials', 'Change Champions', 'Others Active'],
		['High Potentials', 'Engaged Actors', 'Passive Actors'],
	];

	const COHORT_MONTH_OPTIONS =
		'January\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember';

	const MONTHLY_COHORT_TYPES = ['Monthly Cohort', 'Automated Cohort'];

	function isMonthlyCohortType(cohortType) {
		return MONTHLY_COHORT_TYPES.includes(cohortType);
	}

	function isMonthlyCohortDoc(doc) {
		return Boolean(doc && isMonthlyCohortType(doc.cohort_type) && doc.automated_cohort_bucket);
	}

	function cohortTypeDisplayLabel(cohortType) {
		if (isMonthlyCohortType(cohortType)) return __('Monthly Cohort');
		return cohortType || '—';
	}

	frappe.pages[PAGE].on_page_load = function (wrapper) {
		const Cf = solve_ninja.glific_cohort_filters;

		frappe.ui.make_app_page({
			parent: wrapper,
			single_column: true,
		});

		const page = wrapper.page;
		page.set_title(__('Manage Cohort'));

		const $titleMeta = $('<div class="manage-cohort-title-meta">').append(
			$('<span class="badge badge-warning mc-dirty-indicator" style="display:none">').text(
				`${__('Unsaved Changes')}`,
			),
		);
		const $titleRow = page.get_title_area().find('> div > div.flex').first();
		$titleRow.addClass('manage-cohort-title-meta-row');
		$titleMeta.appendTo($titleRow);

		const ctx = {
			doc: null,
			docName: null,
			filtersFg: null,
			searchStart: 0,
			totalCount: 0,
			rowUsers: [],
			selectedRows: {},
			mcDatatable: null,
			mcMembersDatatable: null,
			membersSorted: [],
			_sidebarSummaries: [],
		};

		const $root = $(`
			<div class="manage-cohort-root layout-main-section">
				<style>
				.manage-cohort-root{width:100%;max-width:100%;box-sizing:border-box}
				.manage-cohort-body{display:flex;gap:18px;align-items:flex-start;min-height:360px;width:100%}
				.manage-cohort-body .manage-cohort-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:14px;}
				.mc-cohort-sidebar{flex:0 0 280px;max-width:300px;min-width:252px;display:flex;flex-direction:column;gap:10px;}
				.mc-cohort-cards{display:flex;flex-direction:column;gap:10px;max-height:calc(100vh - 168px);overflow-y:auto;padding-right:2px;}
				.mc-cohort-card{border:1px solid var(--border-color);padding:11px;border-radius:var(--border-radius);cursor:pointer;background:var(--fg-color);text-align:left;}
				.mc-cohort-card:hover{border-color:var(--text-color)}
				.mc-cohort-card.active{border-color:var(--primary)}
				.mc-cohort-card .mc-cc-title{font-weight:600;font-size:13px;line-height:1.3;margin:0 0 6px;color:var(--text-color);}
				.mc-cohort-card .mc-cc-meta{font-size:11px;line-height:1.45;color:var(--text-muted);}
				.mc-inner-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start;}
				@media (max-width: 992px){
					.manage-cohort-body{flex-direction:column}
					.mc-cohort-sidebar{max-width:none;width:100%;flex:none;}
					.mc-inner-grid{grid-template-columns:1fr;}
				}
				.mc-applied-filters-readonly{border:1px solid var(--border-color);padding:12px;border-radius:var(--border-radius);background:var(--fg-color);font-size:12px;line-height:1.45;}
				.manage-cohort-filters{border:1px solid var(--border-color);padding:12px;border-radius:var(--border-radius);background:var(--fg-color)}
				.manage-cohort-sticky-apply{padding-top:10px;margin-top:6px}
				.mc-existing-members-panel{border:1px solid var(--border-color);padding:10px;border-radius:var(--border-radius);background:var(--fg-color);}
				.mc-results-panel{border:1px solid var(--border-color);padding:10px;border-radius:var(--border-radius);background:var(--fg-color);}
				.mc-members-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:6px;line-height:1.25;font-size:12px;}
				.mc-members-toolbar .mc-members-title{font-weight:600;color:var(--text-muted);}
				.mc-results-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin-bottom:6px;line-height:1.25;font-size:12px;}
				.mc-results-toolbar .mc-results-title{font-weight:600;color:var(--text-muted);}
				.mc-members-datatable-wrap,.mc-datatable-wrap{border:1px solid var(--border-color);border-radius:var(--border-radius);overflow:hidden;background:var(--fg-color);}
				.mc-members-datatable-wrap .dt-scrollable{max-height:44vh!important;}
				.mc-datatable-wrap .dt-scrollable{max-height:44vh!important;}
				.manage-cohort-root .datatable{font-size:12px;}
				.manage-cohort-root .dt-cell,.manage-cohort-root .dt-cell__content{font-size:12px!important;}
				.page-head .manage-cohort-title-meta-row{flex-wrap:wrap;align-items:center;gap:4px}
				.page-head .manage-cohort-title-meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin-left:12px;min-width:0;flex:1 1 auto}
				@media (max-width: 576px){.page-head .manage-cohort-title-meta{margin-left:8px;gap:6px}}
				.mc-filter-dl dt{font-weight:600;margin-top:.35rem;float:left;clear:left;width:14rem;}
				.mc-filter-dl dd{margin-left:14.5rem;min-height:1.25em;margin-bottom:.15rem;}
				.mc-filter-dl dt:first-child{margin-top:0;}
				.mc-sidebar-heading{font-weight:600;margin-bottom:4px;}
				.mc-auto-buckets-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 20px;margin:12px 0;}
				.mc-auto-bucket{display:block;margin:0;font-size:13px;font-weight:400;}
				.mc-auto-bucket input{margin-right:6px;}
				</style>
				<div class="manage-cohort-empty alert alert-info hide"></div>
				<div class="manage-cohort-body">
					<aside class="mc-cohort-sidebar">
						<div class="small text-muted mc-sidebar-heading">${__('Cohorts')}</div>
						<div class="mc-cohort-cards"></div>
					</aside>
					<div class="manage-cohort-main hide">
						<div class="mc-applied-filters-readonly hide"></div>
						<div class="manage-cohort-filters">
							<label class="small text-muted">${__('Audience Filters')}</label>
							<div class="mc-filter-fields"></div>
							<div class="manage-cohort-sticky-apply">
								<button type="button" class="btn btn-primary btn-sm btn-block mc-apply">${__('Apply Filters')}</button>
								<p class="small text-muted mb-0 mt-2">${__('Saves filters and refreshes results. Add members from Results, then use Glific: Create Collection, Sync Members.')}</p>
							</div>
						</div>
						<div class="mc-inner-grid">
							<div class="mc-existing-members-panel">
								<div class="mc-members-toolbar">
									<span class="mc-members-title">${__('Existing Members')}</span>
									<span class="text-muted" aria-hidden="true">·</span>
									<span class="mc-existing-count text-muted"></span>
									<button type="button" class="btn btn-default btn-xs mc-remove-selected hide">${__('Remove Selected')}</button>
								</div>
								<div class="mc-members-datatable-wrap"></div>
							</div>
							<div class="mc-results-panel">
								<div class="mc-results-toolbar">
									<span class="mc-results-title">${__('Results')}</span>
									<span class="mc-member-count text-muted"></span>
									<span class="text-muted" aria-hidden="true">·</span>
									<span class="mc-range text-muted"></span>
									<button type="button" class="btn btn-default btn-xs mc-add-selected hide">${__('Add Selected')}</button>
									<button type="button" class="btn btn-default btn-xs mc-add-all-matching hide">${__('Add All Matching')}</button>
								</div>
								<div class="mc-datatable-wrap"></div>
								<div class="mc-pager mt-2" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:6px">
									<button type="button" class="btn btn-default btn-xs mc-prev" disabled>${__('Prev')}</button>
									<button type="button" class="btn btn-default btn-xs mc-next">${__('Next Page')}</button>
									<button type="button" class="btn btn-default btn-xs mc-select-visible">${__('Select Visible')}</button>
									<button type="button" class="btn btn-default btn-xs mc-clear">${__('Clear Selection')}</button>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		`).appendTo(page.main);

		function routePick() {
			const rn = frappe.route_options && frappe.route_options.cohort;
			if (!rn) return;
			delete frappe.route_options.cohort;
			frappe.after_ajax(() => loadDoc(rn));
		}

		frappe.pages[PAGE]._solve_ninja_route_pick = routePick;
		const $dirty = $titleMeta.find('.mc-dirty-indicator');
		const $emptyState = $root.find('.manage-cohort-empty');
		const filterParent = $root.find('.mc-filter-fields')[0];
		const $mainCol = $root.find('.manage-cohort-main');
		const $readonlyFilters = $root.find('.mc-applied-filters-readonly');
		const $filtersBlock = $root.find('.manage-cohort-filters');

		function buildAutomatedBucketCheckboxHtml() {
			const cols = AUTOMATED_BUCKET_COLUMNS.map((colBuckets) => {
				const items = colBuckets
					.map((bucket) => {
						const id = `mc-bucket-${bucket.replace(/\s+/g, '-')}`;
						return `<label class="mc-auto-bucket"><input type="checkbox" class="mc-auto-bucket-cb" value="${frappe.utils.escape_html(
							bucket,
						)}" id="${id}" checked> ${frappe.utils.escape_html(bucket)}</label>`;
					})
					.join('');
				return `<div>${items}</div>`;
			});
			return `<div class="mc-auto-buckets-grid">${cols.join('')}</div>`;
		}

		function getSelectedAutomatedBucketsFromDialog(dlg) {
			const out = [];
			dlg.$wrapper.find('.mc-auto-bucket-cb:checked').each(function () {
				out.push($(this).val());
			});
			return out;
		}

		function buildMonthlyPeriodReadonlyHtml(cohortMonth, cohortYear) {
			return `<p class="mb-2 mt-2"><strong>${__('Month')}:</strong> ${frappe.utils.escape_html(
				cohortMonth,
			)} &nbsp; <strong>${__('Year')}:</strong> ${frappe.utils.escape_html(String(cohortYear))}</p>`;
		}

		function showAutomatedMonthlyModal() {
			frappe.call({
				method: 'solve_ninja.api.v1.automated_cohort.get_monthly_cohort_period',
				freeze: true,
				freeze_message: __('Loading…'),
				callback(r) {
					if (r.exc) return;
					const period = r.message || {};
					const cohortMonth = period.cohort_month;
					const cohortYear = period.cohort_year;
					if (!cohortMonth || cohortYear == null) {
						frappe.msgprint(__('Could not load the current month and year.'));
						return;
					}

					ctx._monthlyCohortPeriod = {
						cohort_month: cohortMonth,
						cohort_year: cohortYear,
					};

					const dlg = new frappe.ui.Dialog({
						title: __('Monthly Cohorts'),
						size: 'large',
						fields: [
							{
								fieldtype: 'HTML',
								fieldname: 'automated_intro',
								options: `<p class="text-muted mb-0">${__(
									'Classify all users and create Glific collections for the current month. Glific sync runs in the background.',
								)}</p>${buildMonthlyPeriodReadonlyHtml(
									cohortMonth,
									cohortYear,
								)}${buildAutomatedBucketCheckboxHtml()}`,
							},
						],
						primary_action_label: __('Create Monthly Collections'),
						primary_action() {
							const buckets = getSelectedAutomatedBucketsFromDialog(dlg);
							runCreateMonthlyCollections(false, {
								buckets,
								cohort_month: cohortMonth,
								cohort_year: cohortYear,
								onComplete: () => dlg.hide(),
							});
						},
					});
					ctx._automatedMonthlyDlg = dlg;
					dlg.show();
				},
			});
		}

		function showMonthlySummaryDialog(payload) {
			const p = payload || {};
			const counts = p.counts_by_bucket || {};
			let html = `<p>${__('Total Users Processed')}: <b>${p.total_users_processed || 0}</b></p>`;
			html += `<p class="text-muted">${__(
				'Glific sync is running in the background for each cohort record created or updated.',
			)}</p>`;
			html += '<table class="table table-bordered table-condensed"><thead><tr>';
			html += `<th>${__('Bucket')}</th><th>${__('Count')}</th></tr></thead><tbody>`;
			Object.keys(counts).forEach((k) => {
				html += `<tr><td>${frappe.utils.escape_html(k)}</td><td>${counts[k]}</td></tr>`;
			});
			html += '</tbody></table>';

			if ((p.created || []).length) {
				html += `<h6>${__('Created')}</h6><ul>`;
				p.created.forEach((row) => {
					html += `<li>${frappe.utils.escape_html(row.group_name || row.doc_name)} — ${__(
						'{0} members',
						[String(row.member_count)],
					)} (${frappe.utils.escape_html(row.glific_sync_status || 'Queued')})</li>`;
				});
				html += '</ul>';
			}
			if ((p.updated || []).length) {
				html += `<h6>${__('Updated')}</h6><ul>`;
				p.updated.forEach((row) => {
					html += `<li>${frappe.utils.escape_html(row.group_name || row.doc_name)} — ${__(
						'{0} members',
						[String(row.member_count)],
					)} (${frappe.utils.escape_html(row.glific_sync_status || 'Queued')})</li>`;
				});
				html += '</ul>';
			}
			if ((p.skipped_duplicates || []).length) {
				html += `<h6 class="text-warning">${__('Skipped (Already Exist)')}</h6><ul>`;
				p.skipped_duplicates.forEach((row) => {
					html += `<li>${frappe.utils.escape_html(row.group_name)}</li>`;
				});
				html += '</ul>';
			}
			if ((p.errors || []).length) {
				html += `<h6 class="text-danger">${__('Errors')}</h6><ul>`;
				p.errors.forEach((row) => {
					html += `<li>${frappe.utils.escape_html(row.bucket)}: ${frappe.utils.escape_html(
						row.message,
					)}</li>`;
				});
				html += '</ul>';
			}

			frappe.msgprint({
				title: __('Monthly Collections'),
				message: html,
				indicator: (p.errors || []).length ? 'orange' : 'green',
			});
		}

		function runCreateMonthlyCollections(confirmOverwrite, opts) {
			opts = opts || {};
			const buckets = opts.buckets || [];
			if (!buckets.length) {
				frappe.msgprint(__('Select At Least One Monthly Cohort.'));
				return;
			}
			const cohort_month = opts.cohort_month;
			const cohort_year = parseInt(String(opts.cohort_year ?? ''), 10);
			if (!cohort_month || !Number.isFinite(cohort_year)) {
				frappe.msgprint(
					__(
						'Current month and year are missing. Close and reopen Monthly Cohorts.',
					),
				);
				return;
			}

			const runOpts = {
				buckets,
				cohort_month,
				cohort_year,
				onComplete: opts.onComplete,
			};

			frappe.call({
				method: 'solve_ninja.api.v1.automated_cohort.create_monthly_automated_collections',
				args: {
					cohort_buckets: buckets,
					cohort_month,
					cohort_year,
					confirm_overwrite: confirmOverwrite ? 1 : 0,
				},
				freeze: true,
				freeze_message: __('Classifying Users and Creating Cohort Records…'),
				callback(r) {
					if (r.exc) return;
					const payload = r.message || {};
					const skipped = payload.skipped_duplicates || [];
					if (!confirmOverwrite && skipped.length) {
						const names = skipped.map((s) => s.group_name).join('<br>');
						frappe.confirm(
							__(
								'These collections already exist for this month:<br><br>{0}<br><br>Overwrite members and re-queue Glific sync?',
								[names],
							),
							() =>
								runCreateMonthlyCollections(true, {
									...runOpts,
									onComplete: opts.onComplete,
								}),
						);
						return;
					}
					if (typeof opts.onComplete === 'function') opts.onComplete();
					showMonthlySummaryDialog(payload);
					refreshCohortCards();
				},
			});
		}

		function renderAutomatedDocReadonly(doc) {
			const bucket = frappe.utils.escape_html(doc.automated_cohort_bucket || '—');
			const period = `${frappe.utils.escape_html(doc.cohort_month || '—')} ${frappe.utils.escape_html(
				String(doc.cohort_year || '—'),
			)}`;
			const syncSt = frappe.utils.escape_html(doc.glific_sync_status || '—');
			const typeLabel = frappe.utils.escape_html(cohortTypeDisplayLabel(doc.cohort_type));
			$readonlyFilters
				.removeClass('hide')
				.html(
					`<dl class="mc-filter-dl">
<dt>${__('Cohort Type')}</dt><dd>${typeLabel}</dd>
<dt>${__('Bucket')}</dt><dd>${bucket}</dd>
<dt>${__('Period')}</dt><dd>${period}</dd>
<dt>${__('Glific Sync')}</dt><dd>${syncSt}</dd>
</dl>`,
				);
			$filtersBlock.addClass('hide');
		}

		function filterFieldDefs() {
			return [
				{
					fieldtype: 'Check',
					fieldname: 'filter_wa_community',
					label: __('Restrict To WhatsApp Communities'),
					description: __(
						'Uses Glific memberships from selected Glific WA Group records.',
					),
					default: 0,
				},
				{
					fieldtype: 'Table MultiSelect',
					fieldname: 'filter_glific_wa_groups',
					options: 'Glific Group Filter WA Group',
					label: __('Glific WA Groups'),
					description: __('Members of any selected group are included (union).'),
					depends_on: 'eval:doc.filter_wa_community',
				},
				{
					fieldtype: 'Table MultiSelect',
					fieldname: 'filter_cities',
					options: 'Glific Group Filter City',
					label: __('Cities'),
				},
				{
					fieldtype: 'Link',
					fieldname: 'filter_gender',
					options: 'Gender',
					label: __('Gender'),
				},
				{ fieldtype: 'Column Break', fieldname: 'mc_col_r' },
				{
					fieldtype: 'Int',
					fieldname: 'filter_contributions_min',
					label: __('Number Of Actions (Min)'),
				},
				{
					fieldtype: 'Int',
					fieldname: 'filter_contributions_max',
					label: __('Number Of Actions (Max)'),
				},
				{
					fieldtype: 'DateRange',
					fieldname: 'filter_last_action_date_range',
					label: __('Last Action Date'),
					description: __('Uses Ninja Profile "last_action_date".'),
				},
				{
					fieldtype: 'DateRange',
					fieldname: 'filter_last_active_date_range',
					label: __('Last Active Date'),
					description: __('Uses Ninja Profile "last_active_date_bot".'),
				},
				{
					fieldtype: 'Data',
					fieldname: 'filter_acquisition_source_unique_id',
					label: __('Acquisition Source Unique ID'),
				},
				{
					fieldtype: 'Link',
					fieldname: 'filter_user_organization',
					options: 'User Organization',
					label: __('User Organization'),
				},
			];
		}

		/** Locked when Filtered cohort and every saved member row is synced to Glific. */
		function filtersLocked(doc) {
			if (!doc || doc.audience_mode !== 'Filtered') return false;
			const m = doc.members || [];
			if (m.length === 0) return false;
			return m.every((row) => row.status === 'Synced');
		}

		function memberRowDedupeKey(row) {
			if (row.name) return `n:${String(row.name)}`;
			const u = (row.user || '').trim();
			const ix = String(row.idx ?? '');
			return `k:${ix}:${u}`;
		}

		function appliedFiltersMarkup(doc) {
			if (!doc || doc.audience_mode !== 'Filtered') return '';
			const chips = [];
			if (doc.filter_wa_community) {
				const gwa = (doc.filter_glific_wa_groups || [])
					.map((r) =>
						frappe.utils.escape_html(String(r.glific_wa_group || '').trim()),
					)
					.filter(Boolean)
					.join(', ');
				const waDd = gwa
					? `${__('Restricted')}: ${gwa}`
					: __('Restricted (No Groups Selected)');
				chips.push(`<dt>${__('WhatsApp Communities')}</dt><dd>${waDd}</dd>`);
			} else chips.push(`<dt>${__('WhatsApp Communities')}</dt><dd>${__('Not Restricted')}</dd>`);

			const cities = (doc.filter_cities || [])
				.map((r) =>
					frappe.utils.escape_html(String(r.samaaja_city || '').trim()),
				)
				.filter(Boolean)
				.join(', ');
			chips.push(`<dt>${__('Cities')}</dt><dd>${cities || '—'}</dd>`);

			chips.push(
				`<dt>${__('Gender')}</dt><dd>${frappe.utils.escape_html(doc.filter_gender || '—')}</dd>`,
			);

			let contrib = __('Any');
			if (
				doc.filter_contributions_min != null ||
				doc.filter_contributions_max != null
			) {
				contrib =
					frappe.utils.escape_html(
						String(doc.filter_contributions_min ?? '—'),
					) +
					` – ` +
					frappe.utils.escape_html(String(doc.filter_contributions_max ?? '—'));
			}
			chips.push(`<dt>${__('Number Of Actions')}</dt><dd>${contrib}</dd>`);

			const actionRange = Cf.format_date_range_display(
				doc.filter_last_action_date_from,
				doc.filter_last_action_date_to,
			);
			chips.push(
				`<dt>${__('Last Action Date')}</dt><dd>${frappe.utils.escape_html(actionRange || '—')}</dd>`,
			);
			const activeRange = Cf.format_date_range_display(
				doc.filter_last_active_date_from,
				doc.filter_last_active_date_to,
			);
			chips.push(
				`<dt>${__('Last Active Date')}</dt><dd>${frappe.utils.escape_html(activeRange || '—')}</dd>`,
			);

			chips.push(
				`<dt>${__('Acquisition Source Unique ID')}</dt><dd>${frappe.utils.escape_html(doc.filter_acquisition_source_unique_id || '—')}</dd>`,
			);
			chips.push(
				`<dt>${__('User Organization')}</dt><dd>${frappe.utils.escape_html(doc.filter_user_organization || '—')}</dd>`,
			);

			return `<div class="text-muted mb-2"><strong>${__(
				'Applied Filters',
			)}</strong>${filtersLocked(doc) ? ` · <span class="text-warning">${__('Read Only (All Members Synced To Glific)')}</span>` : ''}</div><dl class="mc-filter-dl" style="margin:0;overflow:hidden">${chips.join('')}</dl>`;
		}

		function updateFiltersChrome() {
			const doc = ctx.doc;
			$dirty.hide();

			$readonlyFilters.empty();

			if (!doc) {
				$filtersBlock.addClass('hide');
				$readonlyFilters.addClass('hide');
				syncGlificToolbar();
				return;
			}

			const $ro = $readonlyFilters;

			if (doc.audience_mode !== 'Filtered') {
				$filtersBlock.addClass('hide');
				$ro.addClass('hide').empty();
				syncGlificToolbar();
				return;
			}

			if (filtersLocked(doc)) {
				$filtersBlock.addClass('hide');
				$ro.removeClass('hide').html(appliedFiltersMarkup(doc));
			} else {
				$ro.addClass('hide');
				$filtersBlock.removeClass('hide');
			}

			syncGlificToolbar();
		}

		function getFgValuesOrNull() {
			if (!ctx.filtersFg) return null;
			try {
				return ctx.filtersFg.get_values(true, true);
			} catch (e) {
				return null;
			}
		}

		function getNormalizedFiltersForSearch() {
			if (!ctx.doc) return null;
			if (ctx.doc.audience_mode !== 'Filtered') return null;
			const raw =
				filtersLocked(ctx.doc)
					? docToFgValues(ctx.doc)
					: getFgValuesOrNull();
			if (!raw) return null;
			const v = Cf.normalize_glific_filters_from_dialog(raw);
			return Cf.filters_have_any_criteria_glific(v) ? v : null;
		}

		frappe.model.with_doctype('Glific Group', () => {
			ctx.filtersFg = new frappe.ui.FieldGroup({
				fields: filterFieldDefs(),
				body: filterParent,
			});
			ctx.filtersFg.make();
			if (ctx.filtersFg.wrapper) {
				ctx.filtersFg.wrapper.on(
					'change',
					'input, select, textarea',
					() => {
						if (
							ctx.doc &&
							(filtersLocked(ctx.doc) || ctx.doc.audience_mode !== 'Filtered')
						)
							return;
						$dirty.show();
					},
				);
			}

			setupPageToolbarMenusOnce();
			bindControls();
			resetPageUi();
			refreshCohortCards(routePick);

			syncNewCohortPrimary();
		});

		function refreshMemberCount() {
			const el = $root.find('.mc-member-count');
			if (!ctx.doc) {
				el.text('');
				return;
			}
			const n = (ctx.doc.members || []).length;
			el.text(__('Members In Cohort: {0}', [String(n)]));
		}

		function syncNewCohortPrimary() {
			if (ctx.docName) {
				page.clear_primary_action();
				page.clear_secondary_action();
			} else {
				page.set_primary_action(__('New Cohort'), () => showNewCohortDialog());
				page.set_secondary_action(__('Monthly Cohorts'), () =>
					showAutomatedMonthlyModal(),
				);
			}
		}

		function toggleGlificMenuItem(label, show) {
			const g = __('Glific');
			const full = `${g} > ${label}`;
			page.menu.find('span.menu-item-label').each(function syncLab() {
				if ($(this).text() === full) {
					$(this).closest('li').toggle(show);
				}
			});
		}

		function syncGlificToolbar() {
			const d = ctx.doc;
			const hasDoc = Boolean(d);
			const filtered = hasDoc && d.audience_mode === 'Filtered';
			const gid = (d && String(d.glific_group_id || '').trim()) || '';
			const showCreate = filtered && !gid;
			const showDelete = hasDoc && Boolean(gid);
			const showSync = hasDoc && Boolean(gid);
			const labSync = __('Sync Members');
			const labCreate = __('Create Collection');
			const labDelete = __('Delete');
			if (ctx._glificInnerGroupWrap && ctx._glificInnerGroupWrap.length) {
				ctx._glificInnerGroupWrap.toggle(hasDoc);
			}
			if (ctx._glificInnerDeskCreateEl && ctx._glificInnerDeskCreateEl.length) {
				ctx._glificInnerDeskCreateEl.toggle(showCreate);
			}
			if (ctx._glificInnerDeskSyncEl && ctx._glificInnerDeskSyncEl.length) {
				ctx._glificInnerDeskSyncEl.toggle(showSync);
			}
			if (ctx._glificInnerDeskDeleteEl && ctx._glificInnerDeskDeleteEl.length) {
				ctx._glificInnerDeskDeleteEl.toggle(showDelete);
			}
			toggleGlificMenuItem(labCreate, showCreate);
			toggleGlificMenuItem(labSync, showSync);
			toggleGlificMenuItem(labDelete, showDelete);
			$root.find('.mc-add-selected, .mc-add-all-matching').toggleClass('hide', !filtered);
			$root.find('.mc-remove-selected').toggleClass('hide', !hasDoc);
		}

		function setupPageToolbarMenusOnce() {
			if (ctx._toolbarMenusInitialized) return;
			ctx._toolbarMenusInitialized = true;
			const glificGroup = __('Glific');
			ctx._glificInnerDeskCreateEl = page.add_inner_button(
				__('Create Collection'),
				() => createGlificCollection(),
				glificGroup,
			);
			ctx._glificInnerDeskSyncEl = page.add_inner_button(
				__('Sync Members'),
				() => syncMembersFromManage(),
				glificGroup,
			);
			ctx._glificInnerDeskDeleteEl = page.add_inner_button(
				__('Delete'),
				() => deleteGlificGroupFromManage(),
				glificGroup,
			);
			ctx._glificInnerGroupWrap = page.get_inner_group_button(glificGroup);
			syncGlificToolbar();
		}

		function syncPageHeadActions() {
			page.hide_menu();
			page.set_secondary_action(__('Open Full Form'), () => {
				if (!ctx.docName) {
					frappe.msgprint(__('Nothing To Open'));
					return;
				}
				frappe.set_route('Form', 'Glific Group', ctx.docName);
			});
		}

		function setActiveSidebarCard(docName) {
			const $cards = $root.find('.mc-cohort-card');
			$cards.removeClass('active');
			if (!docName) return;
			$cards
				.filter(function () {
					return $(this).attr('data-name') === docName;
				})
				.addClass('active');
		}

		function refreshCohortCards(andThen) {
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_group.glific_group.get_manage_cohort_summaries',
				args: { limit: 500 },
				callback(r) {
					if (r.exc) {
						frappe.msgprint({
							title: __('Error'),
							message: __('Could Not Load Cohort List'),
							indicator: 'red',
						});
						if (typeof andThen === 'function') andThen();
						return;
					}
					const list = r.message || [];
					ctx._sidebarSummaries = list;
					const $wrap = $root.find('.mc-cohort-cards').empty();
					list.forEach((row) => {
						const ctype = frappe.utils.escape_html(
							cohortTypeDisplayLabel(row.cohort_type),
						);
						const bucket = row.automated_cohort_bucket
							? `<br>${__('Bucket')}: ${frappe.utils.escape_html(row.automated_cohort_bucket)}`
							: '';
						const period =
							row.cohort_month && row.cohort_year
								? `<br>${__('Period')}: ${frappe.utils.escape_html(row.cohort_month)} ${row.cohort_year}`
								: '';
						const syncLine = row.glific_sync_status
							? `<br>${__('Glific')}: ${frappe.utils.escape_html(row.glific_sync_status)}`
							: '';
						const created = frappe.datetime.str_to_user(row.creation);
						const updated = frappe.datetime.str_to_user(row.modified);
						const mc =
							row.member_count !== undefined && row.member_count !== null
								? String(row.member_count)
								: '0';
						const gnm = frappe.utils.escape_html(row.group_name || row.name || '');
						const $card = $(`<article class="mc-cohort-card" role="button" tabindex="0">
<div class="mc-cc-title">${gnm}</div>
<div class="mc-cc-meta">${__('Type')}: ${ctype}${bucket}${period}${syncLine}<br>${__('Created')}: ${frappe.utils.escape_html(created)}<br>${__('Updated')}: ${frappe.utils.escape_html(updated)}<br>${__('Members')}: ${frappe.utils.escape_html(mc)}</div>
</article>`);
						$card.attr('data-name', row.name);
						$card.on('click', () => loadDoc(row.name));
						$card.on('keydown', (ev) => {
							if (ev.key === 'Enter' || ev.key === ' ') {
								ev.preventDefault();
								loadDoc(row.name);
							}
						});
						$wrap.append($card);
					});
					if (ctx.docName) setActiveSidebarCard(ctx.docName);
					if (!list.length) {
						$emptyState
							.removeClass('hide')
							.text(__('No Cohorts — Use New Cohort To Create One'));
					} else {
						$emptyState.addClass('hide');
					}
					if (typeof andThen === 'function') andThen();
				},
			});
		}

		function resetPageUi() {
			ctx.doc = null;
			ctx.docName = null;
			if (ctx.filtersFg) ctx.filtersFg.refresh();
			$dirty.hide();
			ctx.selectedRows = {};
			renderResults([], 0, 0);
			refreshMemberCount();
			destroyMembersDatatable();
			$root.find('.mc-existing-count').text('');
			$root.find('.mc-members-datatable-wrap').empty();
			$readonlyFilters.addClass('hide').empty();
			$filtersBlock.removeClass('hide');
			updateFiltersChrome();
			showFilteredButtons(false);
			$mainCol.addClass('hide');
			page.hide_menu();
			setActiveSidebarCard('');
			syncGlificToolbar();
			syncNewCohortPrimary();
		}

		function loadDoc(docName) {
			ctx.doc = null;
			ctx.docName = docName;
			setActiveSidebarCard(docName);
			syncNewCohortPrimary();
			$mainCol.removeClass('hide');
			syncPageHeadActions();
			$emptyState.addClass('hide');
			frappe.call({
				method: 'frappe.client.get',
				args: { doctype: 'Glific Group', name: docName },
				callback(r) {
					if (!r.exc) onDocLoaded(r.message);
					else {
						frappe.msgprint({
							title: __('Error'),
							message: __('Could Not Load Glific Group'),
							indicator: 'red',
						});
						resetPageUi();
					}
				},
			});
		}

		function onDocLoaded(doc) {
			ctx.doc = doc;
			ctx.docName = doc.name;
			setActiveSidebarCard(doc.name);
			refreshMemberCount();
			if (isMonthlyCohortDoc(doc)) {
				renderAutomatedDocReadonly(doc);
				showFilteredButtons(false);
			} else {
				$readonlyFilters.addClass('hide').empty();
				$filtersBlock.removeClass('hide');
				updateFiltersChrome();
				ctx.filtersFg.set_values(docToFgValues(doc));
				showFilteredButtons(doc.audience_mode === 'Filtered' && !!doc.name);
				maybeApplyAfterLoad();
			}
			renderExistingMembers(doc);
			$dirty.hide();
			syncGlificToolbar();
		}

		function maybeApplyAfterLoad() {
			if (!ctx.doc || ctx.doc.audience_mode !== 'Filtered') {
				ctx.totalCount = 0;
				ctx.searchStart = 0;
				renderResults([], 0, 0);
				return;
			}
			const raw = filtersLocked(ctx.doc)
				? docToFgValues(ctx.doc)
				: getFgValuesOrNull();
			if (!raw) return;
			const v = Cf.normalize_glific_filters_from_dialog(raw);
			if (Cf.filters_have_any_criteria_glific(v)) applySearch(true);
			else {
				ctx.totalCount = 0;
				ctx.searchStart = 0;
				renderResults([], 0, 0);
			}
		}

		function docToFgValues(doc) {
			return {
				filter_wa_community: doc.filter_wa_community ? 1 : 0,
				filter_glific_wa_groups: (doc.filter_glific_wa_groups || []).map((r) => ({
					glific_wa_group: r.glific_wa_group,
				})),
				filter_cities: (doc.filter_cities || []).map((r) => ({
					samaaja_city: r.samaaja_city,
				})),
				filter_gender: doc.filter_gender || null,
				filter_contributions_min: doc.filter_contributions_min,
				filter_contributions_max: doc.filter_contributions_max,
				filter_acquisition_source_unique_id:
					doc.filter_acquisition_source_unique_id || null,
				filter_user_organization: doc.filter_user_organization || null,
				filter_last_action_date_range: Cf.date_range_from_stored(
					doc.filter_last_action_date_from,
					doc.filter_last_action_date_to,
				),
				filter_last_active_date_range: Cf.date_range_from_stored(
					doc.filter_last_active_date_from,
					doc.filter_last_active_date_to,
				),
			};
		}

		function mergeFiltersIntoDoc(doc, fgVals) {
			doc.filter_wa_community = fgVals.filter_wa_community ? 1 : 0;
			doc.filter_glific_wa_groups = [];
			let idxWa = 1;
			(fgVals.filter_glific_wa_groups || []).forEach((row) => {
				const gid = row && typeof row === 'object' ? row.glific_wa_group : row;
				if (!gid) return;
				doc.filter_glific_wa_groups.push({
					doctype: 'Glific Group Filter WA Group',
					parentfield: 'filter_glific_wa_groups',
					parenttype: 'Glific Group',
					idx: idxWa++,
					glific_wa_group: gid,
				});
			});

			doc.filter_cities = [];
			let idxC = 1;
			(fgVals.filter_cities || []).forEach((row) => {
				const city = row && typeof row === 'object' ? row.samaaja_city : row;
				if (!city) return;
				doc.filter_cities.push({
					doctype: 'Glific Group Filter City',
					parentfield: 'filter_cities',
					parenttype: 'Glific Group',
					idx: idxC++,
					samaaja_city: city,
				});
			});

			doc.filter_gender = fgVals.filter_gender || '';
			doc.filter_contributions_min = fgVals.filter_contributions_min;
			doc.filter_contributions_max = fgVals.filter_contributions_max;
			doc.filter_acquisition_source_unique_id =
				fgVals.filter_acquisition_source_unique_id || '';
			doc.filter_user_organization = fgVals.filter_user_organization || '';

			const norm = Cf.normalize_glific_filters_from_dialog(fgVals);
			doc.filter_last_action_date_from = norm.filter_last_action_date_from;
			doc.filter_last_action_date_to = norm.filter_last_action_date_to;
			doc.filter_last_active_date_from = norm.filter_last_active_date_from;
			doc.filter_last_active_date_to = norm.filter_last_active_date_to;
		}

		function rebuildSelectionFromDatatable() {
			ctx.selectedRows = {};
			if (!ctx.mcDatatable || !ctx.mcDatatable.rowmanager) return;
			const idxList = ctx.mcDatatable.rowmanager.getCheckedRows();
			(idxList || []).forEach((i) => {
				const u = ctx.rowUsers[i];
				if (u && u.user) ctx.selectedRows[u.user] = u;
			});
		}

		function bindControls() {
			$root.find('.mc-apply').on('click', () => applySearch(true));
			$root.find('.mc-next').on('click', () => pageResults(ctx.searchStart + 50));
			$root.find('.mc-prev').on('click', () =>
				pageResults(Math.max(ctx.searchStart - 50, 0)),
			);
			$root.find('.mc-select-visible').on('click', selectVisibleRows);
			$root.find('.mc-clear').on('click', clearSelectionUi);
			$root.find('.mc-add-selected').on('click', () => addSelectedToMembers());
			$root.find('.mc-add-all-matching').on('click', () => addAllMatchingToMembers());
			$root.find('.mc-remove-selected').on('click', () => removeSelectedMembersFromCohort());
		}

		function syncMembersFromManage() {
			if (!ctx.docName || !ctx.doc) {
				frappe.msgprint(__('Pick A Cohort First'));
				return;
			}
			if (!(ctx.doc.glific_group_id || '').trim()) {
				frappe.msgprint(__('Create A Glific Collection First.'));
				return;
			}
			frappe.call({
				method:
					'solve_ninja.solve_ninja.doctype.glific_group.glific_group.sync_members_to_glific',
				args: { doc_name: ctx.docName },
				freeze: true,
				freeze_message: __('Syncing Members…'),
				callback(r) {
					if (!r.exc) {
						const payload = r.message || {};
						const alertMsg = payload.added
							? __('Synced {0} member(s)', [String(payload.added)])
							: payload.message || __('Done.');
						frappe.show_alert({ message: alertMsg, indicator: 'green' });
						loadDoc(ctx.docName);
						refreshCohortCards();
					}
				},
			});
		}

		function removeSelectedMembersFromCohort() {
			if (!ctx.docName) {
				frappe.msgprint(__('Pick A Cohort First'));
				return;
			}
			if (!ctx.mcMembersDatatable || !ctx.mcMembersDatatable.rowmanager) {
				frappe.msgprint(__('No Selection'));
				return;
			}
			const idxListRaw = ctx.mcMembersDatatable.rowmanager.getCheckedRows() || [];
			const idxSet = idxListRaw.map((i) =>
				parseInt(String(i), 10),
			).filter(Number.isFinite);
			if (!idxSet.length) {
				frappe.msgprint(__('Select At Least One Member In Existing Members'));
				return;
			}

			frappe.confirm(
				__('Remove Selected Members From This Cohort?'),
				() => {
					const memberRowNames = [];
					const memberKeys = [];
					idxSet.forEach((i) => {
						const row = ctx.membersSorted[i];
						if (!row) return;
						if (row.name) memberRowNames.push(row.name);
						else memberKeys.push(memberRowDedupeKey(row));
					});
					frappe.call({
						method:
							'solve_ninja.solve_ninja.doctype.glific_group.glific_group.remove_members_from_glific_group',
						args: {
							doc_name: ctx.docName,
							member_row_names: memberRowNames,
							member_keys: memberKeys,
						},
						freeze: true,
						freeze_message: __('Removing members…'),
						callback(sv) {
							if (sv.exc) return;
							const payload = sv.message || {};
							const nLoc = payload.removed_local;
							const nG = payload.removed_glific;
							let msg = __('Members removed');
							if (nLoc != null && nG != null) {
								msg = __(
									'Removed {0} from cohort ({1} contact(s) removed in Glific)',
									[String(nLoc), String(nG)],
								);
							}
							frappe.show_alert({ message: msg, indicator: 'green' });
							loadDoc(ctx.docName);
							refreshCohortCards();
						},
					});
				},
			);
		}

		function deleteGlificGroupFromManage() {
			if (!ctx.docName) {
				frappe.msgprint(__('Pick A Cohort First'));
				return;
			}
			frappe.confirm(
				__(
					'Delete this cohort in ERPNext and remove its collection in Glific? This cannot be undone.',
				),
				() => {
					frappe.call({
						method:
							'solve_ninja.solve_ninja.doctype.glific_group.glific_group.delete_glific_group_manage',
						args: { doc_name: ctx.docName },
						freeze: true,
						freeze_message: __('Deleting…'),
						callback(r) {
							if (r.exc) return;
							frappe.show_alert({
								message: (r.message && r.message.message) || __('Group deleted'),
								indicator: 'green',
							});
							resetPageUi();
							refreshCohortCards();
						},
					});
				},
			);
		}

		function clearSelectionUi() {
			ctx.selectedRows = {};
			if (ctx.mcDatatable && ctx.mcDatatable.rowmanager) {
				ctx.mcDatatable.rowmanager.checkAll(false);
			}
		}

		function showFilteredButtons(show) {
			const en = !!(ctx.doc && ctx.doc.audience_mode === 'Filtered');
			$root.find('.mc-apply').prop('disabled', !en);
		}

		function runAudienceSearch(resetStart) {
			if (!ctx.doc || ctx.doc.audience_mode !== 'Filtered') return;
			const v = getNormalizedFiltersForSearch();
			if (!v || !Cf.filters_have_any_criteria_glific(v)) {
				frappe.msgprint(
					__(
						'Select At Least One Filter (for WhatsApp communities, enable the checkbox and choose groups).',
					),
				);
				return;
			}
			if (resetStart) ctx.searchStart = 0;
			frappe.call({
				method: 'solve_ninja.api.v1.glific_audience.search_audience_standalone',
				args: {
					filters_json: JSON.stringify(v),
					start: ctx.searchStart,
					page_length: 50,
				},
				freeze: true,
				freeze_message: __('Searching…'),
				callback(r) {
					if (!r.exc) {
						ctx.totalCount = (r.message && r.message.total_count) || 0;
						renderResults(
							(r.message && r.message.users) || [],
							ctx.searchStart,
							ctx.totalCount,
						);
					}
				},
			});
		}

		function applySearch(resetStart) {
			if (!ctx.doc || ctx.doc.audience_mode !== 'Filtered') return;
			if (filtersLocked(ctx.doc)) {
				runAudienceSearch(resetStart);
				return;
			}
			const fgVals = getFgValuesOrNull();
			if (!fgVals) return;
			const v = Cf.normalize_glific_filters_from_dialog(fgVals);
			if (!Cf.filters_have_any_criteria_glific(v)) {
				frappe.msgprint(
					__(
						'Select At Least One Filter (for WhatsApp communities, enable the checkbox and choose groups).',
					),
				);
				return;
			}
			mergeFiltersIntoDoc(ctx.doc, fgVals);
			frappe.call({
				method: 'frappe.client.save',
				args: { doc: ctx.doc },
				freeze: true,
				freeze_message: __('Saving filters…'),
				callback(res) {
					if (!res.exc) {
						ctx.doc = res.message;
						$dirty.hide();
						runAudienceSearch(resetStart);
					}
				},
			});
		}

		function pageResults(nextStart) {
			if (
				nextStart < 0 ||
				nextStart >= ctx.totalCount ||
				!ctx.doc ||
				ctx.doc.audience_mode !== 'Filtered'
			)
				return;
			const v = getNormalizedFiltersForSearch();
			if (!v || !Cf.filters_have_any_criteria_glific(v)) return;
			ctx.searchStart = nextStart;
			frappe.call({
				method: 'solve_ninja.api.v1.glific_audience.search_audience_standalone',
				args: {
					filters_json: JSON.stringify(v),
					start: ctx.searchStart,
					page_length: 50,
				},
				freeze: true,
				callback(r) {
					if (!r.exc) {
						renderResults(
							(r.message && r.message.users) || [],
							ctx.searchStart,
							ctx.totalCount,
						);
					}
				},
			});
		}

		function renderResults(users, start, total) {
			ctx.rowUsers = users || [];
			ctx.selectedRows = {};
			if (ctx.mcDatatable) {
				try {
					ctx.mcDatatable.destroy();
				} catch (e) {
					/* ignore */
				}
				ctx.mcDatatable = null;
			}

			const canSearch =
				ctx.doc &&
				ctx.doc.audience_mode === 'Filtered' &&
				getNormalizedFiltersForSearch();

			const hi = start + (ctx.rowUsers.length ? ctx.rowUsers.length : 0);
			$root.find('.mc-range').text(
				ctx.rowUsers.length
					? __('Showing {0}–{1} Of {2}', [
							String(start + 1),
							String(hi),
							String(total || 0),
						])
					: __('No Rows Loaded For This Segment'),
			);
			$root.find('.mc-prev').prop(
				'disabled',
				!canSearch || start <= 0,
			);
			const noFurther =
				!canSearch ||
				!total ||
				!ctx.rowUsers.length ||
				start + ctx.rowUsers.length >= total ||
				ctx.rowUsers.length < 50;
			$root.find('.mc-next').prop('disabled', noFurther);

			if (typeof frappe.DataTable === 'undefined') return;

			const columns = [
				{
					name: 'user',
					content: __('User'),
					editable: false,
					focusable: false,
				},
				{
					name: 'full_name',
					content: __('Name'),
					editable: false,
					focusable: false,
				},
				{
					name: 'mobile_no',
					content: __('Mobile'),
					editable: false,
					focusable: false,
				},
			];
			const data = ctx.rowUsers.map((u) => [
				u.user || '',
				u.full_name || '',
				u.mobile_no || '',
			]);

			const wrapEl = $root.find('.mc-datatable-wrap')[0];
			ctx.mcDatatable = new frappe.DataTable(wrapEl, {
				columns,
				data,
				layout: 'fluid',
				checkboxColumn: true,
				cellHeight: 28,
				inlineFilters: false,
				disableReorderColumn: true,
				serialNoColumn: false,
				noDataMessage: __('No Rows Loaded For This Segment'),
				language: frappe.boot.lang || 'en',
				translations:
					frappe.utils.datatable && frappe.utils.datatable.get_translations
						? frappe.utils.datatable.get_translations()
						: {},
				direction: frappe.utils.is_rtl && frappe.utils.is_rtl() ? 'rtl' : 'ltr',
				events: {
					onCheckRow: () => rebuildSelectionFromDatatable(),
				},
			});
		}

		function destroyMembersDatatable() {
			if (!ctx.mcMembersDatatable) return;
			try {
				ctx.mcMembersDatatable.destroy();
			} catch (e) {
				/* ignore */
			}
			ctx.mcMembersDatatable = null;
			ctx.membersSorted = [];
		}

		function renderExistingMembers(doc) {
			destroyMembersDatatable();
			const membersRaw = doc && Array.isArray(doc.members) ? doc.members.slice() : [];
			membersRaw.sort((a, b) => {
				const ia = parseInt(String(a.idx || 0), 10);
				const ib = parseInt(String(b.idx || 0), 10);
				const na = Number.isFinite(ia) ? ia : 0;
				const nb = Number.isFinite(ib) ? ib : 0;
				return na - nb;
			});
			ctx.membersSorted = membersRaw;
			const n = membersRaw.length;
			$root.find('.mc-existing-count').text(
				n ? __('{0} Rows', [String(n)]) : __('No Rows'),
			);
			const wrapEl = $root.find('.mc-members-datatable-wrap')[0];
			if (!wrapEl) return;
			if (typeof frappe.DataTable === 'undefined') return;

			const columns = [
				{
					name: 'user',
					content: __('User'),
					editable: false,
					focusable: false,
				},
				{
					name: 'contact_name',
					content: __('Contact Name'),
					editable: false,
					focusable: false,
				},
				{
					name: 'mobile_no',
					content: __('Mobile No'),
					editable: false,
					focusable: false,
				},
				{
					name: 'glific_contact_id',
					content: __('Glific Contact ID'),
					editable: false,
					focusable: false,
				},
				{
					name: 'status',
					content: __('Status'),
					editable: false,
					focusable: false,
				},
			];
			const data = membersRaw.map((row) => [
				row.user || '',
				row.contact_name || '',
				row.mobile_no || '',
				row.glific_contact_id || '',
				row.status || '',
			]);
			ctx.mcMembersDatatable = new frappe.DataTable(wrapEl, {
				columns,
				data,
				layout: 'fluid',
				checkboxColumn: true,
				cellHeight: 28,
				inlineFilters: false,
				disableReorderColumn: true,
				serialNoColumn: false,
				noDataMessage: __('No Members In Cohort Yet'),
				language: frappe.boot.lang || 'en',
				translations:
					frappe.utils.datatable && frappe.utils.datatable.get_translations
						? frappe.utils.datatable.get_translations()
						: {},
				direction: frappe.utils.is_rtl && frappe.utils.is_rtl() ? 'rtl' : 'ltr',
			});
		}

		function selectVisibleRows() {
			if (!ctx.mcDatatable || !ctx.mcDatatable.rowmanager) return;
			ctx.mcDatatable.rowmanager.checkAll(true);
			rebuildSelectionFromDatatable();
		}

		function addSelectedToMembers() {
			rebuildSelectionFromDatatable();
			const keys = Object.keys(ctx.selectedRows);
			if (!ctx.docName) {
				frappe.msgprint(__('Pick A Cohort First'));
				return;
			}
			if (!keys.length) {
				frappe.msgprint(__('Select At Least One User In Results'));
				return;
			}
			frappe.call({
				method: 'frappe.client.get',
				args: { doctype: 'Glific Group', name: ctx.docName },
				callback(r) {
					if (!r.exc) appendAndSaveMembers(r.message, keys);
				},
			});
		}

		function addAllMatchingToMembers() {
			if (!ctx.docName || !ctx.doc) {
				frappe.msgprint(__('Pick A Cohort First'));
				return;
			}
			if (ctx.doc.audience_mode !== 'Filtered') {
				frappe.msgprint(__('This cohort must use filtered audience filters.'));
				return;
			}
			ensureFiltersSavedThen(() => {
				frappe.confirm(
					__(
						'Add every user matching saved filters on this cohort to members? Duplicates by user or mobile are skipped.',
					),
					() => {
						frappe.call({
							method:
								'solve_ninja.api.v1.glific_audience.add_all_filtered_audience_to_members',
							args: { doc_name: ctx.docName },
							freeze: true,
							freeze_message: __('Adding members…'),
							callback(resp) {
								if (resp.exc) return;
								const payload = resp.message || {};
								const n = typeof payload.added === 'number' ? payload.added : null;
								const text =
									n === 0
										? __(
												'No new members (every matched user was already in the cohort).',
											)
										: __(
												'Added {0} member row(s).',
												[n !== null ? String(n) : '…'],
											);
								frappe.show_alert({
									message: payload.message ? String(payload.message) : text,
									indicator: n === 0 ? 'orange' : 'green',
								});
								loadDoc(ctx.docName);
								refreshCohortCards();
							},
						});
					},
				);
			});
		}

		function appendAndSaveMembers(doc, userIds) {
			let maxIdx = (doc.members || []).reduce((m, rr) => {
				const ix = parseInt(String(rr.idx || 0), 10);
				return Number.isFinite(ix) ? Math.max(m, ix) : m;
			}, 0);
			const existingUsers = new Set(
				(doc.members || []).map((row) => row.user).filter(Boolean),
			);
			const existingMobile = new Set(
				(doc.members || [])
					.map((row) => (row.mobile_no || '').trim())
					.filter(Boolean),
			);
			doc.members = doc.members || [];
			userIds.forEach((uid) => {
				const hit = ctx.selectedRows[uid];
				if (!hit) return;
				if (existingUsers.has(uid)) return;
				const mob = ((hit && hit.mobile_no) || '').trim();
				if (mob && existingMobile.has(mob)) return;
				maxIdx += 1;
				doc.members.push({
					doctype: 'Glific Group Contact',
					parentfield: 'members',
					parenttype: 'Glific Group',
					idx: maxIdx,
					user: uid,
					status: 'Pending',
					mobile_no: hit.mobile_no,
					contact_name: hit.full_name || '',
				});
				if (mob) existingMobile.add(mob);
				existingUsers.add(uid);
			});
			frappe.call({
				method: 'frappe.client.save',
				args: { doc },
				freeze: true,
				callback(sv) {
					if (!sv.exc) {
						frappe.msgprint(__('Members Updated'));
						loadDoc(doc.name);
						refreshCohortCards();
					}
				},
			});
		}

		function ensureFiltersSavedThen(callback) {
			if (!ctx.doc || filtersLocked(ctx.doc)) {
				callback();
				return;
			}
			const fgVals = getFgValuesOrNull();
			if (!fgVals) return;
			const v = Cf.normalize_glific_filters_from_dialog(fgVals);
			if (!Cf.filters_have_any_criteria_glific(v)) {
				frappe.msgprint(
					__(
						'Select At Least One Filter (for WhatsApp communities, enable the checkbox and choose groups).',
					),
				);
				return;
			}
			mergeFiltersIntoDoc(ctx.doc, fgVals);
			frappe.call({
				method: 'frappe.client.save',
				args: { doc: ctx.doc },
				freeze: true,
				freeze_message: __('Saving filters…'),
				callback(res) {
					if (!res.exc) {
						ctx.doc = res.message;
						$dirty.hide();
						callback();
					}
				},
			});
		}

		function createGlificCollection() {
			if (!ctx.docName || !ctx.doc) {
				frappe.msgprint(__('Pick A Cohort First'));
				return;
			}
			if (ctx.doc.audience_mode !== 'Filtered') {
				frappe.msgprint(__('This cohort must use filtered audience filters.'));
				return;
			}
			ensureFiltersSavedThen(() => {
				frappe.confirm(
					__(
						'Create an empty Glific collection for this cohort? Contacts are added later via Sync Members.',
					),
					() => {
						frappe.call({
							method:
								'solve_ninja.api.v1.glific_audience.create_filtered_glific_collection',
							args: {
								doc_name: ctx.docName,
							},
							freeze: true,
							callback(resp) {
								if (!resp.exc) {
									const payload = resp.message || {};
									frappe.show_alert({
										message:
											payload.message ||
											__('Glific collection created.'),
										indicator: 'green',
									});
									loadDoc(ctx.docName);
									refreshCohortCards();
								}
							},
						});
					},
				);
			});
		}

		function showNewCohortDialog() {
			const yr = new Date().getFullYear();
			const monthNames = COHORT_MONTH_OPTIONS.split('\n');
			const defaultMonth = monthNames[new Date().getMonth()];
			const dlg = new frappe.ui.Dialog({
				title: __('New Glific Cohort'),
				fields: [
					{
						fieldtype: 'Select',
						fieldname: 'cohort_type',
						label: __('Cohort Type'),
						options: 'Custom Cohort\nMonthly Cohort\nAutomated Cohort',
						default: 'Custom Cohort',
						reqd: 1,
					},
					{
						fieldtype: 'Data',
						fieldname: 'group_name',
						label: __('Group Name'),
						reqd: 1,
						depends_on: 'eval:doc.cohort_type=="Custom Cohort"',
					},
					{
						fieldtype: 'HTML',
						fieldname: 'automated_help',
						options: `<p class="text-muted small">${__(
							'Use <b>Monthly Cohorts</b> to classify users and create Glific collections for the selected month.',
						)}</p><button type="button" class="btn btn-default btn-sm mc-open-automated-modal">${__(
							'Open Monthly Cohorts',
						)}</button>`,
						depends_on:
							'eval:["Monthly Cohort","Automated Cohort"].includes(doc.cohort_type)',
					},
					{ fieldtype: 'Column Break' },
					{
						fieldtype: 'Select',
						fieldname: 'cohort_month',
						label: __('Cohort Month'),
						options: COHORT_MONTH_OPTIONS,
						default: defaultMonth,
						reqd: 1,
						depends_on: 'eval:doc.cohort_type=="Custom Cohort"',
					},
					{
						fieldtype: 'Int',
						fieldname: 'cohort_year',
						label: __('Cohort Year'),
						default: yr,
						reqd: 1,
						depends_on: 'eval:doc.cohort_type=="Custom Cohort"',
					},
				],
				primary_action_label: __('Create'),
				primary_action(vals) {
					if (!vals) return;
					if (isMonthlyCohortType(vals.cohort_type)) {
						dlg.hide();
						showAutomatedMonthlyModal();
						return;
					}
					const doc = {
						doctype: 'Glific Group',
						group_name: vals.group_name,
						audience_mode: 'Filtered',
						cohort_type: vals.cohort_type,
						cohort_month: vals.cohort_month,
						cohort_year: vals.cohort_year,
					};
					frappe.call({
						method: 'frappe.client.insert',
						args: { doc },
						callback(r) {
							if (!r.exc && r.message) {
								frappe.show_alert({ message: __('Cohort Created'), indicator: 'green' });
								dlg.hide();
								const newName = r.message.name;
								refreshCohortCards(() => loadDoc(newName));
							}
						},
					});
				},
			});
			dlg.show();
			dlg.$wrapper.on('click', '.mc-open-automated-modal', () => {
				dlg.hide();
				showAutomatedMonthlyModal();
			});
		}
	};

	frappe.pages[PAGE].on_page_show = function () {
		frappe.pages[PAGE]._solve_ninja_route_pick?.();
	};
})();
