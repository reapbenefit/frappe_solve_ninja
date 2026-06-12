import os
import frappe
from frappe.utils import logger
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from frappe.utils import get_datetime
import time
import psutil
from solve_ninja.api.user import update_user_creation_field
from solve_ninja.api.common import update_user_metadata, update_ninja_profile
from solve_ninja.utils import find_user_by_mobile, validate_and_normalize_mobile

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

GLIFIC_BQ_DATASET = "glific-301906.918095500118"

WA_GROUP_MEMBERS_QUERY = f"""
SELECT
  c.id AS glific_contact_id,
  COALESCE(c.name, cwg.phone) AS contact_name,
  cwg.phone AS phone,
  cwg.group_label,
  cwg.is_admin
FROM `{GLIFIC_BQ_DATASET}.contacts_wa_groups` AS cwg
LEFT JOIN `{GLIFIC_BQ_DATASET}.contacts` AS c
  ON c.phone = cwg.phone
WHERE cwg.group_id = @group_id
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY cwg.phone
  ORDER BY cwg.updated_at DESC NULLS LAST, cwg.inserted_at DESC NULLS LAST
) = 1
"""


def bigquery_credentials_configured():
	return bool(frappe.conf.get("google_credentials_path"))


def get_bigquery_module():
	"""Lazy import so credential checks and API fallbacks work without the BQ library."""
	try:
		from google.cloud import bigquery

		return bigquery
	except ImportError:
		return None


def bigquery_client_available():
	return bigquery_credentials_configured() and get_bigquery_module() is not None


def setup_bigquery_credentials():
	credentials_path = frappe.conf.get("google_credentials_path")
	if not credentials_path:
		return None
	os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
	return credentials_path


def get_bigquery_client():
	bigquery = get_bigquery_module()
	if not bigquery:
		frappe.throw(
			"google-cloud-bigquery is not installed. Install it in the bench env: "
			"pip install google-cloud-bigquery"
		)
	if not setup_bigquery_credentials():
		frappe.throw("google_credentials_path missing in site_config.json")
	return bigquery.Client()


def bq_row_to_contact_dict(row) -> dict:
	"""Map BigQuery row to Glific-style contact dict for member sync."""
	if not isinstance(row, dict):
		row = dict(row)
	glific_contact_id = row.get("glific_contact_id")
	return {
		"id": str(glific_contact_id) if glific_contact_id is not None else "",
		"name": (row.get("contact_name") or "").strip(),
		"phone": (row.get("phone") or "").strip(),
	}


def fetch_wa_group_members_from_bigquery(group_id: int) -> list:
	"""Load WA group members from ``contacts_wa_groups`` joined to ``contacts``."""
	bigquery = get_bigquery_module()
	if not bigquery:
		raise ImportError(
			"google-cloud-bigquery is not installed. "
			"Install with: pip install google-cloud-bigquery"
		)
	job_config = bigquery.QueryJobConfig(
		query_parameters=[
			bigquery.ScalarQueryParameter("group_id", "INT64", int(group_id)),
		]
	)
	client = get_bigquery_client()
	results = client.query(WA_GROUP_MEMBERS_QUERY, job_config=job_config).result()
	return [bq_row_to_contact_dict(row) for row in results]


def sync_wa_group_members_from_bigquery():
	"""Scheduled job: refresh member child tables for all Glific WA Group docs via BigQuery."""
	logger.info("sync_wa_group_members_from_bigquery started")

	if not bigquery_client_available():
		logger.error(
			"BigQuery unavailable (missing credentials or google-cloud-bigquery package)"
		)
		return {"updated": 0, "errors": ["BigQuery unavailable"]}

	updated = 0
	errors = []

	for name in frappe.get_all("Glific WA Group", pluck="name"):
		try:
			doc = frappe.get_doc("Glific WA Group", name)
			doc.flags.ignore_permissions = True
			res = doc.sync_members_from_glific(source="bigquery")
			if res.get("ok"):
				doc.sync_status = "Success"
				doc.sync_error = None
			else:
				doc.sync_status = "Partial"
				doc.sync_error = res.get("error")
			doc.last_synced_on = frappe.utils.now()
			doc.save()
			frappe.db.commit()
			updated += 1
		except Exception:
			errors.append(f"{name}: {traceback.format_exc()[:500]}")
			frappe.log_error(
				title=f"sync_wa_group_members_from_bigquery failed for {name}",
				message=traceback.format_exc(),
			)

	logger.info(
		f"sync_wa_group_members_from_bigquery completed — updated: {updated}, errors: {len(errors)}"
	)
	return {"updated": updated, "errors": errors}


