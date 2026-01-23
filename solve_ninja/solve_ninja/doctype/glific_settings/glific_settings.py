# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json
from frappe.utils import logger
import time
import random
from psycopg2.errors import SerializationFailure

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

class GlificSettings(Document):
    def connect_to_glific(self):
        """Connect to Glific using the provided settings."""
        self._validate_connection_fields()
        try:
            return self._get_glific_session()
        except Exception as e:
            frappe.throw(f"Failed to connect to Glific: {str(e)}")

    def refresh_access_token(self):
        """Refresh Glific access token."""
        self._validate_token_fields()
        try:
            return self._refresh_token()
        except Exception as e:
            frappe.throw(f"Failed to refresh token: {str(e)}")


    def _validate_connection_fields(self):
        if not self.phone or not self.get_password() or not self.api_url:
            frappe.throw("Glific Phone, Password, and API URL are required to connect.")

    def _validate_token_fields(self):
        if not self.api_url or not self.access_token or not self.renewal_token:
            frappe.throw("API URL, access token, and renewal token are required.")

    def _make_api_url(self, endpoint):
        base = self.api_url.rstrip("/")
        return f"{base}{endpoint}"

    def _get_headers(self, token=None):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if token:
            headers["Authorization"] = f"{token}"
        return headers

    def _post(self, url, payload, headers, timeout=15):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if response.status_code == 401:
                frappe.log_error(f"Glific 401 Unauthorized: {response.text}", f"Glific API Error ({url})")
                return {"error": "Unauthorized (401): Invalid credentials or token. Please re-authenticate.", "status_code": 401}
            if response.status_code == 403:
                frappe.log_error(f"Glific 403 Forbidden: {response.text}", f"Glific API Error ({url})")
                return {"error": "Forbidden (403): Access denied. Please check your permissions.", "status_code": 403}
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            frappe.log_error(frappe.get_traceback(), f"Glific API Error ({url})")
            return {"error": str(e)}

    def _save_tokens(self, data):
        # Single DocType -> shared row. Protect with a distributed lock.
        lock_name = "glific_settings:token_update"
        lock_timeout = 30  # seconds

        def _attempt_save():
            self.access_token = data["access_token"]
            self.renewal_token = data["renewal_token"]
            self.token_expiry_time = data["token_expiry_time"]
            self.save(ignore_permissions=True)

        # Use redis lock if available
        lock = None
        try:
            lock = frappe.cache().lock(lock_name, timeout=lock_timeout)
        except Exception:
            lock = None  # if lock API not available in your Frappe version

        # If lock exists, use it; otherwise fallback to retry-only
        if lock:
            with lock:
                self._save_with_retry(_attempt_save)
        else:
            self._save_with_retry(_attempt_save)

    def _save_with_retry(self, fn, attempts=5):
        for i in range(attempts):
            try:
                fn()
                return
            except SerializationFailure:
                frappe.db.rollback()
                # small jitter to avoid thundering herd
                time.sleep(0.1 + random.random() * 0.3)
            except Exception:
                # if it's something else, don't mask it
                raise

        frappe.throw("Failed to save Glific tokens due to repeated concurrent updates. Please retry.")

    def _api_post_with_reauth(self, endpoint, payload, headers=None, retry=True):
        """
        Makes a POST request. If 401, tries to refresh token, then retry.
        If still 401, tries full session login, then retry.
        If still 401, throws authentication error.
        """
        url = self._make_api_url(endpoint)
        if headers is None:
            headers = self._get_headers(token=self.access_token)
        response_data = self._post(url, payload, headers)

        if response_data.get("status_code") == 401 and retry:
            # Try refresh_token first
            refresh_result = self._refresh_token()
            if refresh_result.get("success"):
                headers = self._get_headers(token=self.access_token)
                response_data = self._post(url, payload, headers)
                if response_data.get("status_code") != 401:
                    return response_data

            # If still 401, try full login
            login_result = self._get_glific_session()
            if login_result.get("success"):
                headers = self._get_headers(token=self.access_token)
                response_data = self._post(url, payload, headers)
                if response_data.get("status_code") != 401:
                    return response_data

            # If still 401, give up
            frappe.throw("Authentication failed with Glific after retries (refresh & re-login). Please check credentials or renewal token.")

        return response_data

    def _get_glific_session(self):
        """Login and save tokens."""
        url = self._make_api_url("/api/v1/session")
        headers = self._get_headers()
        payload = {
            "user": {
                "phone": self.phone,
                "password": self.get_password()
            }
        }
        response_data = self._post(url, payload, headers)
        if response_data.get("status_code") == 401:
            frappe.throw("Glific authentication failed: Unauthorized (401). Please check your credentials.")
        if response_data.get("status_code") == 403:
            frappe.throw("Glific authentication failed: Forbidden (403). Please check your permissions.")

        data = (response_data or {}).get("data")
        if data and data.get("access_token"):
            self._save_tokens(data)
            return {"success": True, "msg": "Connected to Glific"}
        return {"success": False, "msg": f"Invalid response: {json.dumps(response_data)}"}

    def _refresh_token(self):
        """Refresh tokens using renewal token."""
        url = self._make_api_url("/api/v1/session/renew")
        headers = self._get_headers(token=self.renewal_token)
        payload = {
            "access_token": self.access_token,
            "renewal_token": self.renewal_token
        }
        response_data = self._post(url, payload, headers)
        if response_data.get("status_code") == 401:
            return {"success": False, "msg": "401 during token refresh"}
        if response_data.get("status_code") == 403:
            return {"success": False, "msg": "403 during token refresh"}

        data = (response_data or {}).get("data")
        if data and data.get("access_token"):
            self._save_tokens(data)
            return {"success": True, "msg": "Token refreshed"}
        return {"success": False, "msg": f"Invalid response: {json.dumps(response_data)}"}


    def call_some_protected_api(self, custom_payload):
        """
        Example method: use this pattern for all API calls needing authentication.
        This method will retry if token is expired/invalid.
        """
        endpoint = "/api/v1/some_protected_resource"
        return self._api_post_with_reauth(endpoint, custom_payload)
    
    def send_hsm_message(self, receiver_id, template_id, parameters=None):
        payload = {
            "query": """
                mutation sendHsmMessage($templateId: ID!, $receiverId: ID!, $parameters: [String]) {
                    sendHsmMessage(templateId: $templateId, receiverId: $receiverId, parameters: $parameters) {
                        message {
                            id
                            body
                            isHsm
                        }
                        errors {
                            key
                            message
                        }
                    }
                }
            """,
            "variables": {
                "templateId": int(template_id),
                "receiverId": int(receiver_id),
                "parameters": parameters or []
            }
        }
        return self._api_graphql_post_with_reauth(payload)

    def create_contact(self, phone, name=None):
        """
        Create a new contact in Glific
        """
        payload = {
            "query": """
                mutation createContact($phone: String!, $name: String) {
                    createContact(phone: $phone, name: $name) {
                        contact {
                            id
                            name
                            phone
                        }
                        errors {
                            key
                            message
                        }
                    }
                }
            """,
            "variables": {
                "phone": phone,
                "name": name or f"User {phone}"
            }
        }
        return self._api_graphql_post_with_reauth(payload)

    def send_whatsapp_message(self, receiver_id, message):
        """
        Send a regular WhatsApp message (not HSM template)
        """
        payload = {
            "query": """
                mutation sendMessage($receiverId: ID!, $message: String!) {
                    sendMessage(receiverId: $receiverId, message: $message) {
                        message {
                            id
                            body
                            isHsm
                        }
                        errors {
                            key
                            message
                        }
                    }
                }
            """,
            "variables": {
                "receiverId": int(receiver_id),
                "message": message
            }
        }
        return self._api_graphql_post_with_reauth(payload)

    def resume_glific_flow(self,flow_id,contact_id,result):
        #logger.info(f"Resuming Glific flow with flow_id: {flow_id}, contact_id: {contact_id}, result: {result}")
        payload = {
                "query": """
                    mutation resumeContactFlow($flowId: ID!, $contactId: ID!, $result: Json!) {
                        resumeContactFlow(flowId: $flowId, contactId: $contactId, result: $result) {
                            success
                            errors {
                                key
                                message
                            }
                        }
                    }
                """,
                "variables": {
                    "flowId": flow_id,
                    "contactId": contact_id,
                    "result": json.dumps({"result":result})
                }
        }
        return self._api_graphql_post_with_reauth(payload)
    
    def get_session_templates(self):
        payload = {
            "query": """
                query getSessionTemplates {
                    sessionTemplates {
                        id
                        label
                        body
                        status
                    }
                }
            """
        }
        return self._api_graphql_post_with_reauth(payload)

    def get_contact(self, contact_id):
        payload = {
            "query": """
                query getContact($id: ID!) {
                    contact(id: $id) {
                        contact {
                            id
                            name
                            phone
                            status
                        }
                    }
                }
            """,
            "variables": {
                "id": int(contact_id)
            }
        }
        return self._api_graphql_post_with_reauth(payload)

    def get_contact_by_phone(self, phone):
        """
        Fetch contact details from Glific using phone number.

        Args:
            phone (str): Phone number in international format (e.g., '919876543210')

        Returns:
            dict: Contact details from Glific
        """
        if not phone:
            frappe.throw("Phone number is required")

        payload = {
            "query": """
                query contactByPhone($phone: String!) {
                contactByPhone(phone: $phone) {
                    contact {
                    id
                    name
                    optinTime
                    optoutTime
                    phone
                    bspStatus
                    status
                    lastMessageAt
                    fields
                    settings
                    }
                }
                }
            """,
            "variables": {
                "phone": phone
            }
        }

        return self._api_graphql_post_with_reauth(payload)

    def get_flow(self, flow_id):
        """
        Fetch flow details from Glific using flow ID.

        Args:
            flow_id (int or str): Flow ID

        Returns:
            dict: Flow details from Glific including id, name, and keywords
        """
        if not flow_id:
            frappe.throw("Flow ID is required")

        payload = {
            "query": """
                query flow($id: ID!) {
                    flow(id: $id) {
                        flow {
                            id
                            name
                            keywords
                        }
                    }
                }
            """,
            "variables": {
                "id": int(flow_id) if isinstance(flow_id, str) else flow_id
            }
        }
        return self._api_graphql_post_with_reauth(payload)

    def update_flow(self, flow_id, name=None, keywords=None, remove_keywords=None):
        """
        Update flow in Glific. Adds or removes keywords from existing keywords list.
        If name is not provided, preserves existing flow name.

        Args:
            flow_id (int or str): Flow ID
            name (str, optional): Flow name. If None, uses existing name.
            keywords (list, optional): Keywords to add to existing keywords list.
            remove_keywords (list, optional): Keywords to remove from existing keywords list.

        Returns:
            dict: Updated flow details from Glific
        """
        if not flow_id:
            frappe.throw("Flow ID is required")

        # First, get existing flow data
        existing_flow_response = self.get_flow(flow_id)
        
        # Extract existing flow data
        existing_flow = None
        if existing_flow_response and "data" in existing_flow_response:
            existing_flow = existing_flow_response.get("data", {}).get("flow", {}).get("flow")
        
        if not existing_flow:
            frappe.throw(f"Flow with ID {flow_id} not found")

        # Use existing name if name not provided
        flow_name = name if name is not None else existing_flow.get("name", "")
        
        # Start with existing keywords (Glific stores keywords in lowercase)
        existing_keywords = existing_flow.get("keywords") or []
        if not isinstance(existing_keywords, list):
            existing_keywords = []
        
        # Normalize existing keywords to lowercase for comparison
        existing_keywords_lower = [kw.lower() if isinstance(kw, str) else kw for kw in existing_keywords]
        
        # Remove keywords first if specified
        if remove_keywords:
            if not isinstance(remove_keywords, list):
                remove_keywords = [remove_keywords]
            # Convert remove_keywords to lowercase for comparison
            remove_keywords_lower = [kw.lower() if isinstance(kw, str) else kw for kw in remove_keywords]
            # Build new list excluding keywords to remove (case-insensitive)
            merged_keywords = []
            for i, existing_kw in enumerate(existing_keywords):
                existing_kw_lower = existing_keywords_lower[i]
                if existing_kw_lower not in remove_keywords_lower:
                    merged_keywords.append(existing_kw)
        else:
            merged_keywords = list(existing_keywords)  # Keep original format from Glific
        
        # Add new keywords if specified (convert to lowercase for Glific)
        if keywords:
            if not isinstance(keywords, list):
                keywords = [keywords]
            # Convert merged_keywords to lowercase list for comparison
            merged_keywords_lower = [kw.lower() if isinstance(kw, str) else kw for kw in merged_keywords]
            # Add new keywords, avoiding duplicates (compare in lowercase)
            for keyword in keywords:
                keyword_lower = keyword.lower() if isinstance(keyword, str) else keyword
                if keyword_lower not in merged_keywords_lower:
                    merged_keywords.append(keyword_lower)
                    merged_keywords_lower.append(keyword_lower)

        payload = {
            "query": """
                mutation updateFlow($id: ID!, $input: FlowInput!) {
                    updateFlow(id: $id, input: $input) {
                        flow {
                            id
                            name
                            keywords
                        }
                        errors {
                            key
                            message
                        }
                    }
                }
            """,
            "variables": {
                "id": str(flow_id),
                "input": {
                    "name": flow_name,
                    "keywords": merged_keywords
                }
            }
        }
        return self._api_graphql_post_with_reauth(payload)

    def _api_graphql_post_with_reauth(self, payload, retry=True):
        """
        Makes a POST to the /api endpoint with GraphQL payload. Handles 401 by refreshing token or re-login.
        Args:
            payload (dict): GraphQL payload with `query` and `variables`.
            retry (bool): Whether to retry on 401 errors.
        Returns:
            dict: JSON response from Glific API
        """
        url = self._make_api_url("/api")
        headers = self._get_headers(token=self.access_token)
        # logger.info(f"Making GraphQL POST to {url} with payload: {json.dumps(payload)}")
        # logger.info(f"Using headers: {json.dumps(headers)}")
        # logger.info(f"Payload: {payload}")
        response_data = self._post(url, payload, headers)

        if response_data.get("status_code") == 401 and retry:
            refresh_result = self._refresh_token()
            if refresh_result.get("success"):
                headers = self._get_headers(token=self.access_token)
                response_data = self._post(url, payload, headers)
                if response_data.get("status_code") != 401:
                    return response_data

            login_result = self._get_glific_session()
            if login_result.get("success"):
                headers = self._get_headers(token=self.access_token)
                response_data = self._post(url, payload, headers)
                if response_data.get("status_code") != 401:
                    return response_data

            frappe.log_error(json.dumps(response_data), "GraphQL Auth Retry Failed")
            frappe.throw("Authentication failed with Glific after retries (refresh & re-login).")

        """ if response_data.get("status_code") == 200:
            logger.info(f"GraphQL response: {json.dumps(response_data)}") """
        
        return response_data


@frappe.whitelist()
def connect_to_glific():
    glific_settings = frappe.get_doc("Glific Settings")
    return glific_settings.connect_to_glific()
