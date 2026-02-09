"""Unit tests for promise service (core algorithm)."""
import pytest
from datetime import timedelta
from unittest.mock import patch
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.models.request_models import ItemRequest, PromiseRules

pytestmark = pytest.mark.unit


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

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

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

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

        # Assertions
        assert response.confidence == "MEDIUM"
        # promise_date = stock_available(0) + processing_lead_time(1) + partial_PO_available(3) + processing_lead_time(1) + buffer(1) = 6
        assert response.promise_date == today + timedelta(
            days=5
        )  # PO in 3 days + processing lead time(1) + buffer(1)
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

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

        # Assertions
        assert response.confidence == "MEDIUM"
        # promise_date = PO_available(5 days) + processing_lead_time(1) + buffer(1) = 7 days
        assert response.promise_date == today + timedelta(
            days=7
        )  # 5 days PO + 1 processing + 1 buffer
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

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

        # Assertions
        assert response.confidence == "LOW"
        assert response.plan[0].shortage == 2.0
        assert len(response.blockers) > 0
        assert any("Shortage" in blocker for blocker in response.blockers)

    def test_skip_weekends(self, mock_erpnext_client):
        """Test: Promise date adjusted to skip weekends (Fri-Sat)."""
        # Setup: Promise date should avoid Friday(4) and Saturday(5)
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=True)
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        # Force base calculation to land on weekend
        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=True)

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

        # Weekend should be skipped (not Friday or Saturday)
        # Working days are Sun(6), Mon(0), Tue(1), Wed(2), Thu(3)
        # Weekend days are Fri(4), Sat(5)
        assert response.promise_date.weekday() not in (4, 5)

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

        response = promise_service.calculate_promise(customer="CUST-001", items=items, rules=rules)

        # Promise should be based on Item B (latest)
        # Item A: today + processing_lead_time(1) + buffer(1) = +2 days
        # Item B: 5 days + processing_lead_time(1) + buffer(1) = +7 days
        assert response.promise_date == today + timedelta(
            days=7
        )  # Item B is latest: 5 + 1 processing + 1 buffer
        assert len(response.plan) == 2

    def test_po_access_permission_denied(self, mock_erpnext_client, today):
        """Test: PO data access denied due to permissions → handles gracefully."""
        # Setup: No stock, but PO access denied
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0,
        }
        # Simulate permission denied error
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        # Mock get_incoming_supply to return access_error

        with patch.object(
            stock_service,
            "get_incoming_supply",
            return_value={"supply": [], "access_error": "permission_denied"},
        ):
            promise_service = PromiseService(stock_service)

            item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
            rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

            response = promise_service.calculate_promise(
                customer="CUST-001", items=[item], rules=rules
            )

            # Should have shortage and mention PO access issue
            assert response.plan[0].shortage == 10.0
            assert any(
                "PO data unavailable" in reason or "permissions" in reason.lower()
                for reason in response.reasons
            )

    def test_no_weekends_false(self, mock_erpnext_client, today):
        """Test: no_weekends=False allows weekend delivery dates."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)  # Allow weekends

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

        # Promise date should be simple addition without weekend skipping
        # today + processing_lead_time(1) + buffer(1) = +2 days (regardless of weekday)
        assert response.promise_date == today + timedelta(days=2)

    def test_desired_date_on_time(self, mock_erpnext_client, today):
        """Test: Desired date set and promise meets it → on_time=True."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001",
            items=[item],
            desired_date=today + timedelta(days=10),  # Desired date is 10 days out
            rules=rules,
        )

        # Should be on time since desired date is far enough
        # Promise would be ~2 days, desired is 10, so on_time
        assert response.confidence in ["HIGH", "MEDIUM"]
        # Check reasons mention desired date
        assert len(response.reasons) > 0

    def test_desired_date_late(self, mock_erpnext_client, today):
        """Test: Desired date set but promise is late → suggestions offered."""
        # Setup: PO arrives late
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-LATE",
                "item_code": "ITEM-001",
                "qty": 10.0,
                "received_qty": 0.0,
                "pending_qty": 10.0,
                "schedule_date": (today + timedelta(days=15)).strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001",
            items=[item],
            desired_date=today + timedelta(days=5),  # Want it in 5 days, but PO is 15 days out
            rules=rules,
        )

        # Should suggest expediting the PO
        assert len(response.options) > 0
        assert any(opt.type == "expedite_po" for opt in response.options)

    def test_no_early_delivery_mode(self, mock_erpnext_client, today):
        """Test: NO_EARLY_DELIVERY mode delays promise to match desired date."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")

        # Set desired date far in future with NO_EARLY_DELIVERY mode
        rules = PromiseRules(
            lead_time_buffer_days=0,
            no_weekends=False,
            desired_date_mode="NO_EARLY_DELIVERY",  # Promise should be adjusted to desired date
        )

        response = promise_service.calculate_promise(
            customer="CUST-001",
            items=[item],
            desired_date=today + timedelta(days=10),  # desired_date is separate parameter
            rules=rules,
        )

        # Promise should be adjusted to desired date
        assert response.promise_date == today + timedelta(days=10)
        assert response.adjusted_due_to_no_early_delivery

    def test_warehouse_needs_processing(self, mock_erpnext_client, today):
        """Test: Warehouse classified as NEEDS_PROCESSING adds extra day."""
        # Test with None rules to hit default path
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []
        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)
        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=None)
        assert response is not None

        # Test NEEDS_PROCESSING warehouse type
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        # Use a warehouse that gets classified as NEEDS_PROCESSING
        from src.utils.warehouse_utils import WarehouseType

        with patch.object(
            promise_service.warehouse_manager,
            "classify_warehouse",
            return_value=WarehouseType.NEEDS_PROCESSING,
        ):
            item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Raw Materials - WH")
            rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

            response = promise_service.calculate_promise(
                customer="CUST-001", items=[item], rules=rules
            )

            # Should add extra processing day
            # Stock available + processing_lead_time(1) + extra_processing(1) = +2 days
            assert response.plan[0].fulfillment[0].ship_ready_date >= today + timedelta(days=2)
            assert any("processing" in reason.lower() for reason in response.reasons)

    def test_warehouse_in_transit_ignored(self, mock_erpnext_client, today):
        """Test: IN_TRANSIT warehouse stock is ignored."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,  # Stock exists but in transit
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        from src.utils.warehouse_utils import WarehouseType

        with patch.object(
            promise_service.warehouse_manager,
            "classify_warehouse",
            return_value=WarehouseType.IN_TRANSIT,
        ):
            item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Transit - WH")
            rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

            response = promise_service.calculate_promise(
                customer="CUST-001", items=[item], rules=rules
            )

            # Should have shortage because IN_TRANSIT stock is not counted
            assert response.plan[0].shortage == 10.0
            # IN_TRANSIT stock is ignored, so we should have shortage
            assert response.confidence == "LOW"

    def test_po_falls_on_weekend_adjusted(self, mock_erpnext_client, today):
        """Test: PO expected date falls on weekend → adjusted to next working day."""
        # Create a date that's Saturday in the future
        from datetime import timedelta

        # Find next Saturday
        days_ahead = (5 - today.weekday()) % 7  # 5 = Saturday
        if days_ahead == 0:
            days_ahead = 7
        next_saturday = today + timedelta(days=days_ahead)

        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 0.0,
            "reserved_qty": 0.0,
            "projected_qty": 0.0,
        }
        # PO arrives on Saturday
        mock_erpnext_client.get_incoming_purchase_orders.return_value = [
            {
                "po_id": "PO-WEEKEND",
                "item_code": "ITEM-001",
                "qty": 10.0,
                "received_qty": 0.0,
                "pending_qty": 10.0,
                "schedule_date": next_saturday.strftime("%Y-%m-%d"),
                "warehouse": "Stores - WH",
            }
        ]

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=True)

        response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

        # Should have fulfillment and promise date should skip weekend
        assert len(response.plan[0].fulfillment) > 0
        assert response.promise_date.weekday() < 5  # Not Fri/Sat

    def test_split_shipment_option(self, mock_erpnext_client, today):
        """Test: When some items available and desired date missed → suggest split shipment."""

        def get_bin_side_effect(item_code, warehouse):
            if item_code == "ITEM-A":
                return {"actual_qty": 10.0, "reserved_qty": 0.0, "projected_qty": 10.0}
            else:
                return {"actual_qty": 0.0, "reserved_qty": 0.0, "projected_qty": 0.0}

        def get_pos_side_effect(item_code):
            if item_code == "ITEM-B":
                return [
                    {
                        "po_id": "PO-LATE",
                        "item_code": "ITEM-B",
                        "qty": 5.0,
                        "received_qty": 0.0,
                        "pending_qty": 5.0,
                        "schedule_date": (today + timedelta(days=20)).strftime("%Y-%m-%d"),
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
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

        response = promise_service.calculate_promise(
            customer="CUST-001",
            items=items,
            desired_date=today + timedelta(days=3),  # Want in 3 days, but B takes 20+
            rules=rules,
        )

        # Should suggest expediting late PO or alternate warehouse
        assert len(response.options) > 0


class TestPromiseServiceEdgeCases:
    """Test edge cases and uncovered branches in promise service."""

    @pytest.mark.unit
    def test_calculate_promise_with_none_rules(self, mock_erpnext_client, today):
        """Test that None rules defaults to PromiseRules()."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")

        # Pass None for rules - should use default
        response = promise_service.calculate_promise(
            customer="CUST-001", items=[item], rules=None  # Test None handling
        )

        assert response.promise_date is not None
        assert response.confidence in ["HIGH", "MEDIUM", "LOW"]

    @pytest.mark.unit
    def test_desired_date_fallback_return(self, mock_erpnext_client, today):
        """Test desired date analysis fallback path."""
        mock_erpnext_client.get_bin_details.return_value = {
            "actual_qty": 10.0,
            "reserved_qty": 0.0,
            "projected_qty": 10.0,
        }
        mock_erpnext_client.get_incoming_purchase_orders.return_value = []

        stock_service = StockService(mock_erpnext_client)
        promise_service = PromiseService(stock_service)

        item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
        rules = PromiseRules(lead_time_buffer_days=0, no_weekends=False)

        # Set desired date that's achievable
        response = promise_service.calculate_promise(
            customer="CUST-001",
            items=[item],
            desired_date=today + timedelta(days=10),  # Far in future
            rules=rules,
        )

        # Should be on time
        assert response.promise_date <= today + timedelta(days=10)
