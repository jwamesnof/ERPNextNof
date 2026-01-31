"""ERPNext API client with authentication and error handling."""
import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
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
            # Preserve status code for permission vs missing data distinction
            error = ERPNextClientError(
                f"HTTP {e.response.status_code}: {e.response.text}"
            )
            error.status_code = e.response.status_code
            raise error from e
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise ERPNextClientError("Request to ERPNext timed out") from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ERPNextClientError(f"Unexpected error: {str(e)}") from e

    def get_stock_balance(
        self, item_code: str, warehouse: Optional[str] = None
    ) -> Dict[str, Any]:
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
            # ERPNext expects JSON strings for list params
            "filters": json.dumps([
                ["item_code", "=", item_code],
                ["warehouse", "=", warehouse],
            ]),
            "fields": json.dumps([
                "actual_qty",
                "reserved_qty",
                "projected_qty",
                "warehouse",
            ]),
        }

        response = self.client.get("/api/resource/Bin", params=params)
        data = self._handle_response(response)
        
        # Return first bin or empty result
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        
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
        
        Uses parent-based approach (fetches full POs then filters) to avoid
        needing Purchase Order Item child table permissions.
        
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
        # Get all submitted Purchase Orders
        params = {
            "filters": json.dumps([
                ["docstatus", "=", 1],  # Submitted only
            ]),
            "fields": json.dumps(["name"]),
            "limit_page_length": 999,
        }
        
        response = self.client.get("/api/resource/Purchase Order", params=params)
        po_list = self._handle_response(response)
        
        # Now fetch full details for each PO and filter items
        result = []
        for po_summary in (po_list if isinstance(po_list, list) else []):
            po_name = po_summary.get("name")
            if not po_name:
                continue
                
            try:
                # Get full PO with items
                po_response = self.client.get(f"/api/resource/Purchase Order/{po_name}")
                po = self._handle_response(po_response)
                
                # Filter items for this item_code
                for item in po.get("items", []):
                    if item.get("item_code") == item_code:
                        qty = item.get("qty", 0)
                        received = item.get("received_qty", 0)
                        pending = qty - received
                        
                        # Only include if not fully received
                        if pending > 0:
                            result.append({
                                "po_id": po_name,
                                "item_code": item.get("item_code"),
                                "qty": qty,
                                "received_qty": received,
                                "pending_qty": pending,
                                "schedule_date": item.get("schedule_date"),
                                "warehouse": item.get("warehouse"),
                            })
            except Exception:
                # Skip POs we can't access
                continue
        
        # Sort by schedule date
        result.sort(key=lambda x: x.get("schedule_date") or "9999-99-99")
        return result

    def get_sales_order(self, sales_order_id: str) -> Dict[str, Any]:
        """Get Sales Order details."""
        response = self.client.get(f"/api/resource/Sales Order/{sales_order_id}")
        return self._handle_response(response)

    def get_sales_order_list(
        self,
        filters: Optional[List] = None,
        fields: Optional[List[str]] = None,
        limit: int = 20,
        order_by: str = "creation desc"
    ) -> List[Dict[str, Any]]:
        """
        Get list of Sales Orders.
        
        Args:
            filters: ERPNext filters (e.g., [["customer", "=", "ABC Corp"]])
            fields: Fields to return (defaults to common fields)
            limit: Max results
            order_by: Sort order
            
        Returns:
            List of Sales Order dicts
        """
        if fields is None:
            fields = ["name", "customer", "creation", "delivery_date", "grand_total", "docstatus"]
        
        params = {
            "fields": json.dumps(fields),
            "filters": json.dumps(filters or []),
            "limit_page_length": limit,
            "order_by": order_by,
        }
        
        response = self.client.get("/api/resource/Sales Order", params=params)
        data = self._handle_response(response)
        
        return data if isinstance(data, list) else data.get("data", [])

    def add_comment_to_doc(
        self, doctype: str, docname: str, comment_text: str
    ) -> Dict[str, Any]:
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

        response = self.client.put(
            f"/api/resource/Sales Order/{sales_order_id}", json=data
        )
        return self._handle_response(response)

    def create_material_request(self, items: List[Dict[str, Any]], priority: str = "Medium") -> Dict[str, Any]:
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
