"""ERPNext API client with authentication and error handling."""
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging
from src.config import settings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import time

logger = logging.getLogger(__name__)


class ERPNextClientError(Exception):
    """Base exception for ERPNext client errors."""

    pass


class CircuitBreaker:
    """Simple circuit breaker pattern for preventing cascading failures."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def record_failure(self):
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def record_success(self):
        """Record a successful request."""
        self.failure_count = 0
        self.state = "closed"

    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "closed":
            return False

        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time and time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
                self.failure_count = 0
                logger.info("Circuit breaker half-open, attempting recovery")
                return False
            return True

        return False


# Global HTTP client with connection pooling
_global_client = None
_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)


def get_global_client() -> httpx.Client:
    """Get or initialize global HTTP client with connection pooling."""
    global _global_client
    if _global_client is None:
        limits = httpx.Limits(
            max_keepalive_connections=50,
            max_connections=100,
            keepalive_expiry=30.0,
        )
        _global_client = httpx.Client(
            limits=limits,
            timeout=httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0),
            http2=False,  # Ensure HTTP/1.1 for better compatibility
        )
        logger.info("Global HTTP client initialized with connection pooling")
    return _global_client


class ERPNextClient:
    """
    HTTP client for ERPNext REST API.

    Handles authentication, error handling, and provides typed methods
    for common ERPNext operations needed by OTP service.

    Uses global connection pooling for stability and reuses connections.
    Includes retry logic with exponential backoff and circuit breaker pattern.
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

        # Use global client instead of creating new ones
        self.client = get_global_client()
        self.auth_header = f"token {self.api_key}:{self.api_secret}"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ReadTimeout, httpx.ConnectError, httpx.NetworkError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying request (attempt {retry_state.attempt_number})..."
        ),
    )
    def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL or relative path
            **kwargs: Additional arguments for httpx request

        Raises:
            ERPNextClientError: On all errors after retries exhausted
        """
        # Check circuit breaker
        if _circuit_breaker.is_open():
            raise ERPNextClientError("Circuit breaker is open - service temporarily unavailable")

        try:
            # Ensure headers are set
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"].update(self._get_headers())

            # Make request
            response = self.client.request(method, url, **kwargs)
            
            # Check for HTTP errors (4xx and 5xx)
            if response.status_code >= 400:
                response.raise_for_status()
            else:
                _circuit_breaker.record_success()
            
            return response

        except (httpx.ReadTimeout, httpx.ConnectError, httpx.NetworkError) as e:
            _circuit_breaker.record_failure()
            logger.error(f"Network error: {e}")
            raise
        except httpx.HTTPStatusError as e:
            _circuit_breaker.record_failure()
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise ERPNextClientError(f"HTTP {e.response.status_code}: {e.response.text}") from e

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and errors."""
        try:
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

        except ERPNextClientError:
            raise
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

        url = f"{self.base_url}/api/method/erpnext.stock.get_item_details"
        response = self._make_request("GET", url, params=params)
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

        url = f"{self.base_url}/api/resource/Bin"
        response = self._make_request("GET", url, params=params)
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

    def get_value(
        self,
        doctype: str,
        filters: Dict[str, str] = None,
        fieldname: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a single document value from ERPNext."""
        params: Dict[str, Any] = {}
        if filters:
            params["filters"] = json.dumps(filters)
        if fieldname:
            params["fields"] = json.dumps(fieldname)
        url = f"{self.base_url}/api/resource/{doctype}"
        try:
            response = self._make_request("GET", url, params=params)
            data = self._handle_response(response)
            if isinstance(data, dict) and "data" in data:
                result_list = data["data"]
            elif isinstance(data, list):
                result_list = data
            else:
                return None
            if result_list and len(result_list) > 0:
                return result_list[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching {doctype}: {e}")
            raise

    def get_incoming_purchase_orders(self, item_code: str) -> List[Dict[str, Any]]:
        """
        Get open purchase orders with expected delivery for an item using parent Purchase Order doctype.

        Returns list of:
            {
                "po_id": "PO-00123",
                "item_code": "ITEM-001",
                "qty": 5.0,
                "received_qty": 0.0,
                "pending_qty": 5.0,
                "schedule_date": "2026-02-03",
                "warehouse": "Stores - WH"
            }
        """
        params = {
            "filters": json.dumps([
                ["docstatus", "=", 1],
                ["status", "in", ["To Receive and Bill", "To Receive"]],
            ]),
            "fields": json.dumps(["name", "schedule_date", "items", "supplier", "status"]),
            "order_by": "schedule_date asc",
            "limit_page_length": 100,
        }
        url = f"{self.base_url}/api/resource/Purchase Order"
        response = self._make_request("GET", url, params=params)
        po_list = self._handle_response(response)
        result = []
        for po in po_list if isinstance(po_list, list) else []:
            # Fetch full PO doc if items not present
            items = po.get("items")
            if not items:
                po_doc_resp = self._make_request("GET", f"{self.base_url}/api/resource/Purchase Order/{po['name']}")
                items = self._handle_response(po_doc_resp).get("items", [])
            for po_item in items:
                if po_item.get("item_code") == item_code and po_item.get("qty", 0) > po_item.get("received_qty", 0):
                    result.append({
                        "po_id": po["name"],
                        "item_code": po_item.get("item_code"),
                        "qty": po_item.get("qty", 0),
                        "received_qty": po_item.get("received_qty", 0),
                        "pending_qty": po_item.get("qty", 0) - po_item.get("received_qty", 0),
                        "schedule_date": po_item.get("schedule_date") or po.get("schedule_date"),
                        "warehouse": po_item.get("warehouse"),
                    })
        return result

    def get_sales_order(self, sales_order_id: str) -> Dict[str, Any]:
        """Get Sales Order details."""
        url = f"{self.base_url}/api/resource/Sales Order/{sales_order_id}"
        response = self._make_request("GET", url)
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

        url = f"{self.base_url}/api/resource/Sales Order"
        response = self._make_request("GET", url, params=params)
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

        url = f"{self.base_url}/api/resource/Comment"
        response = self._make_request("POST", url, json=data)
        return self._handle_response(response)

    def update_sales_order_custom_field(
        self, sales_order_id: str, field_name: str, value: Any
    ) -> Dict[str, Any]:
        """Update a custom field on Sales Order."""
        data = {field_name: value}

        url = f"{self.base_url}/api/resource/Sales Order/{sales_order_id}"
        response = self._make_request("PUT", url, json=data)
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

        url = f"{self.base_url}/api/resource/Material Request"
        response = self._make_request("POST", url, json=data)
        result = self._handle_response(response)

        # ERPNext returns the created doc
        if isinstance(result, dict):
            return result

        return {"name": "Unknown"}

    def health_check(self) -> bool:
        """Check if ERPNext is reachable and authenticated."""
        try:
            url = f"{self.base_url}/api/method/frappe.auth.get_logged_user"
            response = self._make_request("GET", url)
            self._handle_response(response)
            return True
        except Exception as e:
            logger.error(f"ERPNext health check failed: {e}")
            return False

    def close(self):
        """Close the HTTP client (not recommended - uses global connection pool)."""
        # Don't close global client - it's shared
        logger.info("ERPNextClient instance released (global client remains active)")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (doesn't close global client)."""
        # Clean up if needed, but keep the global client open
        pass

    @staticmethod
    def get_circuit_breaker_status() -> Dict[str, Any]:
        """Get current circuit breaker status for monitoring."""
        return {
            "state": _circuit_breaker.state,
            "failure_count": _circuit_breaker.failure_count,
            "last_failure_time": _circuit_breaker.last_failure_time,
            "threshold": _circuit_breaker.failure_threshold,
        }

    @staticmethod
    def reset_circuit_breaker():
        """Reset circuit breaker (useful for manual recovery)."""
        _circuit_breaker.failure_count = 0
        _circuit_breaker.state = "closed"
        _circuit_breaker.last_failure_time = None
        logger.info("Circuit breaker reset")

    @staticmethod
    def close_global_client():
        """Close the global HTTP client (call during shutdown)."""
        global _global_client
        if _global_client is not None:
            _global_client.close()
            _global_client = None
            logger.info("Global HTTP client closed")
