"""Bootstrap Samaaja States/Cities from the committed local JSON."""

from solve_ninja.patches.geo_seed_utils import (
	backfill_existing_city_states,
	load_local_states_cities,
	upsert_states_cities,
)

import frappe


def execute():
	states_cities = load_local_states_cities()
	if not states_cities:
		frappe.logger("solve_ninja.geo_seed").warning(
			"Local india_states_cities.json missing or empty; skipping bootstrap seed"
		)
		return

	upsert_states_cities(states_cities)
	backfill_existing_city_states()
	frappe.db.commit()
