"""
Pull unique state + district pairs from data.gov.in (India Post PIN resource),
upsert into Samaaja States / Samaaja Cities, and cache to local JSON.

Pulls per-state (with retries / backoff) to reduce payload size and survive
rate limits. Progress is saved after each state so re-runs resume cleanly.
"""

from __future__ import annotations

import time

import requests

import frappe
from solve_ninja.patches.geo_seed_utils import (
	backfill_existing_city_states,
	count_local_cities,
	load_local_states_cities,
	normalize_city_name,
	normalize_state_name,
	save_local_states_cities,
	upsert_states_cities,
)

DATA_GOV_RESOURCE_URL = "https://api.data.gov.in/resource/5c2f62fe-5afa-4119-a499-fec9d604d5bd"
PAGE_SIZE = 1000
LOCAL_CITY_THRESHOLD = 600
REQUEST_TIMEOUT = 90
MAX_RETRIES = 5
PAGE_SLEEP_SECONDS = 0.4
STATE_SLEEP_SECONDS = 0.8

# API often stores state names in uppercase; try a few variants per state.
STATE_FILTER_VARIANTS = (
	lambda s: s.upper(),
	lambda s: s,
	lambda s: s.title(),
)


def execute():
	logger = frappe.logger("solve_ninja.geo_seed")
	local = load_local_states_cities()
	local_city_count = count_local_cities(local)
	db_city_count = frappe.db.count("Samaaja Cities", {"state": ["is", "set"]})
	force = bool(frappe.conf.get("force_pull_india_states_cities"))

	should_pull = force or local_city_count < LOCAL_CITY_THRESHOLD or db_city_count < LOCAL_CITY_THRESHOLD

	if should_pull:
		try:
			states_cities = pull_from_data_gov(existing=local)
			unique_cities = count_local_cities(
				{state: list(cities) for state, cities in states_cities.items()}
			)
			logger.info(
				f"data.gov.in pull complete: {len(states_cities)} states, {unique_cities} unique districts"
			)
			save_local_states_cities(states_cities)
		except Exception as e:
			frappe.log_error(
				title="pull_india_states_cities",
				message=f"data.gov.in pull failed, falling back to local JSON: {e}",
			)
			logger.error(f"data.gov.in pull failed: {e}")
			states_cities = local
	else:
		logger.info(
			f"Skipping data.gov.in pull (local={local_city_count}, db={db_city_count} >= {LOCAL_CITY_THRESHOLD})"
		)
		states_cities = local

	if not states_cities:
		logger.warning("No state/city data available to upsert")
		return

	normalized = {
		normalize_state_name(state) or state: sorted(
			{
				normalize_city_name(city) or city
				for city in cities
				if normalize_city_name(city)
			}
		)
		for state, cities in states_cities.items()
		if normalize_state_name(state)
	}

	upsert_states_cities(normalized)
	backfill_existing_city_states()
	frappe.db.commit()


def _bootstrap_state_names(existing: dict[str, list[str]]) -> list[str]:
	"""States to query: existing Samaaja States + local JSON + User Metadata options."""
	names = set(existing.keys())
	names.update(frappe.get_all("Samaaja States", pluck="name", ignore_permissions=True) or [])

	meta = frappe.get_meta("User Metadata")
	state_field = meta.get_field("state") if meta else None
	if state_field and state_field.options:
		for option in state_field.options.split("\n"):
			normalized = normalize_state_name(option)
			if normalized:
				names.add(normalized)

	return sorted(names)


def pull_from_data_gov(existing: dict[str, list[str]] | None = None) -> dict[str, set[str]]:
	api_key = frappe.conf.get("data_gov_api_key")
	if not api_key:
		raise RuntimeError("data_gov_api_key not found in site config")

	logger = frappe.logger("solve_ninja.geo_seed")
	states_cities: dict[str, set[str]] = {
		state: set(cities) for state, cities in (existing or {}).items()
	}
	states = _bootstrap_state_names(existing or {})
	if not states:
		raise RuntimeError("No states available to query on data.gov.in")

	pulled_any = False
	for index, state in enumerate(states, start=1):
		logger.info(f"Pulling districts for state {index}/{len(states)}: {state}")
		districts = _pull_districts_for_state(api_key, state)
		if districts:
			pulled_any = True
			states_cities.setdefault(state, set()).update(districts)
			# Persist after each state so rate-limit / timeout loss is limited.
			save_local_states_cities(states_cities)
			logger.info(f"{state}: {len(districts)} districts (running unique={sum(len(v) for v in states_cities.values())})")
		time.sleep(STATE_SLEEP_SECONDS)

	if not pulled_any and count_local_cities({s: list(c) for s, c in states_cities.items()}) < LOCAL_CITY_THRESHOLD:
		# Fallback: unfiltered pagination if per-state filters returned nothing.
		logger.warning("Per-state pull returned no new data; trying unfiltered pagination")
		states_cities = _pull_unfiltered(api_key, states_cities)
		save_local_states_cities(states_cities)

	if not states_cities:
		raise RuntimeError("data.gov.in returned no usable state/district records")

	return states_cities


