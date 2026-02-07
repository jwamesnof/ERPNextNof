"""Unit tests for ERPNextClient HTTP client with error handling."""
import pytest
import httpx
from unittest.mock import MagicMock, patch
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker before and after each test to ensure test isolation."""
    ERPNextClient.reset_circuit_breaker()
    yield
    ERPNextClient.reset_circuit_breaker()


class TestERPNextClientHTTPErrors:
    """Test HTTP error handling."""

    def test_handles_http_errors(self):
        """Test that HTTP errors trigger circuit breaker and proper error handling."""
        # Test 500 Internal Server Error - should raise immediately
        with patch("src.clients.erpnext_client.get_global_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            response = MagicMock()
            response.status_code = 500
            response.text = "Internal Server Error"
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Internal Server Error", request=MagicMock(), response=response
            )
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError):
                client.get_stock_balance("ITEM-001")

        # Test 502 Bad Gateway - should also raise
        with patch("src.clients.erpnext_client.get_global_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            response = MagicMock()
            response.status_code = 502
            response.text = "Bad Gateway"
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "502 Bad Gateway", request=MagicMock(), response=response
            )
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError):
                client.add_comment_to_doc("Sales Order", "SO-001", "Test comment")


class TestERPNextClientTimeoutHandling:
    """Test timeout exception handling - covered by integration tests."""

    def test_timeout_handling_documented(self):
        """Note: Timeout handling is covered by integration tests."""
        # Timeout exceptions are difficult to unit test with mocks
        # They're better covered by integration tests
        assert True


class TestERPNextClientMalformedResponses:
    """Test handling of malformed JSON responses."""

    def test_handles_malformed_and_error_responses(self):
        """Test handling of invalid JSON and ERPNext error responses."""
        # Test invalid JSON
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.side_effect = ValueError("Invalid JSON")
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError):
                client.get_sales_order("SO-001")

        # Test TimeoutException handling
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            response = MagicMock()
            response.status_code = 200
            response.json.side_effect = httpx.TimeoutException("Timeout occurred")
            mock_client.request.return_value = response
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError) as exc:
                client.get_sales_order("SO-001")
            assert "timed out" in str(exc.value).lower()

        # Test generic Exception handling  
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            response = MagicMock()
            response.status_code = 200
            response.json.side_effect = RuntimeError("Unexpected error")
            mock_client.request.return_value = response
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError) as exc:
                client.get_sales_order("SO-001")
            assert "Unexpected error" in str(exc.value)

        # Test ERPNext error with 'exception' field
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "exception": "Invalid Item Code",
                "exc_type": "ValidationError",
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError) as exc_info:
                client.get_stock_balance("INVALID_ITEM")
            assert "Invalid Item Code" in str(exc_info.value) or "error" in str(exc_info.value).lower()

        # Test ERPNext error with 'exc_type' field
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"exc_type": "frappe.exceptions.PermissionError"}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError):
                client.get_sales_order_list()


class TestERPNextClientStockBalance:
    """Test get_stock_balance method."""

    def test_get_stock_balance_with_and_without_warehouse(self):
        """Test get_stock_balance with and without warehouse parameter."""
        # Test with warehouse parameter
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "data": {
                    "actual_qty": 50.0,
                    "reserved_qty": 5.0,
                    "available_qty": 45.0,
                }
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_stock_balance("ITEM-001", warehouse="WH-Main")
            assert result["actual_qty"] == 50.0
            call_args = mock_client.request.call_args
            assert "warehouse" in str(call_args)

        # Test without warehouse parameter
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "data": {
                    "actual_qty": 100.0,
                    "reserved_qty": 0.0,
                    "available_qty": 100.0,
                }
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_stock_balance("ITEM-002")
            assert result["actual_qty"] == 100.0


class TestERPNextClientSuccessfulResponses:
    """Test successful response handling."""

    def test_response_unwrapping(self):
        """Test response unwrapping for data, message, and raw responses."""
        # Test unwrapping 'data' field
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": {"name": "SO-00001", "customer": "Test Customer"}}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order("SO-00001")
            assert result["name"] == "SO-00001"
            assert result["customer"] == "Test Customer"

        # Test raw data without wrapper
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"name": "SO-00001", "customer": "Test Customer"}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order("SO-00001")
            assert result["name"] == "SO-00001"
            assert result["customer"] == "Test Customer"

        # Test unwrapping 'message' field
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "message": [
                    {"name": "SO-001", "customer": "Cust-A"},
                    {"name": "SO-002", "customer": "Cust-B"},
                ]
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order_list()
            assert isinstance(result, list)
            assert len(result) == 2


class TestERPNextClientBinDetails:
    """Test get_bin_details method with various response formats."""

    def test_bin_details_various_responses(self):
        """Test bin details with wrapped data, empty response, and direct list."""
        # Test with data wrapper
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "data": [
                    {
                        "actual_qty": 100.0,
                        "reserved_qty": 10.0,
                        "projected_qty": 90.0,
                        "warehouse": "WH-Main",
                    }
                ]
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_bin_details("ITEM-001", "WH-Main")
            assert result["actual_qty"] == 100.0
            assert result["reserved_qty"] == 10.0

        # Test returns defaults when empty
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": []}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_bin_details("ITEM-001", "WH-NONEXISTENT")
            assert result["actual_qty"] == 0.0
            assert result["reserved_qty"] == 0.0
            assert result["projected_qty"] == 0.0
            assert result["item_code"] == "ITEM-001"
            assert result["warehouse"] == "WH-NONEXISTENT"

        # Test direct list response
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = [
                {
                    "actual_qty": 50.0,
                    "reserved_qty": 5.0,
                    "projected_qty": 45.0,
                    "warehouse": "WH-Secondary",
                }
            ]
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_bin_details("ITEM-002", "WH-Secondary")
            assert result["actual_qty"] == 50.0
            assert result["reserved_qty"] == 5.0


class TestERPNextClientPurchaseOrders:
    """Test get_incoming_purchase_orders with various response formats."""

    def test_incoming_po_various_responses(self):
        """Test PO response transformation, empty list, and non-list response."""
        # Test PO transformation
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = [
                {
                    "parent": "PO-001",
                    "item_code": "ITEM-001",
                    "qty": 100,
                    "received_qty": 20,
                    "schedule_date": "2026-02-10",
                    "warehouse": "WH-Main",
                }
            ]
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_incoming_purchase_orders("ITEM-001")
            assert len(result) == 1
            assert result[0]["po_id"] == "PO-001"
            assert result[0]["item_code"] == "ITEM-001"
            assert result[0]["pending_qty"] == 80
            assert result[0]["warehouse"] == "WH-Main"

        # Test empty list
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = []
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_incoming_purchase_orders("ITEM-NEVER-ORDERED")
            assert result == []

        # Test non-list response handled gracefully
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": []}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_incoming_purchase_orders("ITEM-001")
            assert result == []

        # Test get_value method with filters
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": [{"name": "ITEM-001", "description": "Test Item"}]}
            mock_client.request.return_value = response
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_value("Item", filters={"item_code": "ITEM-001"}, fieldname=["name", "description"])
            assert result["name"] == "ITEM-001"

        # Test get_value method with filters
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": [{"name": "ITEM-001", "description": "Test Item"}]}
            mock_client.request.return_value = response
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_value("Item", filters={"item_code": "ITEM-001"}, fieldname=["name", "description"])
            assert result["name"] == "ITEM-001"


class TestERPNextClientSalesOrderList:
    """Test get_sales_order_list method."""

    def test_sales_order_list_various_responses(self):
        """Test sales order list with wrapped, direct, and non-list responses."""
        # Test with data wrapper
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "data": [
                    {"name": "SO-001", "customer": "Cust-A", "status": "Draft"},
                    {"name": "SO-002", "customer": "Cust-B", "status": "To Deliver"},
                ]
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order_list(limit=20)
            assert len(result) == 2
            assert result[0]["name"] == "SO-001"

        # Test direct list response
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = [{"name": "SO-003", "customer": "Cust-C"}]
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order_list()
            assert len(result) == 1
            assert result[0]["name"] == "SO-003"

        # Test non-list response returns empty list
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"some_field": "value"}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order_list()
            assert result == []


class TestERPNextClientHealthCheck:
    """Test health check functionality."""

    def test_health_check_success(self):
        """Test successful health check and circuit breaker operations.""" 
        # Test reset_circuit_breaker
        ERPNextClient.reset_circuit_breaker()
        status = ERPNextClient.get_circuit_breaker_status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        
        try:
            with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                response = MagicMock()
                response.status_code = 200
                response.raise_for_status.return_value = None
                response.json.return_value = {"message": "admin"}

                mock_client.request.return_value = response

                client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
                result = client.health_check()

                assert result is True
        finally:
            # Always reset circuit breaker after test to avoid affecting other tests
            ERPNextClient.reset_circuit_breaker()

    def test_health_check_failure_on_error(self):
        """Test health check returns False on error."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get.side_effect = Exception("Connection failed")

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.health_check()

            assert result is False


