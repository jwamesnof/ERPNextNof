"""Pytest fixtures and test configuration."""
import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock
from src.clients.erpnext_client import ERPNextClient
from src.services.stock_service import StockService
from src.services.promise_service import PromiseService
from src.services.apply_service import ApplyService
from src.controllers.otp_controller import OTPController
from src.config import settings


# Mock ERPNext Client
@pytest.fixture
def mock_erpnext_client():
    """Mock ERPNext client for unit/API tests."""
    client = Mock(spec=ERPNextClient)
    
    # Default mock responses
    client.get_bin_details.return_value = {
        "actual_qty": 10.0,
        "reserved_qty": 2.0,
        "projected_qty": 8.0,
    }
    
    client.get_stock_balance.return_value = {
        "actual_qty": 10.0,
        "reserved_qty": 2.0,
        "available_qty": 8.0,
    }
    
    client.get_incoming_purchase_orders.return_value = []
    
    client.get_sales_order.return_value = {
        "name": "SO-00001",
        "customer": "Test Customer",
        "status": "Draft",
    }
    
    client.add_comment_to_doc.return_value = {"name": "comment-123"}
    
    client.update_sales_order_custom_field.return_value = {"name": "SO-00001"}
    
    client.create_material_request.return_value = {
        "name": "MR-00001",
        "doctype": "Material Request",
    }
    
    client.health_check.return_value = True
    
    return client


@pytest.fixture
def stock_service(mock_erpnext_client):
    """Stock service with mocked client."""
    return StockService(mock_erpnext_client)


@pytest.fixture
def promise_service(stock_service):
    """Promise service with mocked dependencies."""
    return PromiseService(stock_service)


@pytest.fixture
def apply_service(mock_erpnext_client):
    """Apply service with mocked client."""
    return ApplyService(mock_erpnext_client)


@pytest.fixture
def otp_controller(promise_service, apply_service):
    """OTP controller with mocked services."""
    return OTPController(promise_service, apply_service)


# Test data fixtures
@pytest.fixture
def sample_item_request():
    """Sample item request for testing."""
    from src.models.request_models import ItemRequest
    return ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")


@pytest.fixture
def sample_promise_request(sample_item_request):
    """Sample promise request for testing."""
    from src.models.request_models import PromiseRequest, PromiseRules
    return PromiseRequest(
        customer="CUST-001",
        items=[sample_item_request],
        desired_date=None,
        rules=PromiseRules(),
    )


@pytest.fixture
def today():
    """Today's date for testing."""
    return date.today()


# Integration test fixtures (only used when RUN_INTEGRATION=1)
@pytest.fixture
def real_erpnext_client():
    """Real ERPNext client for integration tests."""
    return ERPNextClient()


@pytest.fixture
def skip_if_no_integration():
    """Skip test if integration tests are not enabled."""
    if not settings.run_integration:
        pytest.skip("Integration tests disabled (set RUN_INTEGRATION=1 to enable)")


# Playwright fixtures (for E2E tests)
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for Playwright tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }
