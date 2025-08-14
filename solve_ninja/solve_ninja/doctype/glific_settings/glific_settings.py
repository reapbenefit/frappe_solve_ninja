# Copyright (c) 2025, ReapBenefit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json
from frappe.utils import logger

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
        self.access_token = data["access_token"]
        self.renewal_token = data["renewal_token"]
        self.token_expiry_time = data["token_expiry_time"]
        self.save(ignore_permissions=True)

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

    def resume_glific_flow(self,flowId,contactId,result):
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
                "flowId": flowId,
                "contactId": contactId,
                "result": json.dumps(result)
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
        logger.info(f"Making GraphQL POST to {url} with payload: {json.dumps(payload)}")
        logger.info(f"Using headers: {json.dumps(headers)}")
        logger.info(f"Current access token: {self.access_token}")
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

        return response_data


@frappe.whitelist()
def connect_to_glific():
    glific_settings = frappe.get_doc("Glific Settings")
    return glific_settings.connect_to_glific()
