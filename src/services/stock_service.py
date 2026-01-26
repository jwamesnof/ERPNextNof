"""Stock service for querying item availability."""
from typing import Dict, List, Optional
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
                return {
                    "actual_qty": bin_data.get("actual_qty", 0.0),
                    "reserved_qty": bin_data.get("reserved_qty", 0.0),
                    "available_qty": bin_data.get("projected_qty", 0.0),
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
    ) -> List[Dict]:
        """
        Get incoming supply from purchase orders.
        
        Returns list of incoming supply sorted by date:
            [
                {
                    "po_id": "PO-00123",
                    "qty": 5.0,
                    "expected_date": date(2026, 2, 3),
                    "warehouse": "Stores - WH"
                }
            ]
        """
        try:
            pos = self.client.get_incoming_purchase_orders(item_code)

            result = []
            for po in pos:
                # Parse schedule_date
                schedule_date_str = po.get("schedule_date")
                if schedule_date_str:
                    if isinstance(schedule_date_str, str):
                        expected_date = datetime.strptime(
                            schedule_date_str, "%Y-%m-%d"
                        ).date()
                    else:
                        expected_date = schedule_date_str
                else:
                    # Skip POs without schedule date
                    continue

                # Filter by after_date if provided
                if after_date and expected_date < after_date:
                    continue

                result.append(
                    {
                        "po_id": po["po_id"],
                        "qty": po["pending_qty"],
                        "expected_date": expected_date,
                        "warehouse": po.get("warehouse"),
                    }
                )

            # Sort by expected date
            result.sort(key=lambda x: x["expected_date"])
            return result

        except ERPNextClientError as e:
            logger.error(f"Failed to get incoming supply for {item_code}: {e}")
            return []
