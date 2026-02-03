"""Integration tests for OTP API with real ERPNext."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from src.main import app
from src.config import settings

# Skip all tests in this file if run_integration is False
pytestmark = pytest.mark.skipif(
    not settings.run_integration,
    reason="Integration tests disabled. Set RUN_INTEGRATION=true in .env to enable."
)

client = TestClient(app)


class TestPromiseEndpointIntegration:
    """Integration tests for /otp/promise endpoint with real ERPNext."""

    def test_promise_calculation_with_real_erpnext(self):
        """Test promise calculation using real ERPNext data."""
        request_data = {
            "customer": "Test Customer",
            "items": [
                {
                    "item_code": "TEST-ITEM-001",
                    "qty": 10.0,
                    "warehouse": "Stores - WH"
                }
            ],
            "desired_date": (date.today() + timedelta(days=10)).isoformat(),
            "rules": {
                "no_weekends": True,
                "cutoff_time": "14:00",
                "timezone": "UTC",
                "lead_time_buffer_days": 1,
                "processing_lead_time_days": 1,
                "desired_date_mode": "LATEST_ACCEPTABLE"
            }
        }

        response = client.post("/otp/promise", json=request_data)
        
        # Should return 200 even if item doesn't exist (will show as shortage)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "promise_date" in data
        assert "can_fulfill" in data
        assert "confidence" in data
        assert "plan" in data
        assert isinstance(data["plan"], list)

    def test_promise_calculation_multiple_items(self):
        """Test promise calculation with multiple items."""
        request_data = {
            "customer": "Test Customer",
            "items": [
                {"item_code": "ITEM-A", "qty": 5.0},
                {"item_code": "ITEM-B", "qty": 10.0},
                {"item_code": "ITEM-C", "qty": 15.0}
            ],
            "rules": {
                "no_weekends": True,
                "lead_time_buffer_days": 1
            }
        }

        response = client.post("/otp/promise", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have plan for all items
        assert len(data["plan"]) == 3
        
        # Each item should have required fields
        for item_plan in data["plan"]:
            assert "item_code" in item_plan
            assert "qty_required" in item_plan
            assert "fulfillment" in item_plan
            assert "shortage" in item_plan

    def test_promise_calculation_with_warehouse_specified(self):
        """Test promise calculation with specific warehouse."""
        request_data = {
            "customer": "Test Customer",
            "items": [
                {
                    "item_code": "TEST-ITEM",
                    "qty": 5.0,
                    "warehouse": "Finished Goods - WH"
                }
            ]
        }

        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 200

    def test_promise_calculation_strict_fail_mode(self):
        """Test STRICT_FAIL mode with desired date."""
        request_data = {
            "customer": "Test Customer",
            "items": [{"item_code": "ITEM-X", "qty": 100.0}],
            "desired_date": (date.today() + timedelta(days=2)).isoformat(),
            "rules": {
                "desired_date_mode": "STRICT_FAIL",
                "no_weekends": False
            }
        }

        response = client.post("/otp/promise", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include desired_date fields
        assert "desired_date" in data
        assert "desired_date_mode" in data
        assert "on_time" in data

    def test_promise_calculation_no_early_delivery_mode(self):
        """Test NO_EARLY_DELIVERY mode."""
        future_date = date.today() + timedelta(days=20)
        
        request_data = {
            "customer": "Test Customer",
            "items": [{"item_code": "ITEM-Y", "qty": 1.0}],
            "desired_date": future_date.isoformat(),
            "rules": {
                "desired_date_mode": "NO_EARLY_DELIVERY"
            }
        }

        response = client.post("/otp/promise", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["desired_date_mode"] == "NO_EARLY_DELIVERY"

    def test_promise_calculation_with_weekend_handling(self):
        """Test promise calculation respects weekend rules."""
        request_data = {
            "customer": "Test Customer",
            "items": [{"item_code": "ITEM-Z", "qty": 1.0}],
            "rules": {
                "no_weekends": True,
                "lead_time_buffer_days": 0,
                "processing_lead_time_days": 0
            }
        }

        response = client.post("/otp/promise", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Promise date should not be Friday (4) or Saturday (5)
        if data["promise_date"]:
            promise_date = date.fromisoformat(data["promise_date"])
            assert promise_date.weekday() not in [4, 5], "Promise date should not be on weekend"


class TestPromiseEndpointValidation:
    """Test request validation for promise endpoint."""

    def test_promise_validation_missing_customer(self):
        """Test validation error when customer is missing."""
        request_data = {
            "items": [{"item_code": "ITEM-A", "qty": 5.0}]
        }

        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_promise_validation_missing_items(self):
        """Test validation error when items are missing."""
        request_data = {
            "customer": "Test Customer"
        }

        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 422

    def test_promise_validation_empty_items(self):
        """Test validation error when items list is empty."""
        request_data = {
            "customer": "Test Customer",
            "items": []
        }

        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 422

    def test_promise_validation_negative_quantity(self):
        """Test validation error for negative quantity."""
        request_data = {
            "customer": "Test Customer",
            "items": [{"item_code": "ITEM-A", "qty": -5.0}]
        }

        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 422

    def test_promise_validation_zero_quantity(self):
        """Test validation error for zero quantity."""
        request_data = {
            "customer": "Test Customer",
            "items": [{"item_code": "ITEM-A", "qty": 0.0}]
        }

        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 422


class TestHealthEndpointIntegration:
    """Integration tests for health check endpoint."""

    def test_health_check_with_erpnext(self):
        """Test health check reports ERPNext connectivity."""
        response = client.get("/otp/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "erpnext_connected" in data
        
        # Should report actual ERPNext connection status
        assert isinstance(data["erpnext_connected"], bool)


class TestApplyPromiseIntegration:
    """Integration tests for /otp/apply endpoint with real ERPNext."""

    def test_apply_promise_to_sales_order(self):
        """Test applying promise date to actual Sales Order."""
        # This test requires a valid Sales Order to exist
        request_data = {
            "sales_order_id": "SO-TEST-001",
            "promise_date": (date.today() + timedelta(days=7)).isoformat(),
            "confidence": "HIGH",
            "action": "both"
        }

        response = client.post("/otp/apply", json=request_data)
        
        # Will fail if SO doesn't exist, but should handle gracefully
        assert response.status_code in [200, 404, 500]

    def test_apply_promise_validation(self):
        """Test apply promise request validation."""
        # Missing required fields
        request_data = {
            "sales_order_id": "SO-001"
            # Missing promise_date and confidence
        }

        response = client.post("/otp/apply", json=request_data)
        assert response.status_code == 422


class TestSalesOrdersEndpointIntegration:
    """Integration tests for sales orders listing endpoint."""

    def test_get_sales_orders_list(self):
        """Test retrieving sales orders from ERPNext."""
        response = client.get("/otp/sales-orders")
        
        # Should return 200 even if no orders exist
        assert response.status_code == 200
        data = response.json()
        
        # Response is a list of sales orders
        assert isinstance(data, list)

    def test_get_sales_orders_with_filters(self):
        """Test retrieving sales orders with filters."""
        params = {
            "status": "Draft",
            "limit": 10
        }
        
        response = client.get("/otp/sales-orders", params=params)
        assert response.status_code == 200

    def test_get_sales_order_details(self):
        """Test retrieving specific sales order details."""
        # Will return 404 if SO doesn't exist
        response = client.get("/otp/sales-orders/SO-TEST-001")
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "name" in data or "sales_order" in data


class TestErrorHandling:
    """Test error handling with real ERPNext."""

    def test_invalid_endpoint_returns_404(self):
        """Test that invalid endpoint returns 404."""
        response = client.get("/otp/nonexistent")
        assert response.status_code == 404

    def test_invalid_method_returns_405(self):
        """Test that invalid HTTP method returns 405."""
        response = client.put("/otp/promise")
        assert response.status_code == 405

    def test_malformed_json_returns_422(self):
        """Test that malformed JSON returns validation error."""
        response = client.post(
            "/otp/promise",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestConcurrentRequests:
    """Test handling of concurrent requests."""

    def test_multiple_concurrent_promise_calculations(self):
        """Test that multiple requests can be handled concurrently."""
        import concurrent.futures
        
        def make_request():
            request_data = {
                "customer": "Concurrent Test",
                "items": [{"item_code": "CONCURRENT-ITEM", "qty": 1.0}]
            }
            return client.post("/otp/promise", json=request_data)
        
        # Make 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
