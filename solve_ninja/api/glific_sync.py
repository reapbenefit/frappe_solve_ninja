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

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

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
                c.id AS whatsapp_id
            FROM `glific-301906.918095500118.messages` m
            LEFT JOIN `glific-301906.918095500118.contacts` c
                ON m.contact_phone = c.phone
            WHERE m.flow = 'inbound'
            {filter_clause}
        ) x
        GROUP BY contact_phone
    """

    try:
        filter_clause = ""
        query_params = []

        if last_successful_run:
            logger.info("📌 Applying filter by last_successful_run timestamp")
            filter_clause = "AND TIMESTAMP(m.inserted_at) > @last_run"
            query_params.append(
                bigquery.ScalarQueryParameter("last_run", "TIMESTAMP", last_successful_run)
            )
        else:
            logger.info("⚠️ No last_successful_run timestamp found, skipping filter")

        query = query_base.format(filter_clause=filter_clause)
        job_config = bigquery.QueryJobConfig(query_parameters=query_params) if query_params else None

        client = bigquery.Client()
        results = client.query(query, job_config=job_config).result()
        updates = [(row["contact_phone"], row["last_active_date"], row["whatsapp_id"]) for row in results]

        logger.info(f"✅ Total rows from BigQuery: {len(updates)}")

        total = len(updates)
        next_log_percent = 10
        start_time = time.time()
        process = psutil.Process()

        for i, (contact_phone, last_active_date, whatsapp_id) in enumerate(updates, start=1):
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

            doc = frappe.get_doc("Ninja Profile", profiles[0]["name"])
            doc.last_active_date_bot = last_active_date
            doc.wa_id = whatsapp_id
            doc.save(ignore_permissions=True)
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