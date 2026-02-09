"""API routes for item inventory endpoints."""
from fastapi import APIRouter, HTTPException, Query
import logging
from typing import Dict, Any
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"])


def get_item_stock(
    item_code: str = Query(..., description="Item code to fetch stock for"),
    warehouse: str = Query(..., description="Warehouse name"),
) -> Dict[str, Any]:
    """
    Get warehouse-specific stock data for an item.

    Returns actual stock, reserved stock, and available stock (actual - reserved).
    Used by frontend to display dynamic stock metrics when warehouse is changed.

    Args:
        item_code: ERPNext item code (e.g., "SKU001")
        warehouse: Warehouse name (e.g., "Stores - SD")

    Returns:
        dict with stock_actual, stock_reserved, stock_available

    Raises:
        HTTPException(404): If item doesn't exist in warehouse
        HTTPException(500): If ERPNext query fails
    """
    try:
        # Validate inputs
        if not item_code or not item_code.strip():
            raise HTTPException(status_code=400, detail="item_code is required")
        if not warehouse or not warehouse.strip():
            raise HTTPException(status_code=400, detail="warehouse is required")

        # Query ERPNext Bin doctype for this item + warehouse combination
        # Bin doctype stores warehouse-wise stock data for each item
        try:
            client = ERPNextClient()
            bin_data = client.get_value(
                "Bin",
                filters={
                    "item_code": item_code.strip(),
                    "warehouse": warehouse.strip(),
                },
                fieldname=["actual_qty", "reserved_qty"],
            )
        except ERPNextClientError as e:
            logger.error(f"ERPNext error fetching stock for {item_code} in {warehouse}: {e}")
            if "404" in str(e) or "not found" in str(e).lower():
                raise HTTPException(
                    status_code=404,
                    detail=f"Item '{item_code}' not found in warehouse '{warehouse}'",
                )
            raise HTTPException(status_code=502, detail=f"ERPNext error: {str(e)}")

        # If no bin record exists, item has no stock in this warehouse
        if bin_data is None:
            raise HTTPException(
                status_code=404, detail=f"Item '{item_code}' not found in warehouse '{warehouse}'"
            )

        # Extract quantities (default to 0 if missing)
        stock_actual = float(bin_data.get("actual_qty") or 0)
        stock_reserved = float(bin_data.get("reserved_qty") or 0)
        stock_available = stock_actual - stock_reserved

        return {
            "item_code": item_code.strip(),
            "warehouse": warehouse.strip(),
            "stock_actual": stock_actual,
            "stock_reserved": stock_reserved,
            "stock_available": stock_available,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any unexpected errors from ERPNext
        logger.error(f"Error fetching stock for {item_code} in {warehouse}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stock data: {str(e)}")


@router.get("/stock")
async def get_stock(
    item_code: str = Query(..., description="Item code to fetch stock for"),
    warehouse: str = Query(..., description="Warehouse name"),
) -> Dict[str, Any]:
    """
    Get warehouse-specific stock data for an item.

    **Parameters:**
    - `item_code` (string, required): ERPNext item code (e.g., "SKU001")
    - `warehouse` (string, required): Warehouse name (e.g., "Stores - SD")

    **Response (200 OK):**
    ```json
    {
      "item_code": "SKU001",
      "warehouse": "Stores - SD",
      "stock_actual": 100,
      "stock_reserved": 20,
      "stock_available": 80
    }
    ```

    **Error Responses:**
    - **404 Not Found**: Item doesn't exist in specified warehouse
    - **400 Bad Request**: Missing required parameters
    - **500 Internal Server Error**: Backend error accessing ERPNext
    """
    return get_item_stock(item_code=item_code, warehouse=warehouse)
