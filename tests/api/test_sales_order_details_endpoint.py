"""Integration tests for GET /otp/sales-orders/{sales_order_id} endpoint."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.main import app
from src.config import settings
from src.clients.erpnext_client import ERPNextClientError


client = TestClient(app)


def test_sales_order_details_endpoint_exists_and_not_404():
    """Test that GET /otp/sales-orders/{id} endpoint is registered and not 404."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order.return_value = {
            "name": "SO-00001",
            "customer_name": "Customer A",
            "transaction_date": "2026-02-01",
            "items": [],
        }

        response = client.get("/otp/sales-orders/SO-00001")

        assert response.status_code != 404, "Endpoint /otp/sales-orders/{id} is not registered!"


def test_sales_order_details_response_format_matches_contract():
    """Test response matches required schema."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order.return_value = {
            "name": "SO-00001",
            "customer_name": "Customer A",
            "transaction_date": "2026-02-01",
            "delivery_date": None,
            "status": "To Deliver and Bill",
            "grand_total": 1234.56,
            "set_warehouse": "Stores - SD",
            "items": [
                {
                    "item_code": "SKU-001",
                    "item_name": "Widget A",
                    "qty": 2,
                    "uom": "Nos",
                    "warehouse": "Stores - SD",
                }
            ],
        }
        # Mock get_bin_details to return stock data
        mock_instance.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 2.0,
        }

        response = client.get("/otp/sales-orders/SO-00001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "SO-00001"
        assert data["customer_name"] == "Customer A"
        assert data["status"] == "To Deliver and Bill"
        assert data["grand_total"] == 1234.56
        assert len(data["items"]) == 1
        assert data["items"][0]["item_code"] == "SKU-001"
        # Verify stock metrics are present
        assert "stock_actual" in data["items"][0]
        assert "stock_reserved" in data["items"][0]
        assert "stock_available" in data["items"][0]
        assert data["items"][0]["stock_actual"] == 10.0
        assert data["items"][0]["stock_reserved"] == 2.0
        assert data["items"][0]["stock_available"] == 8.0
        assert data["defaults"]["warehouse"] == "Stores - SD"
        assert data["defaults"]["delivery_model"] == settings.delivery_model
        assert data["defaults"]["cutoff_time"] == settings.cutoff_time
        assert data["defaults"]["no_weekends"] == settings.no_weekends


def test_sales_order_details_returns_404_on_missing():
    """Test that ERPNext 404 maps to 404 response."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order.side_effect = ERPNextClientError("HTTP 404: Not Found")

        response = client.get("/otp/sales-orders/SO-DOES-NOT-EXIST")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Sales Order not found"


def test_sales_order_details_returns_502_on_erpnext_error():
    """Test that ERPNext errors return 502 Bad Gateway."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order.side_effect = ERPNextClientError(
            "HTTP 500: Internal Server Error"
        )

        response = client.get("/otp/sales-orders/SO-00001")

        assert response.status_code == 502
        data = response.json()
        assert "ERPNext returned error" in data["detail"]


def test_sales_order_details_stock_metrics_are_optional():
    """Test that stock metrics are optional (backward compatibility)."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order.return_value = {
            "name": "SO-00002",
            "customer_name": "Customer B",
            "transaction_date": "2026-02-02",
            "items": [
                {
                    "item_code": "SKU-002",
                    "qty": 1,
                    "uom": "Nos",
                    "warehouse": "Stores - SD",
                }
            ],
        }
        # Mock get_bin_details to return empty data (simulating stock data unavailable)
        mock_instance.get_bin_details.return_value = {}

        response = client.get("/otp/sales-orders/SO-00002")

        assert response.status_code == 200
        data = response.json()
        # Stock metrics should be 0.0 when unavailable
        assert data["items"][0]["stock_actual"] == 0.0
        assert data["items"][0]["stock_reserved"] == 0.0
        assert data["items"][0]["stock_available"] == 0.0


def test_sales_order_details_is_in_openapi():
    """Verify endpoint appears in OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_schema = response.json()
    paths = openapi_schema.get("paths", {})

    assert "/otp/sales-orders/{sales_order_id}" in paths, (
        "Endpoint /otp/sales-orders/{sales_order_id} not in OpenAPI. "
        f"Available: {list(paths.keys())}"
    )

    sales_order_path = paths["/otp/sales-orders/{sales_order_id}"]
    assert "get" in sales_order_path