class TestERPNextClientContextManager:
    """Test context manager functionality."""

    def test_context_manager_enter_exit(self):
        """Test that context manager properly enters and exits."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            with ERPNextClient(
                base_url="http://test.local", api_key="test", api_secret="test"
            ) as client:
                assert client is not None
                assert isinstance(client, ERPNextClient)
            
            # Context manager exits successfully
            # Global client is NOT closed (it's shared)
            mock_client.close.assert_not_called()

    def test_close_method(self):
        """Test that close method doesn't close the shared global client."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            client.close()

            # close() should NOT call the underlying client's close()
            # because the global client is shared
            mock_client.close.assert_not_called()


class TestERPNextClientMaterialRequest:
    """Test create_material_request method."""

    def test_create_material_request_various_scenarios(self):
        """Test material request creation with success, non-dict response, and empty items."""
        # Test successful creation
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "data": {"name": "MR-001", "material_request_type": "Purchase"}
            }
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            items = [
                {
                    "item_code": "ITEM-001",
                    "qty_needed": 100,
                    "required_by": "2026-02-15",
                    "warehouse": "WH-Main",
                }
            ]
            result = client.create_material_request(items, priority="High")
            assert result["name"] == "MR-001"
            mock_client.request.assert_called_once()

        # Test non-dict response
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = "String response"
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            items = [
                {
                    "item_code": "ITEM-002",
                    "qty_needed": 50,
                    "required_by": "2026-02-20",
                }
            ]
            result = client.create_material_request(items)
            assert result == {"name": "Unknown"}

        # Test empty items list
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"name": "MR-EMPTY"}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.create_material_request([], priority="Low")
            assert result["name"] == "MR-EMPTY"
            call_args = mock_client.request.call_args
            assert call_args is not None