def get_language_code(language):
    language_map = {
        "English": "en",
        "Punjabi": "pa",
        "Marathi": "mr",
        "Hindi": "hi",
        "Kannada": "kn",
        "Assamese": "as",
        "Bengali": "bn",
        "Telugu": "te"
    }

    if language not in language_map:
        frappe.log_error(f"Language '{language}' is not recognized.")
        logger.error(f"Language '{language}' is not recognized.")
        frappe.throw(f"Language '{language}' is not recognized.")

    return language_map[language]


@frappe.whitelist()
def sync_metadata_from_bigquery():
    logger.info("🔄 sync_metadata_from_bigquery started")

    if not bigquery_client_available():
        frappe.log_error(
            "❌ BigQuery unavailable (google_credentials_path or google-cloud-bigquery missing)"
        )
        logger.error("❌ BigQuery unavailable")
        return

    bigquery = get_bigquery_module()
    setup_bigquery_credentials()

    last_successful_run_str = frappe.get_single("Glific Sync").last_successful_run
    last_successful_run = get_datetime(last_successful_run_str) if last_successful_run_str else None
    logger.info(f"🕒 Last successful run: {last_successful_run}")

    updated = 0
    not_found = 0

    query_base = """
        SELECT AS VALUE ARRAY_AGG(x ORDER BY last_active_date DESC LIMIT 1)[OFFSET(0)]
        FROM (
            SELECT 
                m.contact_phone,
                m.inserted_at AS last_active_date,
                c.id AS whatsapp_id,
                c.language AS language,
                -- Extract values from c.fields using filtered UNNEST
                cf1.value AS preferred_name,
                cf2.value AS gender,
                cf3.value AS pincode,
                cf4.value AS year_of_birth

            FROM `glific-301906.918095500118.messages` m
            LEFT JOIN `glific-301906.918095500118.contacts` c
                ON m.contact_phone = c.phone

            -- Unnest and filter for each field
            LEFT JOIN UNNEST(c.fields) AS cf1 ON cf1.label = 'preferred_name'
            LEFT JOIN UNNEST(c.fields) AS cf2 ON cf2.label = 'Gender'
            LEFT JOIN UNNEST(c.fields) AS cf3 ON cf3.label = 'pincode'
            LEFT JOIN UNNEST(c.fields) AS cf4 ON cf4.label = 'year_of_birth'

            WHERE m.flow = 'inbound' {filter_clause}
        ) x
        GROUP BY contact_phone
    """

    try:
        filter_clause = ""
        query_params = []

        if last_successful_run:
            logger.info("📌 Applying filter by last_successful_run datetime (IST wall-clock)")

            # Drop timezone info because BigQuery DATETIME has no timezone
            if last_successful_run.tzinfo:
                last_successful_run = last_successful_run.replace(tzinfo=None)
            logger.info(f"🕒 last_successful_run (Python, naive): {last_successful_run!r}")

            filter_clause = "AND m.inserted_at > @last_run"
            query_params.append(
                bigquery.ScalarQueryParameter("last_run", "DATETIME", last_successful_run)
            )
        else:
            logger.info("⚠️ No last_successful_run datetime found, skipping filter")

        query = query_base.format(filter_clause=filter_clause)
    
        job_config = bigquery.QueryJobConfig(query_parameters=query_params) if query_params else None

        client = get_bigquery_client()
        results = client.query(query, job_config=job_config).result()
        updates = [(row["contact_phone"], row["last_active_date"], row["whatsapp_id"], row["preferred_name"], row["gender"], row["pincode"], row["year_of_birth"], row["language"]) for row in results]

        logger.info(f"✅ Total rows from BigQuery: {len(updates)}")

        total = len(updates)
        next_log_percent = 10
        start_time = time.time()
        process = psutil.Process()

        for i, (contact_phone, last_active_date, whatsapp_id, preferred_name,gender,pincode,year_of_birth,language) in enumerate(updates, start=1):
            email = contact_phone + "@solveninja.org"
           
            profiles = frappe.get_all(
                "Ninja Profile",
                filters={"user": email},
                fields=["name"]
            )

            if not profiles:
                #logger.info(f"⚠️ No Ninja Profile found for user: {email}")
                not_found += 1
                continue

            ninja_profile_doc = frappe.get_doc("Ninja Profile", profiles[0]["name"])
            ninja_profile_doc.last_active_date_bot = last_active_date
            if ninja_profile_doc.wa_id is None:
                ninja_profile_doc.wa_id = whatsapp_id
            ninja_profile_doc.save(ignore_permissions=True)

            frappe.db.commit()

            updated += 1
            
            #logger.info(f"📝 Updated profile for {email}")
            percent_complete = int((i / total) * 100)
            if percent_complete >= next_log_percent:
                elapsed = time.time() - start_time
                avg_time = elapsed / i
                eta = int((total - i) * avg_time)
                mem_mb = process.memory_info().rss / 1024 / 1024

                logger.info(
                    f"📊 {percent_complete}% complete ({i}/{total}) | "
                    f"⏱️ ETA: {eta // 60}m {eta % 60}s | "
                    f"🧠 Mem: {mem_mb:.1f}MB"
                )
                next_log_percent += 10

        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        frappe.db.set_single_value("Glific Sync", "last_successful_run", now_ist)

    except Exception as e:
        frappe.log_error(
            title="Error in sync_metadata_from_bigquery",
            message=traceback.format_exc()
        )
        logger.error(f"❌ Error in BigQuery sync: {e}")

    logger.info(f"🎯 Completed sync — ✅ Updated: {updated} | ❌ Not found: {not_found}")

