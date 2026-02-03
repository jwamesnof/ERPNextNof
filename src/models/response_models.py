"""Response models for OTP API endpoints."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date
from enum import Enum


class PromiseStatus(str, Enum):
    """Status of promise calculation."""
    OK = "OK"  # Promise calculated successfully
    CANNOT_FULFILL = "CANNOT_FULFILL"  # Insufficient stock/supply
    CANNOT_PROMISE_RELIABLY = "CANNOT_PROMISE_RELIABLY"  # Missing data (e.g., PO access denied)


class FulfillmentSource(BaseModel):
    """Details of how an item is fulfilled."""

    source: str = Field(..., description="Source type: 'stock', 'purchase_order', 'production'")
    qty: float = Field(..., description="Quantity from this source")
    available_date: date = Field(..., description="Date when available")
    ship_ready_date: date = Field(..., description="Date ready to ship (available_date + processing_lead_time)")
    warehouse: Optional[str] = Field(None, description="Warehouse name")
    po_id: Optional[str] = Field(None, description="Purchase Order ID (if applicable)")
    expected_date: Optional[date] = Field(None, description="Expected receipt date for PO")


class ItemPlan(BaseModel):
    """Fulfillment plan for a single item."""

    item_code: str
    qty_required: float
    fulfillment: List[FulfillmentSource]
    shortage: float = Field(0.0, description="Unfulfilled quantity")


class PromiseOption(BaseModel):
    """Alternative option to improve promise."""

    type: str = Field(..., description="Option type: alternate_warehouse, expedite_po, etc.")
    description: str
    impact: str = Field(..., description="Impact on promise date/confidence")
    po_id: Optional[str] = None


class PromiseResponse(BaseModel):
    """Response from promise calculation."""

    status: PromiseStatus = Field(..., description="Overall status: OK, CANNOT_FULFILL, or CANNOT_PROMISE_RELIABLY")
    promise_date: Optional[date] = Field(None, description="Final delivery date (null if CANNOT_FULFILL)")
    promise_date_raw: Optional[date] = Field(None, description="Computed promise before desired_date adjustments")
    desired_date: Optional[date] = Field(None, description="Customer requested delivery date (echoed from request)")
    desired_date_mode: Optional[str] = Field(None, description="Mode used for desired_date interpretation")
    on_time: Optional[bool] = Field(None, description="True if promise_date <= desired_date (when both provided)")
    adjusted_due_to_no_early_delivery: bool = Field(False, description="True if promise was delayed to match desired_date in NO_EARLY_DELIVERY mode")
    can_fulfill: bool = Field(..., description="True if order is fully allocatable")
    confidence: str = Field(..., description="Confidence level: HIGH, MEDIUM, LOW")
    plan: List[ItemPlan] = Field(..., description="Fulfillment plan per item")
    reasons: List[str] = Field(..., description="Explanation of promise calculation")
    blockers: List[str] = Field(default_factory=list, description="Issues preventing promise (e.g., insufficient stock, permission denied)")
    options: List[PromiseOption] = Field(
        default_factory=list, description="Alternative options"
    )


class ApplyPromiseResponse(BaseModel):
    """Response from applying promise to Sales Order."""

    status: str = Field(..., description="Status: success or error")
    sales_order_id: str
    actions_taken: List[str] = Field(..., description="List of actions performed")
    erpnext_response: Optional[Dict[str, Any]] = Field(None, description="Raw ERPNext response")
    error: Optional[str] = None


class ProcurementSuggestionResponse(BaseModel):
    """Response from creating procurement suggestion."""

    status: str = Field(..., description="Status: success or error")
    suggestion_id: str = Field(..., description="Created document ID in ERPNext")
    type: str = Field(..., description="Document type created")
    items_count: int
    erpnext_url: str = Field(..., description="Link to view in ERPNext")
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    erpnext_connected: bool = False
    message: Optional[str] = None


class SalesOrderItem(BaseModel):
    """Lightweight Sales Order item for list responses."""

    name: str = Field(..., description="Sales Order ID")
    customer: str = Field(..., description="Customer name")
    transaction_date: date = Field(..., description="Sales Order date")
    delivery_date: Optional[date] = Field(None, description="Expected delivery date")
    status: Optional[str] = Field(None, description="Sales Order status")
    grand_total: Optional[float] = Field(None, description="Total order amount")


class SalesOrderListResponse(BaseModel):
    """Response for GET /otp/sales-orders endpoint."""

    items: List[SalesOrderItem] = Field(..., description="List of Sales Orders")
    count: int = Field(..., description="Total number of items")


class SalesOrderSummary(BaseModel):
    """Sales Order summary for list endpoint (deprecated - use SalesOrderItem)."""

    name: str = Field(..., description="Sales Order ID")
    customer: str = Field(..., description="Customer name")
    transaction_date: date = Field(..., description="Sales Order date")
    delivery_date: Optional[date] = Field(None, description="Expected delivery date")
    status: Optional[str] = Field(None, description="Sales Order status")


class SalesOrderDetailItem(BaseModel):
    """Detailed Sales Order item for details endpoint."""

    item_code: str = Field(..., description="Item code")
    item_name: Optional[str] = Field(None, description="Item name")
    qty: float = Field(..., description="Quantity ordered")
    uom: Optional[str] = Field(None, description="Unit of measure")
    warehouse: Optional[str] = Field(None, description="Warehouse")


class SalesOrderDefaults(BaseModel):
    """Default UI settings for OTP screens."""

    warehouse: Optional[str] = Field(None, description="Default warehouse")
    delivery_model: str = Field(..., description="Delivery model for UI")
    cutoff_time: str = Field(..., description="Daily cutoff time (HH:MM)")
    no_weekends: bool = Field(..., description="Skip weekend dates")


class SalesOrderDetailsResponse(BaseModel):
    """Detailed Sales Order response for details endpoint."""

    id: str = Field(..., description="Sales Order ID")
    customer_name: str = Field(..., description="Customer name")
    transaction_date: date = Field(..., description="Sales Order date")
    delivery_date: Optional[date] = Field(None, description="Expected delivery date")
    status: Optional[str] = Field(None, description="Sales Order status")
    grand_total: Optional[float] = Field(None, description="Total order amount")
    items: List[SalesOrderDetailItem] = Field(..., description="Sales Order items")
    defaults: SalesOrderDefaults = Field(..., description="Default UI settings")
