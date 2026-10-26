import json
from pathlib import Path

import frappe

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "india_states_cities.json"

# Best-effort mapping for existing Samaaja Cities that don't match seeded names exactly.
EXISTING_CITY_STATE = {
	"Amritsar": "Punjab",
	"Bangalore": "Karnataka",
	"Bangalore Division": "Karnataka",
	"Bengaluru": "Karnataka",
	"Bengaluru Urban": "Karnataka",
	"Chennai": "Tamil Nadu",
	"Delhi": "Delhi",
	"Guwahati": "Assam",
	"Guwahati-1": "Assam",
	"Hajipur": "Bihar",
	"Hoshiarpur": "Punjab",
	"Jaipur": "Rajasthan",
	"Jalandhar": "Punjab",
	"Jharkhand": "Jharkhand",
	"Jorhat": "Assam",
	"Ludhiana": "Punjab",
	"Mansa": "Punjab",
	"Mumbai": "Maharashtra",
	"Mysuru": "Karnataka",
	"Nalbari": "Assam",
	"Nanded": "Maharashtra",
	"New Delhi": "Delhi",
	"Other": "Other Territory",
	"Patiala": "Punjab",
	"Patna": "Bihar",
	"Pimpri-Chinchwad": "Maharashtra",
	"Pune": "Maharashtra",
	"Pune Division": "Maharashtra",
	"Varanasi": "Uttar Pradesh",
}

# Map API / alternate spellings onto Samaaja States / User Metadata names.
STATE_ALIASES = {
	"Puducherry": "Pondicherry",
	"Pondicherry": "Pondicherry",
	"Odisha": "Odisha",
	"Orissa": "Odisha",
	"Nct Of Delhi": "Delhi",
	"Delhi": "Delhi",
	"Jammu & Kashmir": "Jammu and Kashmir",
	"Jammu And Kashmir": "Jammu and Kashmir",
	"Dadra & Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
	"Dadra And Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
	"Daman & Diu": "Dadra and Nagar Haveli and Daman and Diu",
	"Daman And Diu": "Dadra and Nagar Haveli and Daman and Diu",
	"Dadra And Nagar Haveli And Daman And Diu": "Dadra and Nagar Haveli and Daman and Diu",
	"Andaman & Nicobar Islands": "Andaman and Nicobar Islands",
	"Andaman And Nicobar Islands": "Andaman and Nicobar Islands",
	"Lakshadweep": "Lakshadweep Islands",
	"Lakshadweep Islands": "Lakshadweep Islands",
}


def data_file_path() -> Path:
	return DATA_PATH


def normalize_state_name(name: str | None) -> str | None:
	if not name:
		return None
	cleaned = " ".join(str(name).strip().split())
	if not cleaned:
		return None
	titled = cleaned.title()
	return STATE_ALIASES.get(titled, titled)


def normalize_city_name(name: str | None) -> str | None:
	if not name:
		return None
	cleaned = " ".join(str(name).strip().split())
	if not cleaned:
		return None
	return cleaned.title()


def load_local_states_cities() -> dict[str, list[str]]:
	path = data_file_path()
	if not path.exists():
		return {}
	with open(path, encoding="utf-8") as f:
		raw = json.load(f)
	result: dict[str, list[str]] = {}
	for state, cities in (raw or {}).items():
		state_name = normalize_state_name(state)
		if not state_name:
			continue
		normalized_cities = []
		seen = set()
		for city in cities or []:
			city_name = normalize_city_name(city)
			if city_name and city_name not in seen:
				seen.add(city_name)
				normalized_cities.append(city_name)
		result[state_name] = sorted(normalized_cities)
	return result


def save_local_states_cities(states_cities: dict[str, list[str] | set[str]]) -> None:
	path = data_file_path()
	path.parent.mkdir(parents=True, exist_ok=True)
	serializable = {
		state: sorted(list(cities))
		for state, cities in sorted(states_cities.items(), key=lambda item: item[0])
	}
	with open(path, "w", encoding="utf-8") as f:
		json.dump(serializable, f, indent=2, ensure_ascii=False)
		f.write("\n")


def count_local_cities(states_cities: dict[str, list[str]] | None = None) -> int:
	data = states_cities if states_cities is not None else load_local_states_cities()
	return sum(len(cities) for cities in data.values())


def ensure_state(state_name: str) -> str | None:
	state_name = normalize_state_name(state_name)
	if not state_name:
		return None
	if frappe.db.exists("Samaaja States", state_name):
		return state_name
	doc = frappe.get_doc({"doctype": "Samaaja States", "state_name": state_name})
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_city(city_name: str, state_name: str) -> str | None:
	city_name = normalize_city_name(city_name)
	state_name = ensure_state(state_name)
	if not city_name or not state_name:
		return None

	if frappe.db.exists("Samaaja Cities", city_name):
		current_state = frappe.db.get_value("Samaaja Cities", city_name, "state")
		if not current_state:
			frappe.db.set_value(
				"Samaaja Cities", city_name, "state", state_name, update_modified=False
			)
		elif current_state != state_name:
			# City names are unique nationally; keep the first linked state.
			frappe.logger("solve_ninja.geo_seed").warning(
				f"City '{city_name}' already linked to '{current_state}', skipping '{state_name}'"
			)
		return city_name

	doc = frappe.get_doc(
		{
			"doctype": "Samaaja Cities",
			"city_name": city_name,
			"state": state_name,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def upsert_states_cities(states_cities: dict[str, list[str] | set[str]]) -> tuple[int, int]:
	"""Upsert map of state -> cities. Returns (state_count, city_count)."""
	state_count = 0
	city_count = 0
	for state_name, cities in states_cities.items():
		if ensure_state(state_name):
			state_count += 1
		for city_name in cities:
			if ensure_city(city_name, state_name):
				city_count += 1
	return state_count, city_count


def backfill_existing_city_states() -> None:
	for city_name, state_name in EXISTING_CITY_STATE.items():
		if not frappe.db.exists("Samaaja Cities", city_name):
			continue
		ensure_state(state_name)
		current_state = frappe.db.get_value("Samaaja Cities", city_name, "state")
		if not current_state:
			frappe.db.set_value(
				"Samaaja Cities", city_name, "state", state_name, update_modified=False
			)
