"""Controllers for OTP API endpoints."""
from typing import Dict, Any
import logging
from src.models.request_models import (
    PromiseRequest,
    ApplyPromiseRequest,
    ProcurementSuggestionRequest,
)
from src.models.response_models import (
    PromiseResponse,
    ApplyPromiseResponse,
    ProcurementSuggestionResponse,
)
from src.services.promise_service import PromiseService
from src.services.apply_service import ApplyService

logger = logging.getLogger(__name__)


class OTPController:
    """Controller for OTP business logic."""

    def __init__(self, promise_service: PromiseService, apply_service: ApplyService):
        """Initialize with required services."""
        self.promise_service = promise_service
        self.apply_service = apply_service

    def calculate_promise(self, request: PromiseRequest) -> PromiseResponse:
        """Handle promise calculation request."""
        logger.info(
            f"Calculating promise for customer {request.customer} "
            f"with {len(request.items)} items"
        )

        response = self.promise_service.calculate_promise(
            customer=request.customer,
            items=request.items,
            desired_date=request.desired_date,
            rules=request.rules,
        )

        logger.info(
            f"Promise calculated: {response.promise_date} "
            f"(confidence: {response.confidence})"
        )
        
        # Debug log for desired_date fields
        logger.info(
            f"Response fields: desired_date={response.desired_date}, "
            f"on_time={response.on_time}, mode={response.desired_date_mode}"
        )

        return response

    def apply_promise(self, request: ApplyPromiseRequest) -> ApplyPromiseResponse:
        """Handle apply promise request."""
        logger.info(
            f"Applying promise to Sales Order {request.sales_order_id}: "
            f"{request.promise_date} ({request.confidence})"
        )

        response = self.apply_service.apply_promise_to_sales_order(
            sales_order_id=request.sales_order_id,
            promise_date=request.promise_date,
            confidence=request.confidence,
            action=request.action,
            comment_text=request.comment_text,
        )

        logger.info(f"Apply promise result: {response.status}")
        return response

    def create_procurement_suggestion(
        self, request: ProcurementSuggestionRequest
    ) -> ProcurementSuggestionResponse:
        """Handle procurement suggestion request."""
        logger.info(
            f"Creating {request.suggestion_type} for {len(request.items)} items "
            f"(priority: {request.priority})"
        )

        # Convert request items to dict format
        items = [
            {
                "item_code": item.item_code,
                "qty_needed": item.qty_needed,
                "required_by": str(item.required_by),
                "reason": item.reason,
            }
            for item in request.items
        ]

        response = self.apply_service.create_procurement_suggestion(
            items=items,
            suggestion_type=request.suggestion_type,
            priority=request.priority,
        )

        logger.info(f"Procurement suggestion result: {response.status}")
        return response
