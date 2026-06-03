// Copyright (c) 2026, ReapBenefit and contributors
// For license information, please see license.txt

/** Shared Desk helpers for Manage Cohort page and Glific Group filter modal — mirrors glific_audience.py. */
frappe.provide('solve_ninja.glific_cohort_filters');

(function () {
	const G = window.solve_ninja.glific_cohort_filters;

	function gg_cint(v, def = 0) {
		if (v === true) return 1;
		if (v === false) return 0;
		if (v === null || v === undefined || v === '') return def;
		const n = parseInt(String(v), 10);
		return Number.isNaN(n) ? def : n;
	}

	function gg_cint_or_null(rawVal) {
		if (rawVal === undefined || rawVal === null || rawVal === '') return null;
		const n = parseInt(String(rawVal), 10);
		return Number.isNaN(n) ? null : n;
	}

	function gg_date_or_null(val) {
		if (val === undefined || val === null || val === '') return null;
		const s = String(val).trim();
		return s || null;
	}

	function gg_coerce_multiselect_list(val, linkFieldName) {
		if (val === undefined || val === null || val === '') return [];
		let v = val;
		if (typeof v === 'string') {
			try {
				const parsed = JSON.parse(v);
				if (Array.isArray(parsed)) v = parsed;
				else return [];
			} catch (_e) {
				return [];
			}
		}
		if (!Array.isArray(v)) return [];
		const dedup = new Set();
		v.forEach((row) => {
			let cell = '';
			if (typeof row === 'string') cell = row.trim();
			else if (row && typeof row === 'object' && row[linkFieldName])
				cell = String(row[linkFieldName]).trim();
			if (cell) dedup.add(cell);
		});
		return Array.from(dedup).sort();
	}

	function date_range_from_stored(fromVal, toVal) {
		const from = gg_date_or_null(fromVal);
		const to = gg_date_or_null(toVal);
		if (!from && !to) return null;
		return [from || to, to || from];
	}

	function stored_from_date_range(rangeVal) {
		if (!rangeVal) return { from: null, to: null };
		if (Array.isArray(rangeVal) && rangeVal.length >= 2) {
			return {
				from: gg_date_or_null(rangeVal[0]),
				to: gg_date_or_null(rangeVal[1]),
			};
		}
		return { from: null, to: null };
	}

	function merge_date_ranges_into_normalized(out, raw) {
		const action = stored_from_date_range(raw.filter_last_action_date_range);
		const active = stored_from_date_range(raw.filter_last_active_date_range);
		out.filter_last_action_date_from =
			gg_date_or_null(raw.filter_last_action_date_from) || action.from;
		out.filter_last_action_date_to =
			gg_date_or_null(raw.filter_last_action_date_to) || action.to;
		out.filter_last_active_date_from =
			gg_date_or_null(raw.filter_last_active_date_from) || active.from;
		out.filter_last_active_date_to =
			gg_date_or_null(raw.filter_last_active_date_to) || active.to;
		return out;
	}

	function normalize_glific_filters_from_dialog(raw) {
		const trim = (x) => (x == null || x === undefined ? '' : String(x)).trim();
		const out = {
			filter_wa_community: gg_cint(raw.filter_wa_community),
			filter_glific_wa_groups: gg_coerce_multiselect_list(
				raw.filter_glific_wa_groups,
				'glific_wa_group',
			),
			filter_wa_community_glific_group_id: trim(raw.filter_wa_community_glific_group_id),
			filter_contributions_min: gg_cint_or_null(raw.filter_contributions_min),
			filter_contributions_max: gg_cint_or_null(raw.filter_contributions_max),
			filter_cities: gg_coerce_multiselect_list(raw.filter_cities, 'samaaja_city'),
			filter_city: raw.filter_city || null,
			filter_gender: raw.filter_gender || null,
			filter_acquisition_source_unique_id: trim(raw.filter_acquisition_source_unique_id),
			filter_user_organization: raw.filter_user_organization || null,
			filter_last_action_date_from: null,
			filter_last_action_date_to: null,
			filter_last_active_date_from: null,
			filter_last_active_date_to: null,
		};
		return merge_date_ranges_into_normalized(out, raw);
	}

	function filters_have_any_criteria_glific(f) {
		const waOn = gg_cint(f.filter_wa_community);
		const waGroups = f.filter_glific_wa_groups && f.filter_glific_wa_groups.length;
		const waLegacy = !!(
			f.filter_wa_community_glific_group_id &&
			String(f.filter_wa_community_glific_group_id).trim()
		);
		if (waOn && (waGroups || waLegacy)) return true;
		if (f.filter_contributions_min != null) return true;
		if (f.filter_contributions_max != null) return true;
		if (f.filter_cities && f.filter_cities.length) return true;
		if (f.filter_city) return true;
		if (f.filter_gender) return true;
		if (f.filter_acquisition_source_unique_id) return true;
		if (f.filter_user_organization) return true;
		if (gg_date_or_null(f.filter_last_action_date_from)) return true;
		if (gg_date_or_null(f.filter_last_action_date_to)) return true;
		if (gg_date_or_null(f.filter_last_active_date_from)) return true;
		if (gg_date_or_null(f.filter_last_active_date_to)) return true;
		return false;
	}

	function format_date_range_display(fromVal, toVal) {
		const from = gg_date_or_null(fromVal);
		const to = gg_date_or_null(toVal);
		if (!from && !to) return null;
		const fmt = (d) => (d ? frappe.datetime.str_to_user(d) : '—');
		return `${fmt(from)} – ${fmt(to)}`;
	}

	Object.assign(G, {
		normalize_glific_filters_from_dialog,
		filters_have_any_criteria_glific,
		gg_coerce_multiselect_list,
		date_range_from_stored,
		stored_from_date_range,
		format_date_range_display,
	});
})();