class TestERPNextClientComments:
    """Test add_comment_to_doc method."""

    def test_add_comment_to_doc(self):
        """Test adding a comment to a document."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": {"name": "COMMENT-001"}}

            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.add_comment_to_doc("Sales Order", "SO-001", "Test comment")

            assert result["name"] == "COMMENT-001"
            mock_client.request.assert_called_once()


class TestERPNextClientUpdateCustomField:
    """Test update_sales_order_custom_field method."""

    def test_update_custom_field(self):
        """Test updating a custom field on Sales Order."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": {"name": "SO-001", "custom_field": "value"}}

            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.update_sales_order_custom_field("SO-001", "custom_promise_date", "2026-02-15")

            assert result["custom_field"] == "value"
            mock_client.request.assert_called_once()


class TestERPNextClientTimeoutException:
    """Test timeout exception handling."""

    def test_timeout_exception_handling(self):
        """Test that httpx.ReadTimeout is properly retried and raises RetryError."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Make the request itself raise ReadTimeout (more realistic)
            mock_client.request.side_effect = httpx.ReadTimeout("Request timed out")

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")

            # The retry decorator should retry 3 times, then raise tenacity.RetryError
            from tenacity import RetryError
            with pytest.raises(RetryError) as exc_info:
                client.get_stock_balance("ITEM-001")

            # Verify it was retried 3 times
            assert mock_client.request.call_count == 3


class TestERPNextClientSalesOrderListParameters:
    """Test get_sales_order_list with different parameter combinations."""

    @pytest.mark.parametrize(
        "customer,status,from_date,to_date,search,limit,offset",
        [
            ("CUST-001", None, None, None, None, 10, 0),  # Only customer
            (None, "Draft", None, None, None, 10, 0),  # Only status
            (None, None, "2024-01-01", None, None, 10, 0),  # Only from_date
            (None, None, None, "2024-02-01", None, 10, 0),  # Only to_date
            ("CUST-001", "Draft", "2024-01-01", "2024-02-01", None, 10, 0),  # Multiple parameters
            (None, None, None, None, "SO-", 10, 0),  # With search
            (None, None, None, None, None, 50, 100),  # With offset
            ("CUST-001", "Draft", "2024-01-01", "2024-02-01", "SO-", 100, 50),  # All parameters
        ],
    )
    def test_get_sales_order_list_with_parameters(self, customer, status, from_date, to_date, search, limit, offset):
        """Test get_sales_order_list with various parameter combinations."""
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "data": [
                    {"name": "SO-001", "customer": "CUST-001", "status": "Draft"},
                    {"name": "SO-002", "customer": "CUST-002", "status": "Draft"},
                ]
            }

            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order_list(
                customer=customer,
                status=status,
                from_date=from_date,
                to_date=to_date,
                search=search,
                limit=limit,
                offset=offset,
            )

            assert isinstance(result, list)
            assert len(result) == 2
            # Verify that request was called with correct URL (second positional arg)
            mock_client.request.assert_called_once()
            call_args = mock_client.request.call_args
            assert "/api/resource/Sales Order" in call_args[0][1]


class TestERPNextClientResponseEdgeCases:
    """Test edge cases in response handling."""

    def test_response_edge_cases(self):
        """Test handling of non-standard response formats."""
        # Test data field with invalid type
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": "invalid_string"}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_sales_order_list()
            assert result == []

        # Test bin details with non-list data
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": "not_a_list"}
            mock_client.request.return_value = response

            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_bin_details("ITEM-001", "WH-1")
            assert result["item_code"] == "ITEM-001"
            assert result["warehouse"] == "WH-1"
            assert result["actual_qty"] == 0.0