def initiate_sync_user_creation_from_bigquery():
    frappe.enqueue(
    "solve_ninja.api.glific_sync.sync_user_creation_from_bigquery",
    queue="long",
    timeout=60 * 60 * 12  # 12 hours
)


def sync_user_creation_from_bigquery():
    frappe.logger().info("🔄 sync_user_creation_from_bigquery started")

    if not bigquery_client_available():
        frappe.log_error("❌ BigQuery unavailable")
        return

    setup_bigquery_credentials()
    updated = 0
    not_found = 0

    query = """
       select distinct phone,inserted_at from `glific-301906.918095500118.contacts`
    """

    try:
        client = get_bigquery_client()
        results = client.query(query, job_config=None).result()
        updates = [(row["phone"], row["inserted_at"]) for row in results]

        frappe.logger().info(f"✅ Total rows from BigQuery: {len(updates)}")

        total = len(updates)
        next_log_percent = 10
        start_time = time.time()
        process = psutil.Process()

        for i, (phone, inserted_at) in enumerate(updates, start=1):
            
            try:
                update_user_creation_field(phone, inserted_at)
                updated += 1
            except Exception as e:
                not_found += 1
                continue
            
            
            percent_complete = int((i / total) * 100)
            if percent_complete >= next_log_percent:
                elapsed = time.time() - start_time
                avg_time = elapsed / i
                eta = int((total - i) * avg_time)
                mem_mb = process.memory_info().rss / 1024 / 1024

                frappe.logger().info(
                    f"📊 {percent_complete}% complete ({i}/{total}) | "
                    f"⏱️ ETA: {eta // 60}m {eta % 60}s | "
                    f"🧠 Mem: {mem_mb:.1f}MB"
                )
                next_log_percent += 10
    except Exception as e:
        frappe.log_error(
            title="Error in sync_user_creation_from_bigquery",
            message=traceback.format_exc()
        )
        frappe.logger().info(f"❌ Error in BigQuery sync: {e}")

    frappe.logger().info(f"🎯 Completed sync — ✅ Updated: {updated} | ❌ Not updated: {not_found}")


