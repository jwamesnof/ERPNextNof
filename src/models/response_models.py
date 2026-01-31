"""Response models for OTP API endpoints."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date


class FulfillmentSource(BaseModel):
    """Details of how an item is fulfilled."""

    source: str = Field(..., description="Source type: 'stock', 'purchase_order', 'production'")
    qty: float = Field(..., description="Quantity from this source")
    available_date: date = Field(..., description="Date when available")
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

    promise_date: date = Field(..., description="Earliest feasible delivery date")
    confidence: str = Field(..., description="Confidence level: HIGH, MEDIUM, LOW")
    plan: List[ItemPlan] = Field(..., description="Fulfillment plan per item")
    reasons: List[str] = Field(..., description="Explanation of promise calculation")
    blockers: List[str] = Field(default_factory=list, description="Issues preventing promise")
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


class SalesOrderSummary(BaseModel):
    """Sales Order summary for list endpoint."""

    name: str
    customer: str
    delivery_date: Optional[date] = None
    item_count: int
    total_qty: float
    status: str
    so_date: date
