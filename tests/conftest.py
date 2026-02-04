"""Pytest configuration and fixtures for all tests."""
import sys
import os
from pathlib import Path
from datetime import datetime, date

# Add project root to Python path so 'src' module can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import MagicMock, patch
try:
    from unittest.mock import AsyncMock
except ImportError:
    # AsyncMock not available in Python < 3.8, create a simple mock
    from unittest.mock import MagicMock
    AsyncMock = MagicMock
from src.config import settings


@pytest.fixture(scope="session")
def today():
    """Fixture providing today's date (session-scoped for efficiency)."""
    return date.today()


@pytest.fixture(scope="function")
def mock_erpnext_client():
    """Fixture providing a mocked ERPNext client (function-scoped to avoid state pollution)."""
    client = MagicMock()
    # These methods are actually SYNCHRONOUS, not async
    client.get_bin_details = MagicMock()
    client.get_incoming_purchase_orders = MagicMock()
    client.get_sales_order_list = MagicMock()
    client.get_sales_order = MagicMock()
    client.get_sales_order_items = MagicMock()
    client.get_item_details = MagicMock()
    client.create_document = MagicMock()
    client.update_document = MagicMock()
    client.delete_document = MagicMock()
    client.execute_method = MagicMock()
    client.get_stock_balance = MagicMock()
    return client


@pytest.fixture(scope="module")
def mock_warehouse_manager():
    """Fixture providing a mocked warehouse manager (module-scoped)."""
    manager = MagicMock()
    manager.get_warehouse_group = MagicMock(return_value="Main")
    manager.is_warehouse_available = MagicMock(return_value=True)
    manager.get_warehouse_type = MagicMock(return_value="DC")
    manager.get_warehouses_by_group = MagicMock(return_value=["WH-Main", "WH-DC"])
    return manager


@pytest.fixture(scope="module")
def sample_promise_request():
    """Fixture providing a sample promise request (module-scoped)."""
    from src.models.request_models import (
        PromiseRequest, ItemRequest, PromiseRules, DesiredDateMode
    )
    from datetime import datetime
    
    return PromiseRequest(
        customer="CUST-001",
        items=[
            ItemRequest(item_code="ITEM-001", qty=10, warehouse="WH-Main"),
            ItemRequest(item_code="ITEM-002", qty=5, warehouse="WH-DC"),
        ],
        desired_date=datetime(2024, 2, 15).date(),
        rules=PromiseRules(
            no_weekends=True,
            cutoff_time="14:00",
            timezone="UTC",
            lead_time_buffer_days=1,
            processing_lead_time_days=1,
            desired_date_mode=DesiredDateMode.LATEST_ACCEPTABLE,
        ),
    )


@pytest.fixture(scope="module")
def sample_promise_response():
    """Fixture providing a sample promise response (module-scoped)."""
    from src.models.response_models import (
        PromiseResponse, ItemPlan, FulfillmentSource, PromiseStatus
    )
    from datetime import datetime
    
    return PromiseResponse(
        status=PromiseStatus.OK,
        promise_date=datetime(2024, 2, 15).date(),
        confidence=95,
        can_fulfill=True,
        plan=[
            ItemPlan(
                item_code="ITEM-001",
                qty_required=10,
                fulfillment=[
                    FulfillmentSource(
                        source="stock",
                        qty=10,
                        available_date=datetime(2024, 2, 10).date(),
                        ship_ready_date=datetime(2024, 2, 15).date(),
                        warehouse="WH-Main",
                        po_id=None,
                        expected_date=None,
                    )
                ],
                shortage=0,
            )
        ],
        reasons=[],
        blockers=[],
        options=[],
    )


@pytest.fixture(scope="module")
def mock_stock_data():
    """Fixture providing mock stock data (module-scoped)."""
    return {
        "ITEM-001": {
            "warehouse": "WH-Main",
            "actual_qty": 10,
            "reserved_qty": 0,
            "ordered_qty": 5,
            "indented_qty": 0,
        },
        "ITEM-002": {
            "warehouse": "WH-DC",
            "actual_qty": 5,
            "reserved_qty": 2,
            "ordered_qty": 0,
            "indented_qty": 0,
        },
    }


@pytest.fixture(scope="module")
def mock_purchase_orders():
    """Fixture providing mock purchase order data (module-scoped)."""
    return [
        {
            "name": "PO-001",
            "supplier": "SUP-001",
            "expected_delivery_date": "2024-02-10",
            "items": [
                {
                    "item_code": "ITEM-003",
                    "qty": 50,
                    "received_qty": 0,
                }
            ],
        },
        {
            "name": "PO-002",
            "supplier": "SUP-002",
            "expected_delivery_date": "2024-02-15",
            "items": [
                {
                    "item_code": "ITEM-001",
                    "qty": 100,
                    "received_qty": 10,
                }
            ],
        },
    ]


@pytest.fixture
def mock_http_client():
    """Fixture providing a mocked HTTP client (function-scoped for safety)."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    return client