CONTACTS_SINCE_BQ_QUERY = f"""
SELECT
  c.phone,
  c.id AS whatsapp_id,
  c.name AS contact_name,
  c.inserted_at,
  c.language,
  pref.value AS preferred_name,
  gen.value AS gender,
  pin.value AS pincode,
  yob.value AS year_of_birth
FROM `{GLIFIC_BQ_DATASET}.contacts` c
LEFT JOIN UNNEST(c.fields) pref ON pref.label = 'preferred_name'
LEFT JOIN UNNEST(c.fields) gen ON gen.label = 'Gender'
LEFT JOIN UNNEST(c.fields) pin ON pin.label = 'pincode'
LEFT JOIN UNNEST(c.fields) yob ON yob.label = 'year_of_birth'
WHERE c.phone IS NOT NULL AND TRIM(c.phone) != ''
  AND c.inserted_at > @since
"""

BQ_PROVISION_COMMIT_EVERY = 10
BQ_PROVISION_ACQUISITION_SOURCE = "Glific"


def _bq_naive_datetime(dt):
	"""BigQuery DATETIME parameters must be timezone-naive."""
	if not dt:
		return None
	dt = get_datetime(dt)
	if dt.tzinfo:
		dt = dt.replace(tzinfo=None)
	return dt


def _get_bq_provision_since_datetime():
	"""Cursor from Solve Ninja Settings; first run defaults to last 24 hours."""
	last_run_str = frappe.db.get_single_value(
		"Solve Ninja Settings", "last_bq_run_frappe"
	)
	if last_run_str:
		return _bq_naive_datetime(last_run_str)
	now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
	return _bq_naive_datetime(now_ist - timedelta(hours=24))


def _load_frappe_mobile_set():
	mobiles = set()
	for row in frappe.get_all(
		"User",
		filters={"name": ["!=", "Administrator"]},
		fields=["mobile_no", "name"],
		limit_page_length=0,
	):
		raw = str(row.get("mobile_no") or "").strip()
		if raw:
			try:
				mobiles.add(validate_and_normalize_mobile(raw))
			except Exception:
				pass
		name = str(row.get("name") or "").strip()
		if name.endswith("@solveninja.org"):
			try:
				mobiles.add(validate_and_normalize_mobile(name.split("@", 1)[0]))
			except Exception:
				pass
	return mobiles


def _user_exists_for_mobile(mobile):
	"""User may exist by mobile_no, email/name, or alternate mobile format."""
	try:
		mobile = validate_and_normalize_mobile(str(mobile).strip())
	except Exception:
		return False
	if frappe.db.exists("User", f"{mobile}@solveninja.org"):
		return True
	if frappe.db.exists("User", {"mobile_no": mobile}):
		return True
	user_name, _, _ = find_user_by_mobile(mobile)
	return bool(user_name)


def _bq_contact_row_to_dict(row):
	if not isinstance(row, dict):
		row = dict(row)
	return row


def _user_data_from_bq_row(row, mobile):
	row = _bq_contact_row_to_dict(row)
	first_name = row.get("preferred_name") or row.get("contact_name") or mobile
	first_name = str(first_name).strip() if first_name else mobile
	return {
		"mobile": mobile,
		"first_name": first_name,
		"wa_id": str(row["whatsapp_id"]) if row.get("whatsapp_id") is not None else None,
		"gender": row.get("gender"),
		"pincode": row.get("pincode"),
		"year_of_birth": row.get("year_of_birth"),
		"acquisition_source_category": BQ_PROVISION_ACQUISITION_SOURCE,
	}


def _create_user_from_bq_contact(mobile, first_name):
	"""Insert User without new_password (avoids Frappe password-strength failures)."""
	user_doc = frappe.get_doc(
		{
			"doctype": "User",
			"email": f"{mobile}@solveninja.org",
			"mobile_no": mobile,
			"mobile": mobile,
			"first_name": first_name,
			"send_welcome_email": 0,
		}
	)
	user_doc.append("roles", {"role": "Solve Ninja"})
	user_doc.insert(ignore_permissions=True)
	return user_doc.name


def _backfill_user_from_bq_contact(mobile, user, row):
	user_data = _user_data_from_bq_row(row, mobile)
	inserted_at = row.get("inserted_at")
	if inserted_at:
		update_user_creation_field(mobile, inserted_at)
	update_user_metadata(user, user_data)
	update_ninja_profile(user, user_data)


