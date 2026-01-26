"""API tests with mocked ERPNext (using FastAPI TestClient)."""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import Mock, patch, MagicMock
from datetime import date, timedelta
from src.routes import otp as otp_routes
from src.clients.erpnext_client import ERPNextClient


# Create test app with overridden dependencies
@pytest.fixture
def test_app(mock_erpnext_client):
    """Create FastAPI test app with mocked dependencies."""
    from src.main import app
    
    # Override the dependency
    def override_get_client():
        return mock_erpnext_client
    
    app.dependency_overrides[otp_routes.get_erpnext_client] = override_get_client
    yield app
    app.dependency_overrides.clear()


@pytest.mark.api
class TestPromiseEndpoint:
    """Test /otp/promise endpoint."""

    def test_promise_endpoint_success(self, test_app, mock_erpnext_client):
        """Test: Valid request returns 200 with promise."""
        client = TestClient(test_app)
        
        response = client.post(
            "/otp/promise",
            json={
                "customer": "CUST-001",
                "items": [
                    {
                        "item_code": "ITEM-001",
                        "qty": 10.0,
                        "warehouse": "Stores - WH"
                    }
                ],
                "rules": {
                    "no_weekends": True,
                    "cutoff_time": "14:00",
                    "timezone": "UTC",
                    "lead_time_buffer_days": 1
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "promise_date" in data
        assert "confidence" in data
        assert data["confidence"] == "HIGH"
        assert "plan" in data
        assert len(data["plan"]) == 1

    def test_promise_endpoint_validation_error(self, test_app):
        """Test: Invalid request (missing fields) returns 422."""
        client = TestClient(test_app)
        
        # Missing 'items' field
        response = client.post(
            "/otp/promise",
            json={
                "customer": "CUST-001",
                # missing items
            }
        )

        assert response.status_code == 422  # Validation error

    def test_promise_endpoint_erpnext_error(self, test_app, mock_erpnext_client):
        """Test: ERPNext error returns 503."""
        from src.clients.erpnext_client import ERPNextClientError
        
        # Make the mock raise an error
        mock_erpnext_client.get_bin_details.side_effect = ERPNextClientError("Connection timeout")

        client = TestClient(test_app)
        
        response = client.post(
            "/otp/promise",
            json={
                "customer": "CUST-001",
                "items": [{"item_code": "ITEM-001", "qty": 10.0}]
            }
        )

        assert response.status_code == 503


@pytest.mark.api
class TestApplyEndpoint:
    """Test /otp/apply endpoint."""

    def test_apply_endpoint_success(self, test_app, mock_erpnext_client):
        """Test: Valid apply request returns success."""
        client = TestClient(test_app)
        
        response = client.post(
            "/otp/apply",
            json={
                "sales_order_id": "SO-00001",
                "promise_date": str(date.today() + timedelta(days=5)),
                "confidence": "MEDIUM",
                "action": "add_comment"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["sales_order_id"] == "SO-00001"
        assert len(data["actions_taken"]) > 0

    def test_apply_endpoint_not_found(self, test_app, mock_erpnext_client):
        """Test: Non-existent SO returns error (but 200 with error status)."""
        from src.clients.erpnext_client import ERPNextClientError
        
        # Make get_sales_order raise an error
        mock_erpnext_client.get_sales_order.side_effect = ERPNextClientError("Not found")

        client = TestClient(test_app)
        
        response = client.post(
            "/otp/apply",
            json={
                "sales_order_id": "SO-99999",
                "promise_date": str(date.today() + timedelta(days=5)),
                "confidence": "MEDIUM",
                "action": "add_comment"
            }
        )

        # Should return 503 due to ERPNext error
        assert response.status_code == 503


@pytest.mark.api
class TestProcurementEndpoint:
    """Test /otp/procurement-suggest endpoint."""

    def test_procure_endpoint_success(self, test_app, mock_erpnext_client):
        """Test: Valid procurement request creates MR."""
        client = TestClient(test_app)
        
        response = client.post(
            "/otp/procurement-suggest",
            json={
                "items": [
                    {
                        "item_code": "ITEM-001",
                        "qty_needed": 5.0,
                        "required_by": str(date.today() + timedelta(days=7)),
                        "reason": "Sales Order SO-00001"
                    }
                ],
                "suggestion_type": "material_request",
                "priority": "HIGH"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["suggestion_id"] == "MR-00001"
        assert data["type"] == "material_request"


@pytest.mark.api
class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_check_success(self, test_app, mock_erpnext_client):
        """Test: Health check when ERPNext is reachable."""
        mock_erpnext_client.health_check.return_value = True

        client = TestClient(test_app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["erpnext_connected"] is True

    def test_health_check_degraded(self, test_app, mock_erpnext_client):
        """Test: Health check when ERPNext is unreachable."""
        mock_erpnext_client.health_check.return_value = False

        client = TestClient(test_app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["erpnext_connected"] is False
