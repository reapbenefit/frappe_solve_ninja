import frappe
from frappe import qb
from frappe.query_builder.functions import Count, Sum
from samaaja.api.common import custom_response

@frappe.whitelist(allow_guest=True)
def get_subcategories_user_tag_wise_stats():
    user_tags_stats = {}
    query = """SELECT subcategory, count(subcategory) FROM public."tabLocation" as location
				LEFT JOIN "tabEvents" as events
				ON location.name = events.location  where events.name IS NOT NULL group by subcategory """
    subcategories_stats_list = frappe.db.sql(query, as_dict=True)
    
    # Convert list to dictionary for easier lookup
    subcategories_stats = {}
    for stat in subcategories_stats_list:
        subcategories_stats[stat["subcategory"]] = stat["count"]

    query = """SELECT name, _user_tags FROM "tabEvent Sub Category" """
    subcategories = frappe.db.sql(query, as_dict=True)
    for subcategory in subcategories:
        if subcategory["_user_tags"] is None:
            continue
        user_tags = subcategory["_user_tags"].split(",")

        # Get count for this subcategory, default to 0 if not found
        subcategory_count = subcategories_stats.get(subcategory["name"], 0)

        for user_tag in user_tags:
            if user_tag == "hidden":
                continue
            if user_tag == "":
                continue

            subcategory_item = {
                subcategory["name"]: subcategory_count
            }
            is_other = subcategory["name"] == "Other"

            if user_tag in user_tags_stats:
                if is_other:
                    # Append "Other" at the end
                    user_tags_stats[user_tag].append(subcategory_item)
                else:
                    # Insert before any "Other" items, or append if no "Other" exists
                    other_index = next(
                        (i for i, item in enumerate(user_tags_stats[user_tag]) if "Other" in item),
                        len(user_tags_stats[user_tag])
                    )
                    user_tags_stats[user_tag].insert(other_index, subcategory_item)
            else:
                user_tags_stats[user_tag] = [subcategory_item]

    # Reorder dictionary to ensure "Other" user_tag is at the end
    if "Other" in user_tags_stats:
        other_data = user_tags_stats.pop("Other")
        user_tags_stats["Other"] = other_data

    return user_tags_stats


@frappe.whitelist(allow_guest=True)
def get_addresses():
    """
    Get addresses/events with optional field selection and filtering.
    
    Query parameters:
    - fields: JSON array of field names to select (optional)
    - event_id: Filter by specific event ID (optional)
    - category: Filter by category (user_tag) (optional)
    - subCategory: Filter by subcategory name (optional)
    """
    import json
    
    available_fields = {
        'event_id': 'events.name AS event_id',
        'latitude': 'CAST(location.latitude AS FLOAT8) AS latitude',
        'longitude': 'CAST(location.longitude AS FLOAT8) AS longitude',
        'address': 'address',
        'city': 'city',
        'district': 'district',
        'state': 'state',
        'title': 'events.title AS title',
        'type': 'events.type AS type',
        'subcategory': 'events.subcategory AS subcategory',
        'status': 'events.status AS status',
        'description': 'events.description AS description',
        'location': 'events.location AS location',
        'impacted_entity_count': 'events.impacted_entity_count AS impacted_entity_count',
        'attachment1': 'events.attachment1 AS attachment1',
        'attachment2': 'events.attachment2 AS attachment2',
    }
    
    # Get query parameters
    params = frappe.form_dict
    fields_list = []
    query_params = []
    
    # Handle fields parameter
    if params.get('fields'):
        try:
            fields_list = json.loads(params.get('fields'))
            if isinstance(fields_list, list):
                fields_list = [available_fields[field] for field in fields_list if field in available_fields]
        except (json.JSONDecodeError, TypeError):
            fields_list = []
    
    # Build fields string
    if fields_list:
        fields_str = ', '.join(fields_list)
    else:
        fields_str = ', '.join(available_fields.values())
    
    # Build base query
    query = f"""SELECT {fields_str}
    FROM public."tabLocation" as location
    LEFT JOIN public."tabEvents" as events
    ON location.name = events.location"""
    
    # Add WHERE clause
    where_clauses = []
    
    if params.get('event_id'):
        where_clauses.append('events.name = %s')
        query_params.append(params.get('event_id'))
    else:
        where_clauses.append('events.name IS NOT NULL')
    
    # Add category filter
    if params.get('category'):
        where_clauses.append("""events.subcategory IN (
            SELECT DISTINCT(name) FROM public."tabEvent Sub Category" tesc 
            WHERE "_user_tags" LIKE %s
        )""")
        query_params.append(f"%{params.get('category')}%")
    
    # Add subCategory filter (supports multiple values)
    if params.get('subCategory'):
        subcategory_value = params.get('subCategory')
        subcategories = []
        
        # Try to parse as JSON array first
        try:
            parsed = json.loads(subcategory_value)
            if isinstance(parsed, list):
                subcategories = parsed
            else:
                subcategories = [subcategory_value]
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat as comma-separated string
            if ',' in subcategory_value:
                subcategories = [s.strip() for s in subcategory_value.split(',')]
            else:
                subcategories = [subcategory_value]
        
        # Remove empty strings
        subcategories = [s for s in subcategories if s]
        
        if subcategories:
            if len(subcategories) == 1:
                # Single value - use LIKE for partial matching
                where_clauses.append('events.subcategory LIKE %s')
                query_params.append(f"%{subcategories[0]}%")
            else:
                # Multiple values - use IN clause with exact matching
                placeholders = ', '.join(['%s'] * len(subcategories))
                where_clauses.append(f'events.subcategory IN ({placeholders})')
                query_params.extend(subcategories)
    
    # Combine WHERE clauses
    if where_clauses:
        query += ' WHERE ' + ' AND '.join(where_clauses)
    
    try:
        # Execute query
        if query_params:
            events = frappe.db.sql(query, tuple(query_params), as_dict=True)
        else:
            events = frappe.db.sql(query, as_dict=True)
        
        return custom_response(
            message="Success",
            data=events,
            status_code=200
        )
    except Exception as err:
        frappe.log_error(f"Error in get_addresses: {str(err)}", "get_addresses")
        return custom_response(
            message="Internal Server Error",
            data=None,
            status_code=500,
            error=str(err)
        )