def _fetch_bq_contacts_since(since_dt):
	bigquery = get_bigquery_module()
	if not bigquery:
		raise ImportError("google-cloud-bigquery is not installed")
	job_config = bigquery.QueryJobConfig(
		query_parameters=[
			bigquery.ScalarQueryParameter("since", "DATETIME", since_dt),
		]
	)
	client = get_bigquery_client()
	return list(client.query(CONTACTS_SINCE_BQ_QUERY, job_config=job_config).result())


def provision_missing_users_from_bigquery_incremental():
	"""
	Scheduled job: create Frappe users for Glific contacts added since last_bq_run_frappe,
	then backfill creation date, User Metadata, and Ninja Profile.

	Cursor: Solve Ninja Settings.last_bq_run_frappe
	Invoked via daily_long scheduler (same as other Glific BigQuery sync jobs).
	"""
	if not frappe.conf.get("bq_provision_enabled"):
		logger.info(
			"provision_missing_users_from_bigquery_incremental disabled (set bq_provision_enabled=1 in site_config.json to enable)"
		)
		return {"skipped": True, "reason": "disabled"}

	if not bigquery_client_available():
		frappe.log_error(
			"BigQuery unavailable for provision_missing_users_from_bigquery_incremental",
			"BQ User Provision",
		)
		return {"ok": False, "error": "bigquery_unavailable"}

	stats = {
		"since": None,
		"fetched": 0,
		"skipped_existing": 0,
		"created": 0,
		"backfill_ok": 0,
		"failed": 0,
	}

	since_dt = _get_bq_provision_since_datetime()
	stats["since"] = str(since_dt)
	logger.info(f"provision_missing_users_from_bigquery_incremental since={since_dt!r}")

	try:
		setup_bigquery_credentials()
		bq_rows = _fetch_bq_contacts_since(since_dt)
		stats["fetched"] = len(bq_rows)

		frappe_mobiles = _load_frappe_mobile_set()
		max_inserted_at = since_dt

		for row in bq_rows:
			row = _bq_contact_row_to_dict(row)
			raw_phone = str(row.get("phone") or "").strip()
			if not raw_phone:
				continue
			try:
				mobile = validate_and_normalize_mobile(raw_phone)
			except Exception:
				stats["failed"] += 1
				continue

			inserted_at = row.get("inserted_at")
			if inserted_at:
				ins_naive = _bq_naive_datetime(inserted_at)
				if ins_naive and (max_inserted_at is None or ins_naive > max_inserted_at):
					max_inserted_at = ins_naive

			if mobile in frappe_mobiles or _user_exists_for_mobile(mobile):
				stats["skipped_existing"] += 1
				frappe_mobiles.add(mobile)
				continue

			try:
				user_data = _user_data_from_bq_row(row, mobile)
				user = _create_user_from_bq_contact(mobile, user_data["first_name"])
				_backfill_user_from_bq_contact(mobile, user, row)
				frappe_mobiles.add(mobile)
				stats["created"] += 1
				stats["backfill_ok"] += 1

				if stats["created"] % BQ_PROVISION_COMMIT_EVERY == 0:
					frappe.db.commit()
			except Exception:
				stats["failed"] += 1
				frappe.db.rollback()
				frappe.log_error(
					traceback.format_exc(),
					f"BQ user provision failed for {mobile}",
				)

		frappe.db.commit()

		now_naive = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
		if stats["fetched"] == 0:
			cursor_value = now_naive
		elif max_inserted_at and max_inserted_at > since_dt:
			cursor_value = max_inserted_at
		else:
			cursor_value = now_naive
		frappe.db.set_single_value(
			"Solve Ninja Settings", "last_bq_run_frappe", cursor_value
		)
		frappe.db.commit()
		stats["cursor_updated_to"] = str(cursor_value)
		stats["ok"] = True

	except Exception:
		frappe.log_error(
			traceback.format_exc(),
			"provision_missing_users_from_bigquery_incremental",
		)
		stats["ok"] = False
		stats["error"] = "job_failed"
		logger.error("provision_missing_users_from_bigquery_incremental failed", exc_info=True)

	logger.info(f"provision_missing_users_from_bigquery_incremental done: {stats}")
	return stats


