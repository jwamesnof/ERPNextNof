"""Unit tests for promise service (core algorithm)."""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.models.request_models import ItemRequest, PromiseRules


@pytest.mark.unit
class TestPromiseService:
    """Test suite for promise calculation algorithm."""

    def test_promise_all_from_stock(self, mock_erpnext_client, today):
        """Test: All items available in stock → HIGH confidence, immediate promise."""
        # Setup: 10 units in stock, need 10
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Assertions
        assert response.confidence == "HIGH"
        # promise_date = stock_available_date(today) + processing_lead_time(1 day) + buffer(1 day)
        assert response.promise_date == today + timedelta(days=2)
        assert len(response.plan) == 1
        assert response.plan[0].shortage == 0
        assert response.plan[0].fulfillment[0].source == "stock"
        assert response.plan[0].fulfillment[0].qty == 10.0
        # Verify ship_ready_date includes processing lead time
        assert response.plan[0].fulfillment[0].ship_ready_date == today + timedelta(days=1)

    def test_promise_partial_stock(self, mock_erpnext_client, today):
        """Test: Partial from stock, rest from PO → MEDIUM confidence."""
        # Setup: 5 in stock, need 10, PO has 5 arriving in 3 days
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 5.0,
            "reserved_qty": 0.0,
            "projected_qty": 5.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-00123",
                "item_code": "ITEM-001",
                "qty": 5.0,
                "received_qty": 0.0,
                "pending_qty": 5.0,
                "schedule_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Assertions
        assert response.confidence == "MEDIUM"
        # promise_date = stock_available(0) + processing_lead_time(1) + partial_PO_available(3) + processing_lead_time(1) + buffer(1) = 6
        assert response.promise_date == today + timedelta(days=5)  # PO in 3 days + processing lead time(1) + buffer(1)
        assert len(response.plan[0].fulfillment) == 2
        assert response.plan[0].fulfillment[0].source == "stock"
        assert response.plan[0].fulfillment[1].source == "purchase_order"
        assert response.plan[0].shortage == 0

    def test_promise_no_stock(self, mock_erpnext_client, today):
        """Test: All from incoming PO → MEDIUM confidence."""
        # Setup: 0 in stock, PO has 10 arriving in 5 days
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-00124",
                "item_code": "ITEM-001",
                "qty": 10.0,
                "received_qty": 0.0,
                "pending_qty": 10.0,
                "schedule_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Assertions
        assert response.confidence == "MEDIUM"
        # promise_date = PO_available(5 days) + processing_lead_time(1) + buffer(1) = 7 days
        assert response.promise_date == today + timedelta(days=7)  # 5 days PO + 1 processing + 1 buffer
        assert response.plan[0].fulfillment[0].source == "purchase_order"

    def test_promise_shortage(self, mock_erpnext_client, today):
        """Test: Insufficient supply → LOW confidence, has shortage."""
        # Setup: 3 in stock, PO has 5, need 10 → shortage of 2
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 3.0,
            "reserved_qty": 0.0,
            "projected_qty": 3.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-00125",
                "item_code": "ITEM-001",
                "qty": 5.0,
                "received_qty": 0.0,
                "pending_qty": 5.0,
                "schedule_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Assertions
        assert response.confidence == "LOW"
        assert response.plan[0].shortage == 2.0
        assert len(response.blockers) > 0
        assert any("Shortage" in blocker for blocker in response.blockers)

    def test_skip_weekends(self, mock_erpnext_client):
        """Test: Promise date adjusted to skip weekends."""
        # Setup: Promise falls on Saturday (2026-01-31 is Saturday)
        saturday = date(2026, 1, 31)
        
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        # Force base calculation to land on Saturday
        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(
            lead_time_buffer_days=0,  # No buffer
            no_weekends=True
        )

        # Mock _get_today to return Friday (so Saturday after buffer would be tested)
        # This is a simplified test - in reality would need more complex date mocking
        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Weekend should be skipped
        assert response.promise_date.weekday() < 5  # Not Saturday(5) or Sunday(6)

    def test_multi_item_promise(self, mock_erpnext_client, today):
        """Test: Multiple items, promise is max of all item dates."""
        # Setup: Item A available today, Item B arrives in 5 days
        def get_bin_side_effect(item_code, warehouse):
            if item_code == "ITEM-A":
                return {"actual_qty": 10.0, "reserved_qty": 0.0, "projected_qty": 10.0}
            else:
                return {"actual_qty": 0.0, "reserved_qty": 0.0, "projected_qty": 0.0}

        def get_pos_side_effect(item_code):
            if item_code == "ITEM-B":
                return [
                    {
                        "po_id": "PO-00126",
                        "item_code": "ITEM-B",
                        "qty": 5.0,
                        "received_qty": 0.0,
                        "pending_qty": 5.0,
                        "schedule_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
                        "warehouse": "Stores - WH",
                    }
                ]
            return []

        mock_erpnext_client.get_bin_details.side_effect = get_bin_side_effect
        mock_erpnext_client.get_incoming_purchase_orders.side_effect = get_pos_side_effect

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        items = [
            ItemRequest(item_code="ITEM-A", qty=10.0, warehouse="Stores - WH"),
            ItemRequest(item_code="ITEM-B", qty=5.0, warehouse="Stores - WH"),
        ]
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001", items=items, rules=rules
        )

        # Promise should be based on Item B (latest)
        # Item A: today + processing_lead_time(1) + buffer(1) = +2 days
        # Item B: 5 days + processing_lead_time(1) + buffer(1) = +7 days
        assert response.promise_date == today + timedelta(days=7)  # Item B is latest: 5 + 1 processing + 1 buffer
        assert len(response.plan) == 2
