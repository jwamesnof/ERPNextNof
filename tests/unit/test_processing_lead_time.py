"""Unit tests for processing lead time feature."""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.models.request_models import ItemRequest, PromiseRules

pytestmark = pytest.mark.unit


@pytest.mark.unit
class TestProcessingLeadTime:
    """Test suite for processing lead time calculations."""

    def test_processing_lead_time_default(self, mock_erpnext_client, today):
        """Test: Default processing lead time (1 day) is applied."""
        # Setup: 10 units in stock
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)  # No buffer, only processing lead time

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # With default processing_lead_time_days=1: ship_ready_date = today + 1
        assert response.promise_date == response.plan[0].fulfillment[0].ship_ready_date
        assert response.plan[0].fulfillment[0].ship_ready_date == today + timedelta(days=1)

    def test_processing_lead_time_warehouse_override(self, mock_erpnext_client, today):
        """Test: Warehouse-specific processing lead time overrides default."""
        # Setup: 10 units in stock
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        # Override warehouse processing lead time to 3 days
        promise_service = PromiseService(
            stock_service,
            warehouse_lead_times={"Stores - WH": 3}
        )

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # With warehouse override (3 days): ship_ready_date = today + 3
        assert response.promise_date == response.plan[0].fulfillment[0].ship_ready_date
        assert response.plan[0].fulfillment[0].ship_ready_date == today + timedelta(days=3)

    def test_processing_lead_time_item_override(self, mock_erpnext_client, today):
        """Test: Item-specific processing lead time overrides warehouse override."""
        # Setup: 10 units in stock
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        # Item-specific override (5 days) beats warehouse override (3 days)
        promise_service = PromiseService(
            stock_service,
            warehouse_lead_times={"Stores - WH": 3},
            item_lead_times={"ITEM-001": 5}
        )

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # With item override (5 days): ship_ready_date = today + 5
        assert response.promise_date == response.plan[0].fulfillment[0].ship_ready_date
        assert response.plan[0].fulfillment[0].ship_ready_date == today + timedelta(days=5)

    def test_processing_lead_time_rule_override(self, mock_erpnext_client, today):
        """Test: Warehouse override has higher priority than rule-level override."""
        # Setup: 10 units in stock
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        # Warehouse override (3 days) takes priority over rule (2 days)
        promise_service = PromiseService(
            stock_service,
            warehouse_lead_times={"Stores - WH": 3}
        )

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(
            lead_time_buffer_days=0,
            no_weekends=False,
            processing_lead_time_days=2  # Rule-level override (lower priority)
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # With warehouse override (3 days): ship_ready_date should be 3 days out
        assert response.promise_date == response.plan[0].fulfillment[0].ship_ready_date
        assert response.plan[0].fulfillment[0].ship_ready_date >= today + timedelta(days=2)  # At least 3 days out

    def test_processing_lead_time_hierarchy_item_beats_all(self, mock_erpnext_client, today):
        """Test: Item override has highest priority in hierarchy."""
        # Setup: 10 units in stock
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        # Priority hierarchy: Item (5) > Warehouse (3) > Rule (2) > Default (1)
        promise_service = PromiseService(
            stock_service,
            warehouse_lead_times={"Stores - WH": 3},
            item_lead_times={"ITEM-001": 5}
        )

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(
            lead_time_buffer_days=0,
            no_weekends=False,
            processing_lead_time_days=2
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Item override (5 days) wins: ship_ready_date = today + 5
        assert response.promise_date == response.plan[0].fulfillment[0].ship_ready_date
        assert response.plan[0].fulfillment[0].ship_ready_date == today + timedelta(days=5)

    def test_processing_lead_time_with_po(self, mock_erpnext_client, today):
        """Test: Processing lead time applied to PO delivery dates."""
        # Setup: No stock, PO arriving in 3 days
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-001",
                "item_code": "ITEM-001",
                "qty": 10.0,
                "received_qty": 0.0,
                "pending_qty": 10.0,
                "schedule_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(
            stock_service,
            item_lead_times={"ITEM-001": 2}  # 2-day processing lead time
        )

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # PO available: 3 days + processing lead time: 2 days = 5 days
        assert response.promise_date == today + timedelta(days=5)
        assert response.plan[0].fulfillment[0].available_date == today + timedelta(days=3)
        assert response.plan[0].fulfillment[0].ship_ready_date == today + timedelta(days=5)

    def test_processing_lead_time_with_weekends(self, mock_erpnext_client, today):
        """Test: Weekend rules applied after processing lead time."""
        # Setup: 10 units in stock
        # Assume today is Friday (weekday 4)
        friday = date(2026, 1, 30)  # Friday
        
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(
            stock_service,
            item_lead_times={"ITEM-001": 1}  # 1-day processing lead time
        )

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        # With weekend skip: Friday -> Saturday(skip) -> Sunday(skip) -> Monday
        rules = PromiseRules(
            lead_time_buffer_days=0,
            no_weekends=True,
            processing_lead_time_days=1
        )

        # Mock today as Friday (weekday 4)
        promise_service._get_today = Mock(return_value=friday)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Friday + 1 day processing = Saturday (skip) -> Sunday (skip) -> Monday
        monday = date(2026, 2, 2)
        assert response.promise_date == monday
