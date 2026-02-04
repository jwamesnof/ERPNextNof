"""Unit tests for ApplyService."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from src.services.apply_service import ApplyService
from src.clients.erpnext_client import ERPNextClientError

pytestmark = pytest.mark.unit


class TestApplyServiceSuccessPath:
    """Test successful promise application."""

    def test_apply_promise_with_comment_only(self):
        """Test applying promise with comment only."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {"name": "SO-00001", "customer": "Test Customer"}
        mock_client.add_comment_to_doc.return_value = {"name": "COMMENT-001"}

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00001",
            promise_date=date(2026, 2, 10),
            confidence="HIGH",
            action="add_comment",
        )

        assert result.status == "success"
        assert "SO-00001" in result.sales_order_id
        assert len(result.actions_taken) > 0
        assert any("Added comment" in action for action in result.actions_taken)
        mock_client.add_comment_to_doc.assert_called_once()

    def test_apply_promise_with_custom_field_only(self):
        """Test applying promise with custom field only."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {
            "name": "SO-00002",
            "customer": "Test Customer 2",
        }
        mock_client.update_sales_order_custom_field.return_value = {"name": "SO-00002"}

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00002",
            promise_date=date(2026, 2, 15),
            confidence="MEDIUM",
            action="set_custom_field",
        )

        assert result.status == "success"
        assert result.sales_order_id == "SO-00002"
        assert len(result.actions_taken) > 0
        assert mock_client.update_sales_order_custom_field.called

    def test_apply_promise_with_both_actions(self):
        """Test applying promise with both comment and custom field."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {
            "name": "SO-00003",
            "customer": "Test Customer 3",
        }
        mock_client.add_comment_to_doc.return_value = {"name": "COMMENT-002"}
        mock_client.update_sales_order_custom_field.return_value = {"name": "SO-00003"}

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00003",
            promise_date=date(2026, 2, 20),
            confidence="HIGH",
            action="both",
        )

        assert result.status == "success"
        assert result.sales_order_id == "SO-00003"
        assert len(result.actions_taken) >= 2
        mock_client.add_comment_to_doc.assert_called_once()
        assert mock_client.update_sales_order_custom_field.called

    def test_apply_promise_with_custom_comment_text(self):
        """Test applying promise with custom comment text."""
        custom_comment = "Custom promise message for customer"
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {
            "name": "SO-00004",
            "customer": "Test Customer 4",
        }
        mock_client.add_comment_to_doc.return_value = {"name": "COMMENT-003"}

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00004",
            promise_date=date(2026, 2, 25),
            confidence="HIGH",
            action="add_comment",
            comment_text=custom_comment,
        )

        assert result.status == "success"
        mock_client.add_comment_to_doc.assert_called_once()
        call_args = mock_client.add_comment_to_doc.call_args
        assert call_args[0][2] == custom_comment


