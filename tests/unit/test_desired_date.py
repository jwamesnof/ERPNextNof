"""Unit tests for desired_date handling."""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.models.request_models import ItemRequest, PromiseRules, DesiredDateMode
from src.models.response_models import PromiseResponse

pytestmark = pytest.mark.unit


@pytest.mark.unit
class TestDesiredDateHandling:
    """Test suite for desired_date modes and on_time calculations."""

    def test_no_desired_date_provided(self, mock_erpnext_client, today):
        """Test: When no desired_date, on_time should be None."""
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
            customer="CUST-001", items=[item], desired_date=None, rules=rules
        )

        assert response.desired_date is None
        assert response.on_time is None
        assert response.promise_date is not None
        assert response.promise_date_raw == response.promise_date

    def test_latest_acceptable_on_time(self, mock_erpnext_client, today):
        """Test: LATEST_ACCEPTABLE mode when promise <= desired_date (on time)."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=10)  # Far in the future
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.LATEST_ACCEPTABLE
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        assert response.on_time is True
        assert response.promise_date <= desired
        assert response.desired_date == desired
        assert response.desired_date_mode == "LATEST_ACCEPTABLE"
        assert response.adjusted_due_to_no_early_delivery is False

    def test_latest_acceptable_late(self, mock_erpnext_client, today):
        """Test: LATEST_ACCEPTABLE mode when promise > desired_date (late)."""
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
                "schedule_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=5)  # Desired earlier than PO arrival
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.LATEST_ACCEPTABLE
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        assert response.on_time is False
        assert response.promise_date > desired
        assert response.desired_date == desired
        # Should have suggestions when late
        assert len(response.options) > 0

    def test_strict_fail_on_time(self, mock_erpnext_client, today):
        """Test: STRICT_FAIL mode when promise <= desired_date (succeeds)."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=10)
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.STRICT_FAIL
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        assert response.on_time is True
        assert response.promise_date <= desired

    def test_strict_fail_late_raises_error(self, mock_erpnext_client, today):
        """Test: STRICT_FAIL mode when promise > desired_date (raises ValueError)."""
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
                "schedule_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=5)
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.STRICT_FAIL
        )

        with pytest.raises(ValueError) as exc_info:
            promise_service.calculate_promise(
                customer="CUST-001", items=[item], desired_date=desired, rules=rules
            )
        
        assert "Cannot meet desired delivery date" in str(exc_info.value)
        assert "Earliest possible promise" in str(exc_info.value)

    def test_no_early_delivery_promise_earlier(self, mock_erpnext_client, today):
        """Test: NO_EARLY_DELIVERY mode when promise < desired_date (adjust to desired)."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=10)  # Desired far in future
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            processing_lead_time_days=1,
            desired_date_mode=DesiredDateMode.NO_EARLY_DELIVERY
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        # Promise should be adjusted to desired_date
        assert response.promise_date == desired
        assert response.promise_date_raw < desired  # Raw was earlier
        assert response.on_time is True
        assert response.adjusted_due_to_no_early_delivery is True
        assert "Can deliver earlier" in "".join(response.reasons)

    def test_no_early_delivery_promise_later(self, mock_erpnext_client, today):
        """Test: NO_EARLY_DELIVERY mode when promise > desired_date (late, not adjusted)."""
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
                "schedule_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=5)
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.NO_EARLY_DELIVERY
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        # Promise should NOT be adjusted (can't deliver earlier)
        assert response.promise_date > desired
        assert response.on_time is False
        assert response.adjusted_due_to_no_early_delivery is False

    def test_options_generated_when_late(self, mock_erpnext_client, today):
        """Test: Options (split_shipment, expedite_po) generated when promise misses desired_date."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 5.0,  # Partial stock
            "reserved_qty": 0.0,
            "projected_qty": 5.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-001",
                "item_code": "ITEM-001",
                "qty": 10.0,
                "received_qty": 0.0,
                "pending_qty": 10.0,
                "schedule_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=15.0, warehouse="Stores - WH")
        desired = today + timedelta(days=5)
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.LATEST_ACCEPTABLE
        )

        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        assert response.on_time is False
        # Should have expedite_po option
        assert any(opt.type == "expedite_po" for opt in response.options)

    def test_dynamic_recalculation_stock_change(self, mock_erpnext_client, today):
        """Test: Promise date changes when stock availability changes."""
        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        # Scenario 1: Stock available
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        response1 = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Scenario 2: Stock reduced (new reservation)
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 10.0,  # New reservation
            "projected_qty": 5.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-001",
                "item_code": "ITEM-001",
                "qty": 10.0,
                "received_qty": 0.0,
                "pending_qty": 10.0,
                "schedule_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        response2 = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=rules
        )

        # Promise date should be later when stock is reserved
        assert response2.promise_date > response1.promise_date
        assert response1.confidence == "HIGH"  # All from stock
        assert response2.confidence == "MEDIUM"  # Partial from PO

    def test_dynamic_recalculation_with_desired_date(self, mock_erpnext_client, today):
        """Test: on_time flag changes when stock/supply changes relative to desired_date."""
        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        desired = today + timedelta(days=5)
        rules = PromiseRules(
            lead_time_buffer_days=1,
            no_weekends=False,
            desired_date_mode=DesiredDateMode.LATEST_ACCEPTABLE
        )

        # Scenario 1: Stock available -> on time
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 15.0,
            "reserved_qty": 0.0,
            "projected_qty": 15.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        response1 = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        # Scenario 2: Stock depleted, PO arrives late -> NOT on time
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
                "schedule_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        response2 = promise_service.calculate_promise(
            customer="CUST-001", items=[item], desired_date=desired, rules=rules
        )

        # on_time should change from True to False
        assert response1.on_time is True
        assert response2.on_time is False
        assert response2.promise_date > desired
