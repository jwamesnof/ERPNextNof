"""Request models for OTP API endpoints."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum


class DesiredDateMode(str, Enum):
    """Mode for interpreting desired_date."""

    LATEST_ACCEPTABLE = "LATEST_ACCEPTABLE"  # desired_date is latest acceptable delivery
    STRICT_FAIL = "STRICT_FAIL"  # Hard constraint - fail if promise > desired
    NO_EARLY_DELIVERY = "NO_EARLY_DELIVERY"  # Customer does not want delivery earlier than desired


class ItemRequest(BaseModel):
    """Item in a promise request."""

    item_code: str = Field(..., description="ERPNext item code")
    qty: float = Field(..., gt=0, description="Quantity required")
    warehouse: Optional[str] = Field(None, description="Specific warehouse (optional)")


class PromiseRules(BaseModel):
    """Business rules for promise calculation."""

    no_weekends: bool = Field(True, description="Skip weekend dates")
    cutoff_time: str = Field("14:00", description="Daily cutoff time (HH:MM)")
    timezone: str = Field("UTC", description="Timezone for calculations")
    lead_time_buffer_days: int = Field(1, ge=0, description="Additional buffer days")
    processing_lead_time_days: int = Field(
        1, ge=0, description="Warehouse processing days before shipment"
    )
    desired_date_mode: DesiredDateMode = Field(
        DesiredDateMode.LATEST_ACCEPTABLE,
        description="How to interpret desired_date: LATEST_ACCEPTABLE (default), STRICT_FAIL, or NO_EARLY_DELIVERY",
    )


class PromiseRequest(BaseModel):
    """Request to calculate order promise date."""

    customer: str = Field(..., description="Customer ID or name")
    items: List[ItemRequest] = Field(..., min_length=1, description="Items to promise")
    desired_date: Optional[date] = Field(None, description="Customer desired delivery date")
    rules: PromiseRules = Field(default_factory=PromiseRules, description="Promise rules")


class ApplyPromiseRequest(BaseModel):
    """Request to apply promise to a Sales Order."""

    sales_order_id: str = Field(..., description="Sales Order ID in ERPNext")
    promise_date: date = Field(..., description="Calculated promise date")
    confidence: str = Field(..., description="Confidence level (HIGH/MEDIUM/LOW)")
    action: str = Field("both", description="Action: 'add_comment', 'set_custom_field', or 'both'")
    comment_text: Optional[str] = Field(None, description="Custom comment text")


class ProcurementItem(BaseModel):
    """Item needing procurement."""

    item_code: str
    qty_needed: float = Field(..., gt=0)
    required_by: date
    reason: str


class ProcurementSuggestionRequest(BaseModel):
    """Request to create procurement suggestion."""

    items: List[ProcurementItem] = Field(..., min_length=1)
    suggestion_type: str = Field(
        "material_request", description="Type: 'material_request', 'draft_po', or 'task'"
    )
    priority: str = Field("MEDIUM", description="Priority: HIGH, MEDIUM, LOW")
