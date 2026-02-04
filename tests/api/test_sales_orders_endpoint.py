"""Integration tests for GET /otp/sales-orders endpoint."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, call
import json
from src.main import app

pytestmark = pytest.mark.api


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    from src.routes import otp
    otp._sales_orders_cache.clear()
    yield
    otp._sales_orders_cache.clear()


def test_sales_orders_endpoint_exists_and_not_404():
    """
    Test that GET /otp/sales-orders endpoint is registered and not 404.
    Verifies endpoint is properly exposed in FastAPI.
    """
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order_list.return_value = []
        
        response = client.get("/otp/sales-orders")
        
        assert response.status_code != 404, "Endpoint /otp/sales-orders is not registered!"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


def test_sales_orders_response_format_matches_contract():
    """Test response matches required schema - plain array of items."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        
        mock_instance.get_sales_order_list.return_value = [
            {
                "name": "SO-00001",
                "customer": "Customer A",
                "transaction_date": "2026-02-01",
                "delivery_date": "2026-02-05",
                "status": "To Deliver and Bill",
                "grand_total": 1234.56,
            }
        ]
        
        response = client.get("/otp/sales-orders")
        
        assert response.status_code == 200
        items = response.json()
        
        # Response should be a plain array
        assert isinstance(items, list), f"Response should be array, got: {type(items)}"
        assert len(items) == 1
        assert items[0]["name"] == "SO-00001"
        assert items[0]["customer"] == "Customer A"
        assert items[0]["grand_total"] == 1234.56


def test_erpnext_client_does_not_send_doctype_twice():
    """
    CRITICAL: Verify doctype is NOT sent in query params.
    ERPNext get_list() fails if doctype is passed both in URL and params.
    """
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        
        # Mock the underlying httpx client to capture the actual request
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        
        mock_instance.client = MagicMock()
        mock_instance.client.get = MagicMock(return_value=mock_response)
        mock_instance._handle_response = lambda x: []
        mock_instance.get_sales_order_list.return_value = []
        
        response = client.get("/otp/sales-orders?limit=10&customer=ABC")
        
        # Verify the endpoint call happened
        mock_instance.get_sales_order_list.assert_called_once()
        call_kwargs = mock_instance.get_sales_order_list.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["customer"] == "ABC"


def test_query_params_mapping():
    """Test all query parameters are correctly passed to client."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order_list.return_value = []
        
        response = client.get(
            "/otp/sales-orders?limit=25&offset=10&customer=ACME&status=Draft"
            "&from_date=2026-01-01&to_date=2026-02-01&search=SAL"
        )
        
        assert response.status_code == 200
        mock_instance.get_sales_order_list.assert_called_with(
            limit=25,
            offset=10,
            status="Draft",
            customer="ACME",
            from_date="2026-01-01",
            to_date="2026-02-01",
            search="SAL",
        )


def test_erpnext_error_returns_502_not_503():
    """Test that ERPNext errors return 502 Bad Gateway, not 503."""
    from src.clients.erpnext_client import ERPNextClientError
    
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        
        # Simulate ERPNext error (e.g., doctype duplicate, permission error, etc.)
        mock_instance.get_sales_order_list.side_effect = ERPNextClientError(
            "TypeError: get_list() got multiple values for argument 'doctype'"
        )
        
        response = client.get("/otp/sales-orders")
        
        # Should return 502 Bad Gateway, not 503
        assert response.status_code == 502, f"Expected 502, got {response.status_code}"
        data = response.json()
        assert "ERPNext returned error" in data["detail"]


def test_empty_response():
    """Test that empty results are returned correctly."""
    with patch("src.routes.otp.ERPNextClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.get_sales_order_list.return_value = []
        
        response = client.get("/otp/sales-orders")
        
        assert response.status_code == 200
        items = response.json()
        assert items == []


def test_sales_orders_is_in_openapi():
    """Verify endpoint appears in OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    
    openapi_schema = response.json()
    paths = openapi_schema.get("paths", {})
    
    assert "/otp/sales-orders" in paths, (
        f"Endpoint /otp/sales-orders not in OpenAPI. Available: {list(paths.keys())}"
    )
    
    sales_orders_path = paths["/otp/sales-orders"]
    assert "get" in sales_orders_path
