"""Additional tests to improve coverage to 98%+."""
import pytest
from unittest.mock import MagicMock, patch
import time
from datetime import date
import httpx

from src.clients.erpnext_client import ERPNextClient, ERPNextClientError, _circuit_breaker
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.models.request_models import ItemRequest, PromiseRules
from src.utils.warehouse_utils import WarehouseType

pytestmark = pytest.mark.unit


class TestCircuitBreakerHalfOpen:
    """Test circuit breaker half-open state and recovery."""

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker transitions to half-open and recovers."""
        ERPNextClient.reset_circuit_breaker()
        
        # Force circuit breaker to open by recording failures
        for _ in range(5):
            _circuit_breaker.record_failure()
        
        assert _circuit_breaker.is_open() is True
        
        # Simulate timeout passage to trigger half-open state
        _circuit_breaker.last_failure_time = time.time() - 61  # More than 60s timeout
        
        # Check should return False (not open) and transition to half-open
        is_open = _circuit_breaker.is_open()
        assert is_open is False
        assert _circuit_breaker.state == "half_open"
        
        # Record success to close circuit breaker
        _circuit_breaker.record_success()
        assert _circuit_breaker.state == "closed"
        
        ERPNextClient.reset_circuit_breaker()


class TestERPNextClientGetValueEdgeCases:
    """Test get_value method edge cases."""

    def test_get_value_with_empty_response(self):
        """Test get_value returns None for empty results."""
        ERPNextClient.reset_circuit_breaker()
        
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            # Test with empty list in data
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {"data": []}
            mock_client.request.return_value = response
            
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_value("Item", filters={"item_code": "NONEXISTENT"})
            assert result is None
            
        # Test with direct empty list response
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = []
            mock_client.request.return_value = response
            
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_value("Item", filters={"item_code": "NONEXISTENT"})
            assert result is None
            
        # Test with non-list, non-dict response (returns None)
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = "invalid_response"
            mock_client.request.return_value = response
            
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            result = client.get_value("Item", filters={"item_code": "INVALID"})
            assert result is None
            
        # Test exception handling in get_value
        with patch("src.clients.erpnext_client.get_global_client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            response = MagicMock()
            response.status_code = 404
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=response
            )
            response.text = "Item not found"
            mock_client.request.return_value = response
            
            client = ERPNextClient(base_url="http://test.local", api_key="test", api_secret="test")
            with pytest.raises(ERPNextClientError):
                client.get_value("Item", filters={"item_code": "INVALID"})


class TestProcurementSuggestionErrorHandling:
    """Test procurement suggestion endpoint error handling."""

    def test_procurement_suggestion_erpnext_error(self):
        """Test procurement suggestion handles ERPNext errors."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.routes.otp import get_controller
        
        test_client = TestClient(app)
        
        # Create mock controller
        mock_controller = MagicMock()
        mock_controller.create_procurement_suggestion.side_effect = ERPNextClientError("ERPNext connection failed")
        
        # Override dependency
        app.dependency_overrides[get_controller] = lambda: mock_controller
        
        try:
            response = test_client.post(
                "/otp/procurement-suggest",
                json={
                    "items": [
                        {
                            "item_code": "ITEM-001",
                            "qty_needed": 100,
                            "required_by": "2026-03-01",
                            "reason": "Stock shortage"
                        }
                    ],
                    "suggestion_type": "material_request",
                    "priority": "HIGH"
                }
            )
            
            assert response.status_code == 503
            assert "ERPNext service error" in response.json()["detail"]
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    def test_procurement_suggestion_generic_error(self):
        """Test procurement suggestion handles generic errors."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.routes.otp import get_controller
        
        test_client = TestClient(app)
        
        # Create mock controller that raises on method call
        mock_controller = MagicMock()
        mock_controller.create_procurement_suggestion.side_effect = RuntimeError("Unexpected system error")
        
        # Override dependency
        app.dependency_overrides[get_controller] = lambda: mock_controller
        
        try:
            response = test_client.post(
                "/otp/procurement-suggest",
                json={
                    "items": [
                        {
                            "item_code": "ITEM-001",
                            "qty_needed": 100,
                            "required_by": "2026-03-01",
                            "reason": "Stock shortage"
                        }
                    ],
                    "suggestion_type": "material_request",
                    "priority": "HIGH"
                }
            )
            
            assert response.status_code == 500
            assert "Internal error" in response.json()["detail"]
        finally:
            # Clean up override
            app.dependency_overrides.clear()



class TestOTPHealthCheckMockSupply:
    """Test OTP health check with mock supply enabled."""

    def test_otp_health_check_with_mock_supply(self):
        """Test OTP health endpoint returns mock supply message."""
        from fastapi.testclient import TestClient
        from src.main import app
        from src.config import settings
        
        test_client = TestClient(app)
        
        with patch.object(settings, "use_mock_supply", True):
            response = test_client.get("/otp/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["erpnext_connected"] is False
            assert "mock supply data" in data["message"].lower()


class TestGroupWarehouseWarning:
    """Test GROUP warehouse handling in promise service."""

    def test_group_warehouse_passed_to_build_item_plan(self):
        """Test that GROUP warehouse triggers warning in _build_item_plan."""
        import logging
        from unittest.mock import patch
        
        mock_client = MagicMock()
        mock_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_client.get_incoming_purchase_orders.return_value = []
        
        stock_service = StockService(mock_client)
        promise_service = PromiseService(stock_service)
        
        # Mock classify_warehouse to return GROUP
        with patch.object(
            promise_service.warehouse_manager,
            "classify_warehouse",
            return_value=WarehouseType.GROUP
        ), patch("src.services.promise_service.logger") as mock_logger:
            item = ItemRequest(item_code="ITEM-001", qty=10, warehouse="All Warehouses - Group")
            rules = PromiseRules(no_weekends=False)
            
            result = promise_service.calculate_promise(
                customer="CUST-001",
                items=[item],
                rules=rules
            )
            
            # Verify GROUP warehouse warning was logged
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Group warehouse" in warning_call
            assert "All Warehouses - Group" in warning_call
            
            # Check that reasons contain GROUP warehouse message
            assert any("Group warehouse" in str(r) for r in result.reasons)