BQ_CONTACTS_DISTINCT_PHONES_QUERY = f"""
SELECT DISTINCT phone
FROM `{GLIFIC_BQ_DATASET}.contacts`
WHERE phone IS NOT NULL AND TRIM(phone) != ''
"""

BQ_CONTACTS_BY_PHONES_QUERY = f"""
SELECT
  c.phone,
  ANY_VALUE(c.id) AS whatsapp_id,
  ANY_VALUE(c.name) AS contact_name,
  ANY_VALUE(c.inserted_at) AS inserted_at,
  ANY_VALUE(c.language) AS language,
  ANY_VALUE(pref.value) AS preferred_name,
  ANY_VALUE(gen.value) AS gender,
  ANY_VALUE(pin.value) AS pincode,
  ANY_VALUE(yob.value) AS year_of_birth
FROM `{GLIFIC_BQ_DATASET}.contacts` c
LEFT JOIN UNNEST(c.fields) pref ON pref.label = 'preferred_name'
LEFT JOIN UNNEST(c.fields) gen ON gen.label = 'Gender'
LEFT JOIN UNNEST(c.fields) pin ON pin.label = 'pincode'
LEFT JOIN UNNEST(c.fields) yob ON yob.label = 'year_of_birth'
WHERE c.phone IN UNNEST(@phones)
GROUP BY c.phone
"""


def _normalize_phone_set(phones, country_prefix=None):
	normalized = set()
	for raw in phones:
		p = str(raw or "").strip()
		if not p:
			continue
		try:
			p = validate_and_normalize_mobile(p)
			if country_prefix and not str(p).startswith(str(country_prefix)):
				continue
			normalized.add(p)
		except Exception:
			continue
	return normalized


def _load_bq_phone_set(country_prefix=None):
	bigquery = get_bigquery_module()
	if not bigquery:
		raise ImportError("google-cloud-bigquery is not installed")
	setup_bigquery_credentials()
	client = get_bigquery_client()
	rows = client.query(BQ_CONTACTS_DISTINCT_PHONES_QUERY).result()
	return _normalize_phone_set(
		[str(getattr(r, "phone", "") or "") for r in rows],
		country_prefix=country_prefix,
	)


def get_bq_frappe_user_diff(country_prefix=None):
	"""Return BQ vs Frappe phone diff counts (for pre/post backfill checks)."""
	bq_phones = _load_bq_phone_set(country_prefix=country_prefix)
	frappe_phones = _load_frappe_mobile_set()
	if country_prefix:
		frappe_phones = _normalize_phone_set(frappe_phones, country_prefix=country_prefix)
	missing = sorted(bq_phones - frappe_phones)
	return {
		"bq_unique": len(bq_phones),
		"frappe_unique": len(frappe_phones),
		"missing_in_frappe": len(missing),
		"in_frappe_only": len(frappe_phones - bq_phones),
		"missing_sample": missing[:5],
	}


def _fetch_bq_contacts_for_phones(phones):
	bigquery = get_bigquery_module()
	if not bigquery:
		raise ImportError("google-cloud-bigquery is not installed")
	setup_bigquery_credentials()
	client = get_bigquery_client()
	job_config = bigquery.QueryJobConfig(
		query_parameters=[
			bigquery.ArrayQueryParameter("phones", "STRING", [str(p) for p in phones]),
		]
	)
	rows = client.query(BQ_CONTACTS_BY_PHONES_QUERY, job_config=job_config).result()
	by_phone = {}
	for row in rows:
		row = _bq_contact_row_to_dict(row)
		try:
			mobile = validate_and_normalize_mobile(str(row.get("phone") or "").strip())
		except Exception:
			continue
		by_phone[mobile] = row
	return by_phone


