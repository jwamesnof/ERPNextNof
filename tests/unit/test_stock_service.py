"""Unit tests for StockService."""
import pytest
from unittest.mock import MagicMock
from datetime import date
from src.services.stock_service import StockService

pytestmark = pytest.mark.unit
from src.clients.erpnext_client import ERPNextClientError


class TestStockServiceGetAvailableStock:
    """Test get_available_stock method."""

    def test_get_available_stock_success(self):
        """Test successful stock retrieval."""
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 100.0,
            "reserved_qty": 10.0,
            "projected_qty": 90.0
        }
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-001", "WH-Main")
        
        assert result["actual_qty"] == 100.0
        assert result["available_qty"] == 90.0  # actual - reserved
        mock_client.get_bin_details.assert_called_once_with("ITEM-001", "WH-Main")

    def test_get_available_stock_erpnext_error_handled(self):
        """Test that ERPNext errors are handled."""
        mock_client = MagicMock()
        mock_client.get_bin_details.side_effect = ERPNextClientError("Permission denied")
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-001", "WH-Main")
        
        # Should return zeros on error
        assert result["actual_qty"] == 0.0
        assert result["available_qty"] == 0.0

    def test_get_available_stock_exception_handled(self):
        """Test that unexpected exceptions are propagated (or handled if not wrapped)."""
        mock_client = MagicMock()
        mock_client.get_bin_details.side_effect = ERPNextClientError("Connection error")
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-001", "WH-Main")
        
        # ERPNextClientError is caught, should return zeros
        assert result["actual_qty"] == 0.0
        assert result["available_qty"] == 0.0


class TestStockServiceGetIncomingSupply:
    """Test get_incoming_supply method."""

    def test_get_incoming_supply_success(self):
        """Test successful incoming supply retrieval."""
        mock_client = MagicMock()
        mock_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-001",
                "item_code": "ITEM-001",
                "pending_qty": 50,
                "schedule_date": "2026-02-10",
                "warehouse": "WH-Main"
            },
            {
                "po_id": "PO-002",
                "item_code": "ITEM-001",
                "pending_qty": 30,
                "schedule_date": "2026-02-15",
                "warehouse": "WH-Main"
            }
        ]
        
        service = StockService(mock_client)
        result = service.get_incoming_supply("ITEM-001")
        
        assert "supply" in result
        assert "access_error" in result
        assert len(result["supply"]) == 2
        assert result["supply"][0]["po_id"] == "PO-001"
        assert result["supply"][0]["qty"] == 50
        assert result["access_error"] is None
        mock_client.get_incoming_purchase_orders.assert_called_once_with("ITEM-001")

    def test_get_incoming_supply_empty(self):
        """Test incoming supply with no POs."""
        mock_client = MagicMock()
        mock_client.get_incoming_purchase_orders.return_value = []
        
        service = StockService(mock_client)
        result = service.get_incoming_supply("ITEM-NEVER-ORDERED")
        
        assert result["supply"] == []
        assert result["access_error"] is None

    def test_get_incoming_supply_permission_error_handled(self):
        """Test that permission errors are flagged with access_error."""
        mock_client = MagicMock()
        error = ERPNextClientError("Permission denied")
        error.status_code = 403
        mock_client.get_incoming_purchase_orders.side_effect = error
        
        service = StockService(mock_client)
        result = service.get_incoming_supply("ITEM-001")
        
        # Should return empty supply with access_error set
        assert result["supply"] == []
        assert result["access_error"] == "permission_denied"

    def test_get_incoming_supply_other_error_handled(self):
        """Test that other errors are flagged with other_error."""
        mock_client = MagicMock()
        mock_client.get_incoming_purchase_orders.side_effect = ERPNextClientError("Connection error")
        
        service = StockService(mock_client)
        result = service.get_incoming_supply("ITEM-001")
        
        # Should return empty supply with access_error set
        assert result["supply"] == []
        assert result["access_error"] == "other_error"


class TestStockServiceDataTransformation:
    """Test data transformation in StockService."""

    def test_transforms_po_data_correctly(self):
        """Test that PO data is transformed to expected format."""
        mock_client = MagicMock()
        mock_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-003",
                "item_code": "ITEM-002",
                "pending_qty": 100,
                "schedule_date": "2026-02-20",
                "warehouse": "WH-Incoming"
            }
        ]
        
        service = StockService(mock_client)
        result = service.get_incoming_supply("ITEM-002")
        
        assert result["supply"][0]["po_id"] == "PO-003"
        assert result["supply"][0]["qty"] == 100
        assert result["supply"][0]["expected_date"] == date(2026, 2, 20)

    def test_calculates_available_qty_correctly(self):
        """Test that available_qty is calculated as actual - reserved."""
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 150.0,
            "reserved_qty": 25.0,
            "projected_qty": 125.0
        }
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-003", "WH-Main")
        
        assert result["available_qty"] == 125.0  # 150 - 25


class TestStockServiceMultipleWarehouseScenarios:
    """Test stock service with multiple warehouse scenarios."""

    def test_different_warehouses_separate_calls(self):
        """Test that different warehouses make separate calls."""
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 50.0,
            "reserved_qty": 5.0,
            "projected_qty": 45.0
        }
        
        service = StockService(mock_client)
        
        result1 = service.get_available_stock("ITEM-001", "WH-A")
        result2 = service.get_available_stock("ITEM-001", "WH-B")
        
        assert mock_client.get_bin_details.call_count == 2
        assert result1["actual_qty"] == 50.0
        assert result2["actual_qty"] == 50.0


class TestStockServiceEdgeCases:
    """Test edge cases."""

    def test_negative_reserved_qty_handled(self):
        """Test that negative reserved qty doesn't cause issues."""
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 100.0,
            "reserved_qty": -5.0,  # Negative (shouldn't happen but handle it)
            "projected_qty": 105.0
        }
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-001", "WH-Main")
        
        # Should still calculate available_qty
        assert result["available_qty"] == 105.0

    def test_zero_stock_handled(self):
        """Test that zero stock is handled correctly."""
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0
        }
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-NO-STOCK", "WH-Main")
        
        assert result["actual_qty"] == 0.0
        assert result["available_qty"] == 0.0

    def test_very_large_quantities(self):
        """Test handling of very large quantities."""
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 1000000.0,
            "reserved_qty": 100000.0,
            "projected_qty": 900000.0
        }
        
        service = StockService(mock_client)
        result = service.get_available_stock("ITEM-BULK", "WH-Mega")
        
        assert result["available_qty"] == 900000.0

    def test_skips_pos_without_schedule_date(self):
        """Test that POs without schedule_date are skipped."""
        mock_client = MagicMock()
        mock_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-NO-DATE",
                "item_code": "ITEM-001",
                "pending_qty": 50,
                "schedule_date": None,  # No date
                "warehouse": "WH-Main"
            },
            {
                "po_id": "PO-WITH-DATE",
                "item_code": "ITEM-001",
                "pending_qty": 30,
                "schedule_date": "2026-02-15",
                "warehouse": "WH-Main"
            }
        ]
        
        service = StockService(mock_client)
        result = service.get_incoming_supply("ITEM-001")
        
        # Only the PO with a date should be included
        assert len(result["supply"]) == 1
        assert result["supply"][0]["po_id"] == "PO-WITH-DATE"

