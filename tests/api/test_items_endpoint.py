"""Tests for items endpoint (GET /api/items/stock)."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.clients.erpnext_client import ERPNextClientError

client = TestClient(app)


@pytest.mark.api
class TestItemStockEndpoint:
    """Tests for GET /api/items/stock endpoint."""

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_success(self, mock_client_class):
        """Test successful stock retrieval for valid item + warehouse."""
        # Setup mock
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 100, "reserved_qty": 20})
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["item_code"] == "SKU001"
        assert data["warehouse"] == "Stores - SD"
        assert data["stock_actual"] == 100.0
        assert data["stock_reserved"] == 20.0
        assert data["stock_available"] == 80.0

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_zero_values(self, mock_client_class):
        """Test response with zero stock values."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 0, "reserved_qty": 0})
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU_ZERO", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stock_actual"] == 0.0
        assert data["stock_reserved"] == 0.0
        assert data["stock_available"] == 0.0

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_negative_available(self, mock_client_class):
        """Test response with negative available stock (over-reserved)."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 50, "reserved_qty": 75})
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU_OVER", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stock_actual"] == 50.0
        assert data["stock_reserved"] == 75.0
        assert data["stock_available"] == -25.0  # negative

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_item_not_found(self, mock_client_class):
        """Test 404 when item doesn't exist in warehouse."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value=None)
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "NONEXISTENT", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_erpnext_404_error(self, mock_client_class):
        """Test 404 when ERPNext returns 404 error."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(
            side_effect=ERPNextClientError("HTTP 404: Item not found")
        )
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "NONEXISTENT", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_erpnext_502_error(self, mock_client_class):
        """Test 502 when ERPNext returns other error."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(side_effect=ERPNextClientError("Connection timeout"))
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 502
        data = response.json()
        assert "detail" in data

    def test_get_stock_missing_item_code(self):
        """Test 422 when item_code parameter is missing."""
        response = client.get("/api/items/stock", params={"warehouse": "Stores - SD"})
        assert response.status_code == 422

    def test_get_stock_missing_warehouse(self):
        """Test 422 when warehouse parameter is missing."""
        response = client.get("/api/items/stock", params={"item_code": "SKU001"})
        assert response.status_code == 422

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_empty_item_code(self, mock_client_class):
        """Test 400 when item_code is empty string."""
        response = client.get(
            "/api/items/stock", params={"item_code": "", "warehouse": "Stores - SD"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "item_code is required" in data["detail"]

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_empty_warehouse(self, mock_client_class):
        """Test 400 when warehouse is empty string."""
        response = client.get("/api/items/stock", params={"item_code": "SKU001", "warehouse": ""})
        assert response.status_code == 400
        data = response.json()
        assert "warehouse is required" in data["detail"]

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_whitespace_handling(self, mock_client_class):
        """Test that leading/trailing whitespace is handled correctly."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 100, "reserved_qty": 20})
        mock_client_class.return_value = mock_instance

        # Call with whitespace
        response = client.get(
            "/api/items/stock", params={"item_code": " SKU001 ", "warehouse": " Stores - SD "}
        )

        assert response.status_code == 200
        data = response.json()
        # Verify whitespace was trimmed
        assert data["item_code"] == "SKU001"
        assert data["warehouse"] == "Stores - SD"

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_multiple_warehouses(self, mock_client_class):
        """Test stock retrieval for same item in different warehouses."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 50, "reserved_qty": 10})
        mock_client_class.return_value = mock_instance

        warehouses = ["Stores - SD", "Finished Goods - SD", "Goods In Transit - SD"]

        for warehouse in warehouses:
            response = client.get(
                "/api/items/stock", params={"item_code": "SKU001", "warehouse": warehouse}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["warehouse"] == warehouse
            assert data["item_code"] == "SKU001"

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_missing_qty_fields(self, mock_client_class):
        """Test handling of missing qty fields in ERPNext response."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        # Return empty dict (missing fields)
        mock_instance.get_value = MagicMock(return_value={})
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()
        # Should default to 0
        assert data["stock_actual"] == 0.0
        assert data["stock_reserved"] == 0.0
        assert data["stock_available"] == 0.0

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_only_actual_qty(self, mock_client_class):
        """Test with only actual_qty field present."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 100})
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stock_actual"] == 100.0
        assert data["stock_reserved"] == 0.0
        assert data["stock_available"] == 100.0

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_decimal_values(self, mock_client_class):
        """Test handling of decimal quantity values."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(
            return_value={"actual_qty": 100.5, "reserved_qty": 20.25}
        )
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stock_actual"] == 100.5
        assert data["stock_reserved"] == 20.25
        assert data["stock_available"] == 80.25

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_unexpected_exception(self, mock_client_class):
        """Test 500 on unexpected exception."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(side_effect=Exception("Unexpected error"))
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_calls_correct_doctype(self, mock_client_class):
        """Test that endpoint calls correct ERPNext Bin doctype."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 100, "reserved_qty": 20})
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200

        # Verify correct doctype and filters were used
        mock_instance.get_value.assert_called_once()
        call_args = mock_instance.get_value.call_args
        assert call_args[0][0] == "Bin"  # doctype
        assert call_args[1]["filters"]["item_code"] == "SKU001"
        assert call_args[1]["filters"]["warehouse"] == "Stores - SD"

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_case_sensitive_item_code(self, mock_client_class):
        """Test that item codes are passed exactly as provided (case-sensitive)."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        mock_instance.get_value = MagicMock(return_value={"actual_qty": 100, "reserved_qty": 20})
        mock_client_class.return_value = mock_instance

        # Test with mixed case
        response = client.get(
            "/api/items/stock", params={"item_code": "SkU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200

        # Verify the exact item code was passed to ERPNext
        call_args = mock_instance.get_value.call_args
        assert call_args[1]["filters"]["item_code"] == "SkU001"

    @patch("src.routes.items.ERPNextClient")
    def test_get_stock_response_type_conversion(self, mock_client_class):
        """Test that quantity values are converted to float."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=None)
        # Return string values that should be converted to float
        mock_instance.get_value = MagicMock(
            return_value={"actual_qty": "100", "reserved_qty": "20"}
        )
        mock_client_class.return_value = mock_instance

        response = client.get(
            "/api/items/stock", params={"item_code": "SKU001", "warehouse": "Stores - SD"}
        )

        assert response.status_code == 200
        data = response.json()
        # Verify type conversion to float
        assert isinstance(data["stock_actual"], float)
        assert isinstance(data["stock_reserved"], float)
        assert isinstance(data["stock_available"], float)
        assert data["stock_actual"] == 100.0
        assert data["stock_reserved"] == 20.0
