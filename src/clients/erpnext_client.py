"""ERPNext API client with authentication and error handling."""
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
import json
import logging
from src.config import settings

logger = logging.getLogger(__name__)


class ERPNextClientError(Exception):
    """Base exception for ERPNext client errors."""

    pass


class ERPNextClient:
    """
    HTTP client for ERPNext REST API.

    Handles authentication, error handling, and provides typed methods
    for common ERPNext operations needed by OTP service.
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        api_secret: str = None,
        timeout: float = 30.0,
    ):
        """Initialize ERPNext client with authentication."""
        self.base_url = (base_url or settings.erpnext_base_url).rstrip("/")
        self.api_key = api_key or settings.erpnext_api_key
        self.api_secret = api_secret or settings.erpnext_api_secret
        self.timeout = timeout

        # Create httpx client with auth headers
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"token {self.api_key}:{self.api_secret}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and errors."""
        try:
            response.raise_for_status()
            data = response.json()

            # ERPNext wraps responses in different ways
            if isinstance(data, dict):
                # Check for ERPNext error messages
                if data.get("exc_type") or data.get("exception"):
                    error_msg = data.get("exception") or data.get("exc_type")
                    raise ERPNextClientError(f"ERPNext error: {error_msg}")

                # Return the data or message field
                return data.get("data") or data.get("message") or data

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise ERPNextClientError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise ERPNextClientError("Request to ERPNext timed out") from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ERPNextClientError(f"Unexpected error: {str(e)}") from e

    def get_stock_balance(self, item_code: str, warehouse: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current stock balance for an item.

        Returns:
            {
                "item_code": "ITEM-001",
                "warehouse": "Stores - WH",
                "actual_qty": 10.0,
                "reserved_qty": 2.0,
                "available_qty": 8.0
            }
        """
        params = {"item_code": item_code}
        if warehouse:
            params["warehouse"] = warehouse

        response = self.client.get("/api/method/erpnext.stock.get_item_details", params=params)
        return self._handle_response(response)

    def get_bin_details(self, item_code: str, warehouse: str) -> Dict[str, Any]:
        """
        Get bin (stock ledger) details for item in warehouse.

        Alternative method using frappe.client.get_list
        """
        params = {
            "filters": json.dumps([["item_code", "=", item_code], ["warehouse", "=", warehouse]]),
            "fields": json.dumps(["actual_qty", "reserved_qty", "projected_qty", "warehouse"]),
        }

        response = self.client.get("/api/resource/Bin", params=params)
        data = self._handle_response(response)

        # ERPNext returns data wrapped in a 'data' key
        if isinstance(data, dict) and "data" in data:
            bin_list = data["data"]
        elif isinstance(data, list):
            bin_list = data
        else:
            bin_list = []

        # Return first bin or empty result
        if bin_list and len(bin_list) > 0:
            return bin_list[0]

        return {
            "item_code": item_code,
            "warehouse": warehouse,
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0,
        }

    def get_incoming_purchase_orders(self, item_code: str) -> List[Dict[str, Any]]:
        """
        Get open purchase orders with expected delivery for an item.

        Returns list of:
            {
                "po_id": "PO-00123",
                "item_code": "ITEM-001",
                "qty": 5.0,
                "received_qty": 0.0,
                "pending_qty": 5.0,
                "schedule_date": "2026-02-03"
            }
        """
        params = {
            "filters": json.dumps(
                [
                    ["item_code", "=", item_code],
                    ["docstatus", "=", 1],  # Submitted
                    ["qty", ">", "received_qty"],  # Not fully received
                ]
            ),
            "fields": json.dumps(
                [
                    "parent",
                    "item_code",
                    "qty",
                    "received_qty",
                    "schedule_date",
                    "warehouse",
                ]
            ),
            "order_by": "schedule_date asc",
            "limit_page_length": 500,
        }

        response = self.client.get("/api/resource/Purchase Order Item", params=params)
        items = self._handle_response(response)

        # Transform to our format
        result = []
        for item in items if isinstance(items, list) else []:
            result.append(
                {
                    "po_id": item.get("parent"),
                    "item_code": item.get("item_code"),
                    "qty": item.get("qty", 0),
                    "received_qty": item.get("received_qty", 0),
                    "pending_qty": item.get("qty", 0) - item.get("received_qty", 0),
                    "schedule_date": item.get("schedule_date"),
                    "warehouse": item.get("warehouse"),
                }
            )

        return result

    def get_sales_order(self, sales_order_id: str) -> Dict[str, Any]:
        """Get Sales Order details."""
        response = self.client.get(f"/api/resource/Sales Order/{sales_order_id}")
        return self._handle_response(response)

    def get_sales_order_list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        customer: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Sales Orders list from ERPNext via Resource API.

        Args:
            limit: Max number of results (default 20, max 100)
            offset: Number of records to skip for pagination (default 0)
            status: Filter by status (e.g., 'Draft', 'To Deliver')
            customer: Filter by customer name
            from_date: Filter transaction_date >= this date (ISO format)
            to_date: Filter transaction_date <= this date (ISO format)
            search: Search in SO name or customer name

        Returns:
            List of Sales Order dictionaries with minimal fields

        Note:
            Uses Resource API (/api/resource/Sales Order), NOT method API.
            Do NOT pass doctype in params - it's in the URL path.
        """
        filters: List[List[Any]] = [
            ["docstatus", "in", [0, 1]],  # Draft or Submitted
        ]

        if status:
            filters.append(["status", "=", status])

        if customer:
            filters.append(["customer", "=", customer])

        if from_date:
            filters.append(["transaction_date", ">=", from_date])

        if to_date:
            filters.append(["transaction_date", "<=", to_date])

        # CRITICAL: Do NOT include 'doctype' in params when using Resource API
        # The doctype is already in the URL path: /api/resource/Sales Order
        params: Dict[str, Any] = {
            "filters": json.dumps(filters),
            "fields": json.dumps(
                [
                    "name",
                    "customer",
                    "transaction_date",
                    "delivery_date",
                    "status",
                    "grand_total",
                ]
            ),
            "order_by": "transaction_date desc",
            "limit_page_length": min(limit, 100),
            "limit_start": offset,
        }

        if search:
            params["or_filters"] = json.dumps(
                [["name", "like", f"%{search}%"], ["customer", "like", f"%{search}%"]]
            )

        response = self.client.get("/api/resource/Sales Order", params=params)
        data = self._handle_response(response)

        # Resource API returns list directly or wrapped in "data"
        if isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], list) else []
        return data if isinstance(data, list) else []

    def add_comment_to_doc(self, doctype: str, docname: str, comment_text: str) -> Dict[str, Any]:
        """Add a comment to a document."""
        data = {
            "reference_doctype": doctype,
            "reference_name": docname,
            "content": comment_text,
            "comment_type": "Comment",
        }

        response = self.client.post("/api/resource/Comment", json=data)
        return self._handle_response(response)

    def update_sales_order_custom_field(
        self, sales_order_id: str, field_name: str, value: Any
    ) -> Dict[str, Any]:
        """Update a custom field on Sales Order."""
        data = {field_name: value}

        response = self.client.put(f"/api/resource/Sales Order/{sales_order_id}", json=data)
        return self._handle_response(response)

    def create_material_request(
        self, items: List[Dict[str, Any]], priority: str = "Medium"
    ) -> Dict[str, Any]:
        """
        Create a Material Request for procurement.

        Args:
            items: List of items with item_code, qty, schedule_date
            priority: High, Medium, Low
        """
        mr_items = []
        for item in items:
            mr_items.append(
                {
                    "item_code": item["item_code"],
                    "qty": item["qty_needed"],
                    "schedule_date": item["required_by"],
                    "warehouse": item.get("warehouse", settings.default_warehouse),
                }
            )

        data = {
            "doctype": "Material Request",
            "material_request_type": "Purchase",
            "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "schedule_date": items[0]["required_by"] if items else None,
            "priority": priority,
            "items": mr_items,
        }

        response = self.client.post("/api/resource/Material Request", json=data)
        result = self._handle_response(response)

        # ERPNext returns the created doc
        if isinstance(result, dict):
            return result

        return {"name": "Unknown"}

    def health_check(self) -> bool:
        """Check if ERPNext is reachable and authenticated."""
        try:
            response = self.client.get("/api/method/frappe.auth.get_logged_user")
            self._handle_response(response)
            return True
        except Exception as e:
            logger.error(f"ERPNext health check failed: {e}")
            return False

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
