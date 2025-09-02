import frappe
import io
import frappe
import pandas as pd
from frappe.utils.file_manager import get_file


@frappe.whitelist()
def update_city_state(state: str, city: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float):
    """
    Update rows in 'Events Metadata' where latitude/longitude fall within the given bounding box.

    Args:
        state (str): State name to set
        city (str): City name to set
        lat_min (float): Minimum latitude
        lat_max (float): Maximum latitude
        lon_min (float): Minimum longitude
        lon_max (float): Maximum longitude

    Returns:
        dict: Summary with affected row count
    """
    query = """
        UPDATE `Events Metadata`
        SET state = %(state)s,
            city  = %(city)s
        WHERE latitude BETWEEN %(lat_min)s AND %(lat_max)s
          AND longitude BETWEEN %(lon_min)s AND %(lon_max)s
        RETURNING event_id
    """

    updated = frappe.db.sql(query, {
        "state": state,
        "city": city,
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max
    }, as_dict=True)

    frappe.db.commit()

    return {
        "updated_rows": len(updated),
        "city": city,
        "state": state,
        "event_ids": [r["event_id"] for r in updated]
    }

@frappe.whitelist()
def bulk_update_city_state_pandas(file: str = None, csv_text: str = None, dry_run: int = 0):
    """
    Bulk update 'Events Metadata' by reading a CSV with pandas and reusing update_city_state().

    CSV must have columns:
        State, City, Lat_Min, Lat_Max, Lon_Min, Lon_Max

    Args:
        file_url (str, optional): Path to file (e.g. '/files/city_bboxes.csv')
        csv_text (str, optional): Raw CSV content
        dry_run (int, optional): If 1, simulate only (no DB updates).

    Returns:
        dict: Summary of updates
    """
    if not file and not csv_text:
        raise frappe.ValidationError("Provide either 'file' or 'csv_text'.")

    # Load CSV into pandas DataFrame
    if file:
        file = frappe.get_doc("File", file)
        df = pd.read_csv(file.get_full_path())
    else:
        df = pd.read_csv(io.StringIO(csv_text))

    required_cols = ["State", "City", "Lat_Min", "Lat_Max", "Lon_Min", "Lon_Max"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise frappe.ValidationError(f"CSV missing required columns: {', '.join(missing)}")

    results, errors = [], []
    updated_total = 0

    for idx, row in df.iterrows():
        try:
            state = str(row["State"]).strip()
            city = str(row["City"]).strip()
            lat_min = float(row["Lat_Min"])
            lat_max = float(row["Lat_Max"])
            lon_min = float(row["Lon_Min"])
            lon_max = float(row["Lon_Max"])

            if dry_run:
                results.append({
                    "row_index": int(idx),
                    "state": state,
                    "city": city,
                    "simulated": True
                })
                continue

            res = update_city_state(state, city, lat_min, lat_max, lon_min, lon_max)
            updated_total += res["updated_rows"]
            results.append({
                "row_index": int(idx),
                "state": state,
                "city": city,
                "updated_rows": res["updated_rows"],
                "event_ids": res["event_ids"],
            })

        except Exception as e:
            errors.append({"row_index": int(idx), "error": str(e), "row": row.to_dict()})

    return {
        "total_rows": len(df),
        "updated_total": updated_total,
        "dry_run": bool(dry_run),
        "results": results,
        "errors": errors,
    }