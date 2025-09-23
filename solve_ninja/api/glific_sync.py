import os
import frappe
from google.cloud import bigquery
from frappe.utils import logger
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from frappe.utils import get_datetime
import time
import psutil
from solve_ninja.api.user import update_user_creation_field

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)


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

    credentials_path = frappe.conf.get("google_credentials_path")
    if not credentials_path:
        frappe.log_error("❌ google_credentials_path missing in site_config.json")
        logger.error("❌ google_credentials_path missing in site_config.json")
        return

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

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

        client = bigquery.Client()
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

    credentials_path = frappe.conf.get("google_credentials_path")
    if not credentials_path:
        frappe.log_error("❌ google_credentials_path missing in site_config.json")
        return

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    updated = 0
    not_found = 0

    query = """
       select distinct phone,inserted_at from `glific-301906.918095500118.contacts`
    """

    try:
        client = bigquery.Client()
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