class TestApplyServiceErrorHandling:
    """Test error handling in ApplyService."""

    def test_sales_order_not_found_returns_error(self):
        """Test error when sales order doesn't exist."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = None

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-NONEXISTENT",
            promise_date=date(2026, 2, 10),
            confidence="HIGH",
            action="both",
        )

        assert result.status == "error"
        assert "not found" in result.error.lower()
        assert result.sales_order_id == "SO-NONEXISTENT"

    def test_comment_failure_continues_with_warning(self):
        """Test that comment failure doesn't stop other actions."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {
            "name": "SO-00005",
            "customer": "Test Customer 5",
        }
        mock_client.add_comment_to_doc.side_effect = ERPNextClientError("Permission denied")
        mock_client.update_sales_order_custom_field.return_value = {"name": "SO-00005"}

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00005",
            promise_date=date(2026, 2, 10),
            confidence="HIGH",
            action="both",
        )

        assert result.status == "success"
        assert any("Failed to add comment" in action for action in result.actions_taken)

    def test_custom_field_failure_handled_gracefully(self):
        """Test that custom field failure is handled gracefully."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {
            "name": "SO-00006",
            "customer": "Test Customer 6",
        }
        mock_client.add_comment_to_doc.return_value = {"name": "COMMENT-004"}
        mock_client.update_sales_order_custom_field.side_effect = ERPNextClientError(
            "Field not found"
        )

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00006",
            promise_date=date(2026, 2, 10),
            confidence="HIGH",
            action="both",
        )

        assert result.status == "success"
        assert any("comment" in action.lower() for action in result.actions_taken)
        assert any("Custom field not available" in action for action in result.actions_taken)

    def test_confidence_field_failure_ignored(self):
        """Test that confidence field update failure is silently ignored."""
        mock_client = MagicMock()
        mock_client.get_sales_order.return_value = {
            "name": "SO-00007",
            "customer": "Test Customer 7",
        }
        # First call (promise_date) succeeds, second call (confidence) fails
        mock_client.update_sales_order_custom_field.side_effect = [
            {"name": "SO-00007"},
            ERPNextClientError("Confidence field not found"),
        ]

        service = ApplyService(mock_client)
        result = service.apply_promise_to_sales_order(
            sales_order_id="SO-00007",
            promise_date=date(2026, 2, 10),
            confidence="HIGH",
            action="set_custom_field",
        )

        assert result.status == "success"
        # Should still report success for the promise_date field
        assert any("custom_otp_promise_date" in action for action in result.actions_taken)


class TestApplyServiceCreateMaterialRequest:
    """Test material request creation."""

    def test_create_material_request_success(self):
        """Test successful material request creation."""
        mock_client = MagicMock()
        mock_client.create_material_request.return_value = {
            "name": "MR-00001",
            "doctype": "Material Request",
        }

        service = ApplyService(mock_client)
        items = [
            {"item_code": "ITEM-001", "qty_needed": 100, "required_by": "2026-02-15"},
            {"item_code": "ITEM-002", "qty_needed": 50, "required_by": "2026-02-15"},
        ]

        result = service.create_procurement_suggestion(items, "material_request", "HIGH")

        assert result.status == "success"
        assert result.suggestion_id == "MR-00001"
        assert result.type == "material_request"
        assert result.items_count == 2
        mock_client.create_material_request.assert_called_once()

    def test_create_material_request_with_priority(self):
        """Test material request creation with priority."""
        mock_client = MagicMock()
        mock_client.create_material_request.return_value = {"name": "MR-00002"}

        service = ApplyService(mock_client)
        items = [{"item_code": "ITEM-003", "qty_needed": 25, "required_by": "2026-02-10"}]

        result = service.create_procurement_suggestion(items, "material_request", "HIGH")

        assert result.status == "success"
        call_args = mock_client.create_material_request.call_args
        assert call_args[0][1] == "High"  # Priority mapped

    def test_create_material_request_handles_error(self):
        """Test material request creation error handling."""
        mock_client = MagicMock()
        mock_client.create_material_request.side_effect = ERPNextClientError("Permission denied")

        service = ApplyService(mock_client)
        items = [{"item_code": "ITEM-004", "qty_needed": 10, "required_by": "2026-02-20"}]

        result = service.create_procurement_suggestion(items, "material_request", "MEDIUM")

        assert result.status == "error"
        assert result.error is not None
        assert "permission" in result.error.lower() or "error" in result.error.lower()

    def test_create_unsupported_suggestion_type(self):
        """Test that unsupported suggestion types return error."""
        mock_client = MagicMock()

        service = ApplyService(mock_client)
        items = [{"item_code": "ITEM-005", "qty_needed": 10, "required_by": "2026-02-20"}]

        result = service.create_procurement_suggestion(items, "draft_po", "MEDIUM")

        assert result.status == "error"
        assert "not implemented" in result.error.lower()


class TestApplyServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_apply_promise_with_all_confidence_levels(self):
        """Test applying promise with different confidence levels."""
        for confidence in ["HIGH", "MEDIUM", "LOW"]:
            mock_client = MagicMock()
            mock_client.get_sales_order.return_value = {"name": "SO-001"}
            mock_client.add_comment_to_doc.return_value = {"name": "COMMENT-001"}

            service = ApplyService(mock_client)
            result = service.apply_promise_to_sales_order(
                sales_order_id="SO-001",
                promise_date=date(2026, 2, 10),
                confidence=confidence,
                action="add_comment",
            )

            assert result.status == "success"

    def test_empty_items_list_material_request(self):
        """Test material request creation with empty items list."""
        mock_client = MagicMock()
        mock_client.create_material_request.return_value = {"name": "MR-00003"}

        service = ApplyService(mock_client)
        result = service.create_procurement_suggestion([], "material_request", "LOW")

        # Should still attempt to create even with empty list
        assert result.status == "success"

    def test_material_request_with_single_item(self):
        """Test material request with single item."""
        mock_client = MagicMock()
        mock_client.create_material_request.return_value = {"name": "MR-00004"}

        service = ApplyService(mock_client)
        items = [{"item_code": "ITEM-SINGLE", "qty_needed": 1, "required_by": "2026-02-05"}]

        result = service.create_procurement_suggestion(items, "material_request", "MEDIUM")

        assert result.status == "success"
        assert result.items_count == 1

    def test_erpnext_url_construction(self):
        """Test that ERPNext URL is properly constructed."""
        mock_client = MagicMock()
        mock_client.create_material_request.return_value = {"name": "MR-00005"}

        service = ApplyService(mock_client)
        items = [{"item_code": "ITEM-URL-TEST", "qty_needed": 10, "required_by": "2026-02-10"}]

        result = service.create_procurement_suggestion(items, "material_request", "HIGH")

        assert result.erpnext_url is not None
        assert "MR-00005" in result.erpnext_url
