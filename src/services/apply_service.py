"""Service for applying promise results to ERPNext."""
from typing import Dict, Any, List
import logging
from datetime import date
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError
from src.models.response_models import ApplyPromiseResponse, ProcurementSuggestionResponse
from src.config import settings

logger = logging.getLogger(__name__)


class ApplyService:
    """Service for writing back promise results to ERPNext."""

    def __init__(self, erpnext_client: ERPNextClient):
        """Initialize with ERPNext client."""
        self.client = erpnext_client

    def apply_promise_to_sales_order(
        self,
        sales_order_id: str,
        promise_date: date,
        confidence: str,
        action: str = "both",
        comment_text: str = None,
    ) -> ApplyPromiseResponse:
        """
        Apply promise to a Sales Order in ERPNext.

        Actions:
        - add_comment: Add a comment to the SO
        - set_custom_field: Update custom field (if exists)
        - both: Do both actions
        """
        actions_taken = []
        erpnext_responses = {}

        try:
            # Verify SO exists
            so = self.client.get_sales_order(sales_order_id)
            if not so:
                return ApplyPromiseResponse(
                    status="error",
                    sales_order_id=sales_order_id,
                    actions_taken=[],
                    error=f"Sales Order {sales_order_id} not found",
                )

            # Action 1: Add comment
            if action in ["add_comment", "both"]:
                if not comment_text:
                    comment_text = (
                        f"Order Promise Date: {promise_date} "
                        f"(Confidence: {confidence})\n"
                        f"Calculated by OTP Engine."
                    )

                try:
                    comment_response = self.client.add_comment_to_doc(
                        "Sales Order", sales_order_id, comment_text
                    )
                    actions_taken.append(f"Added comment to {sales_order_id}")
                    erpnext_responses["comment"] = comment_response
                except ERPNextClientError as e:
                    logger.warning(f"Failed to add comment: {e}")
                    actions_taken.append(f"Failed to add comment: {str(e)}")

            # Action 2: Update custom field (if it exists)
            if action in ["set_custom_field", "both"]:
                try:
                    # Try to set custom field for promise date
                    field_response = self.client.update_sales_order_custom_field(
                        sales_order_id, "custom_otp_promise_date", str(promise_date)
                    )
                    actions_taken.append(
                        f"Set custom field 'custom_otp_promise_date' to {promise_date}"
                    )
                    erpnext_responses["custom_field"] = field_response

                    # Also set confidence if field exists
                    try:
                        conf_response = self.client.update_sales_order_custom_field(
                            sales_order_id, "custom_otp_confidence", confidence
                        )
                        actions_taken.append(
                            f"Set custom field 'custom_otp_confidence' to {confidence}"
                        )
                    except ERPNextClientError:
                        pass  # Field may not exist

                except ERPNextClientError as e:
                    logger.warning(f"Failed to set custom field: {e}")
                    actions_taken.append(
                        f"Custom field not available (may need to create it in ERPNext)"
                    )

            return ApplyPromiseResponse(
                status="success",
                sales_order_id=sales_order_id,
                actions_taken=actions_taken,
                erpnext_response=erpnext_responses,
            )

        except ERPNextClientError as e:
            logger.error(f"Failed to apply promise: {e}")
            return ApplyPromiseResponse(
                status="error",
                sales_order_id=sales_order_id,
                actions_taken=actions_taken,
                error=str(e),
            )

    def create_procurement_suggestion(
        self,
        items: List[Dict[str, Any]],
        suggestion_type: str = "material_request",
        priority: str = "MEDIUM",
    ) -> ProcurementSuggestionResponse:
        """
        Create procurement suggestion in ERPNext.

        Types:
        - material_request: Create a Material Request
        - draft_po: Create a draft Purchase Order (future)
        - task: Create a Task for manual follow-up (future)
        """
        try:
            if suggestion_type == "material_request":
                # Map priority
                erpnext_priority = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}.get(
                    priority, "Medium"
                )

                # Create Material Request
                mr_response = self.client.create_material_request(items, erpnext_priority)

                mr_name = mr_response.get("name", "Unknown")
                erpnext_url = f"{settings.erpnext_base_url}/app/material-request/{mr_name}"

                return ProcurementSuggestionResponse(
                    status="success",
                    suggestion_id=mr_name,
                    type="material_request",
                    items_count=len(items),
                    erpnext_url=erpnext_url,
                )

            else:
                # Other types not implemented in MVP
                return ProcurementSuggestionResponse(
                    status="error",
                    suggestion_id="",
                    type=suggestion_type,
                    items_count=0,
                    erpnext_url="",
                    error=f"Suggestion type '{suggestion_type}' not implemented yet",
                )

        except ERPNextClientError as e:
            logger.error(f"Failed to create procurement suggestion: {e}")
            return ProcurementSuggestionResponse(
                status="error",
                suggestion_id="",
                type=suggestion_type,
                items_count=len(items),
                erpnext_url="",
                error=str(e),
            )