def _pull_districts_for_state(api_key: str, state: str) -> set[str]:
	logger = frappe.logger("solve_ninja.geo_seed")
	districts: set[str] = set()
	for variant_fn in STATE_FILTER_VARIANTS:
		filter_value = variant_fn(state)
		try:
			page_districts = _paginate(
				api_key,
				extra_params={"filters[statename]": filter_value},
			)
		except Exception as e:
			logger.warning(f"Failed pulling state={state} filter={filter_value}: {_redact(e)}")
			continue
		if page_districts:
			for _state_name, cities in page_districts.items():
				districts.update(cities)
			break
	return districts


def _pull_unfiltered(api_key: str, states_cities: dict[str, set[str]]) -> dict[str, set[str]]:
	pulled = _paginate(api_key, extra_params={})
	for state, cities in pulled.items():
		states_cities.setdefault(state, set()).update(cities)
	return states_cities


def _paginate(api_key: str, extra_params: dict) -> dict[str, set[str]]:
	logger = frappe.logger("solve_ninja.geo_seed")
	states_cities: dict[str, set[str]] = {}
	offset = 0
	total = None
	page = 0

	while True:
		page += 1
		params = {
			"api-key": api_key,
			"format": "json",
			"limit": PAGE_SIZE,
			"offset": offset,
			**extra_params,
		}
		payload = _request_with_retries(params)
		if total is None:
			total = int(payload.get("total") or 0)
			logger.info(
				f"data.gov.in page query total={total} filters={list(extra_params.keys())}"
			)

		records = payload.get("records") or []
		if not records:
			break

		for record in records:
			state = normalize_state_name(record.get("statename") or record.get("stateName"))
			city = normalize_city_name(record.get("district") or record.get("District"))
			if not state or not city:
				continue
			states_cities.setdefault(state, set()).add(city)

		offset += len(records)
		logger.info(
			f"data.gov.in page {page}: fetched {offset}"
			+ (f"/{total}" if total else "")
			+ f", unique districts so far={sum(len(v) for v in states_cities.values())}"
		)

		if total and offset >= total:
			break
		if len(records) < PAGE_SIZE:
			break
		time.sleep(PAGE_SLEEP_SECONDS)

	return states_cities


def _redact(error: Exception | str) -> str:
	text = str(error)
	api_key = frappe.conf.get("data_gov_api_key") or ""
	if api_key:
		text = text.replace(api_key, "***")
	return text


def _request_with_retries(params: dict) -> dict:
	logger = frappe.logger("solve_ninja.geo_seed")
	last_error = None

	for attempt in range(1, MAX_RETRIES + 1):
		try:
			response = requests.get(
				DATA_GOV_RESOURCE_URL,
				params=params,
				timeout=REQUEST_TIMEOUT,
			)
			try:
				payload = response.json()
			except ValueError:
				payload = {}

			if response.status_code == 429 or (
				isinstance(payload, dict)
				and "rate limit" in str(payload.get("error", "")).lower()
			):
				raise requests.exceptions.RequestException(
					f"Rate limited: {payload.get('error') or response.status_code}"
				)

			response.raise_for_status()
			if not isinstance(payload, dict):
				raise requests.exceptions.RequestException(
					"Invalid JSON payload from data.gov.in"
				)
			return payload
		except requests.exceptions.RequestException as e:
			last_error = e
			sleep_for = min(60, 2**attempt)
			logger.warning(
				f"data.gov.in request failed (attempt {attempt}/{MAX_RETRIES}): {_redact(e)}; "
				f"sleeping {sleep_for}s"
			)
			time.sleep(sleep_for)

	raise RuntimeError(
		f"data.gov.in request failed after {MAX_RETRIES} retries: {_redact(last_error)}"
	)
