"""Stock service for querying item availability."""
from typing import Dict, Optional
from datetime import date, datetime
import logging
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError

logger = logging.getLogger(__name__)


class StockService:
    """Service for stock-related queries."""

    def __init__(self, erpnext_client: ERPNextClient):
        """Initialize with ERPNext client."""
        self.client = erpnext_client

    def get_available_stock(
        self, item_code: str, warehouse: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get available stock for an item.

        Returns:
            {
                "actual_qty": 10.0,
                "reserved_qty": 2.0,
                "available_qty": 8.0
            }
        """
        try:
            if warehouse:
                bin_data = self.client.get_bin_details(item_code, warehouse)
                logger.info(f"DEBUG: get_bin_details returned: {bin_data}")
                actual_qty = bin_data.get("actual_qty", 0.0)
                reserved_qty = bin_data.get("reserved_qty", 0.0)
                available_qty = actual_qty - reserved_qty
                logger.info(
                    f"DEBUG: {item_code} in {warehouse} - actual={actual_qty}, reserved={reserved_qty}, available={available_qty}"
                )

                return {
                    "actual_qty": actual_qty,
                    "reserved_qty": reserved_qty,
                    "available_qty": max(0.0, available_qty),  # Can't be negative
                }
            else:
                # Get stock across all warehouses (simplified for MVP)
                # In production, you'd query multiple warehouses
                stock_data = self.client.get_stock_balance(item_code, warehouse)
                return {
                    "actual_qty": stock_data.get("actual_qty", 0.0),
                    "reserved_qty": stock_data.get("reserved_qty", 0.0),
                    "available_qty": stock_data.get("available_qty", 0.0),
                }
        except ERPNextClientError as e:
            logger.error(f"Failed to get stock for {item_code}: {e}")
            # Return zero stock on error
            return {"actual_qty": 0.0, "reserved_qty": 0.0, "available_qty": 0.0}

    def get_incoming_supply(
        self, item_code: str, after_date: Optional[date] = None
    ) -> Dict[str, any]:
        """
        Get incoming supply from purchase orders.

        Returns:
            {
                "supply": [  # List of supply, may be empty if no POs exist
                    {
                        "po_id": "PO-00123",
                        "qty": 5.0,
                        "expected_date": date(2026, 2, 3),
                        "warehouse": "Stores - WH"
                    }
                ],
                "access_error": None or str  # "permission_denied" or "other_error"
            }
        """
        result = {"supply": [], "access_error": None}

        try:
            pos = self.client.get_incoming_purchase_orders(item_code)

            for po in pos:
                # Parse schedule_date
                schedule_date_str = po.get("schedule_date")
                if schedule_date_str:
                    if isinstance(schedule_date_str, str):
                        expected_date = datetime.strptime(schedule_date_str, "%Y-%m-%d").date()
                    else:
                        expected_date = schedule_date_str
                else:
                    # Skip POs without schedule date
                    continue

                # Filter by after_date if provided
                if after_date and expected_date < after_date:
                    continue

                result["supply"].append(
                    {
                        "po_id": po["po_id"],
                        "qty": po["pending_qty"],
                        "expected_date": expected_date,
                        "warehouse": po.get("warehouse"),
                    }
                )

            # Sort by expected date
            result["supply"].sort(key=lambda x: x["expected_date"])
            return result

        except ERPNextClientError as e:
            # Distinguish between permission error and other errors
            status_code = getattr(e, "status_code", None)
            if status_code == 403:
                result["access_error"] = "permission_denied"
                logger.warning(f"Permission denied accessing PO data for {item_code}: {e}")
            else:
                result["access_error"] = "other_error"
                logger.error(f"Failed to get incoming supply for {item_code}: {e}")
            return result