def backfill_missing_users_from_bigquery_batch(
	batch_size=500,
	start_offset=0,
	country_prefix=None,
	acquisition_source=None,
):
	"""
	Create + backfill up to ``batch_size`` users missing in Frappe vs BigQuery.

	``start_offset`` is usually 0; the diff is recomputed each call.
	"""
	if not bigquery_client_available():
		frappe.throw("BigQuery unavailable")

	acquisition_source = acquisition_source or BQ_PROVISION_ACQUISITION_SOURCE
	bq_phones = _load_bq_phone_set(country_prefix=country_prefix)
	frappe_phones = _load_frappe_mobile_set()
	if country_prefix:
		frappe_phones = _normalize_phone_set(frappe_phones, country_prefix=country_prefix)

	missing_all = sorted(bq_phones - frappe_phones)
	phones = missing_all[start_offset : start_offset + batch_size]

	stats = {
		"missing_before": len(missing_all),
		"batch_selected": len(phones),
		"created": 0,
		"backfill_ok": 0,
		"failed": 0,
		"create_failed": [],
		"backfill_failed": [],
	}

	if not phones:
		stats["ok"] = True
		stats["done"] = True
		return stats

	bq_by_phone = _fetch_bq_contacts_for_phones(phones)
	frappe_mobiles = set(frappe_phones)

	for mobile in phones:
		row = bq_by_phone.get(mobile)
		if not row:
			stats["failed"] += 1
			continue

		if mobile in frappe_mobiles or _user_exists_for_mobile(mobile):
			frappe_mobiles.add(mobile)
			continue

		try:
			user_data = _user_data_from_bq_row(row, mobile)
			user_data["acquisition_source_category"] = acquisition_source
			user = _create_user_from_bq_contact(mobile, user_data["first_name"])
			inserted_at = row.get("inserted_at")
			if inserted_at:
				update_user_creation_field(mobile, inserted_at)
			update_user_metadata(user, user_data)
			update_ninja_profile(user, user_data)

			frappe_mobiles.add(mobile)
			stats["created"] += 1
			stats["backfill_ok"] += 1

			if stats["created"] % BQ_PROVISION_COMMIT_EVERY == 0:
				frappe.db.commit()
		except Exception:
			stats["failed"] += 1
			stats["create_failed"].append(mobile)
			frappe.db.rollback()
			frappe.log_error(
				traceback.format_exc(),
				f"BQ backfill batch failed for {mobile}",
			)

	frappe.db.commit()
	stats["missing_after_approx"] = stats["missing_before"] - stats["created"]
	stats["ok"] = True
	stats["done"] = stats["batch_selected"] == 0
	logger.info(f"backfill_missing_users_from_bigquery_batch: {stats}")
	return stats


def run_backfill_missing_users_from_bigquery(
	batch_size=500,
	max_batches=None,
	country_prefix=None,
	acquisition_source=None,
):
	"""
	Run multiple backfill batches until empty or ``max_batches`` is reached.

	Example::

	    bench --site solveninja.org execute \\
	        solve_ninja.api.glific_sync.run_backfill_missing_users_from_bigquery \\
	        --kwargs '{"batch_size": 500, "max_batches": 16}'
	"""
	if not bigquery_client_available():
		frappe.throw("BigQuery unavailable")

	diff_before = get_bq_frappe_user_diff(country_prefix=country_prefix)
	summary = {
		"batch_size": batch_size,
		"max_batches": max_batches,
		"missing_before": diff_before["missing_in_frappe"],
		"batches": [],
		"total_created": 0,
		"total_failed": 0,
	}

	batch_num = 0
	while True:
		if max_batches is not None and batch_num >= max_batches:
			break

		stats = backfill_missing_users_from_bigquery_batch(
			batch_size=batch_size,
			start_offset=0,
			country_prefix=country_prefix,
			acquisition_source=acquisition_source,
		)
		summary["batches"].append(stats)
		summary["total_created"] += stats.get("created", 0)
		summary["total_failed"] += stats.get("failed", 0)
		batch_num += 1

		if stats.get("done") or stats.get("batch_selected", 0) == 0:
			break
		if stats.get("created", 0) == 0 and stats.get("failed", 0) == 0:
			break

	diff_after = get_bq_frappe_user_diff(country_prefix=country_prefix)
	summary["missing_after"] = diff_after["missing_in_frappe"]
	summary["batches_run"] = batch_num
	summary["ok"] = True
	logger.info(f"run_backfill_missing_users_from_bigquery: {summary}")
	return summary