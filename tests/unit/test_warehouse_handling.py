"""Test warehouse classification and handling.

Verifies that OTP correctly handles different warehouse types to prevent
false delivery promises.
"""
import pytest
from datetime import date
from src.utils.warehouse_utils import WarehouseManager, WarehouseType
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.models.request_models import ItemRequest, PromiseRules

pytestmark = pytest.mark.unit


class TestWarehouseClassification:
    """Test warehouse classification logic."""

    def test_sellable_warehouses(self):
        """Stores-type warehouses should be SELLABLE."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("Stores - SD") == WarehouseType.SELLABLE
        assert wm.classify_warehouse("Stores - WH") == WarehouseType.SELLABLE
        assert wm.classify_warehouse("Main Warehouse") == WarehouseType.SELLABLE

    def test_needs_processing_warehouses(self):
        """Finished Goods warehouses should be NEEDS_PROCESSING."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("Finished Goods - SD") == WarehouseType.NEEDS_PROCESSING
        assert wm.classify_warehouse("Finished Goods - WH") == WarehouseType.NEEDS_PROCESSING

    def test_in_transit_warehouses(self):
        """Goods In Transit warehouses should be IN_TRANSIT."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("Goods In Transit - SD") == WarehouseType.IN_TRANSIT
        assert wm.classify_warehouse("Goods In Transit - WH") == WarehouseType.IN_TRANSIT

    def test_not_available_warehouses(self):
        """WIP and rejected warehouses should be NOT_AVAILABLE."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("Work In Progress - SD") == WarehouseType.NOT_AVAILABLE
        assert wm.classify_warehouse("Rejected - SD") == WarehouseType.NOT_AVAILABLE
        assert wm.classify_warehouse("Scrap") == WarehouseType.NOT_AVAILABLE

    def test_group_warehouses(self):
        """All Warehouses should be GROUP."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("All Warehouses - SD") == WarehouseType.GROUP
        assert wm.classify_warehouse("All Warehouses - WH") == WarehouseType.GROUP

    def test_pattern_matching(self):
        """Unmapped warehouses should match by pattern."""
        wm = WarehouseManager()
        # Transit patterns
        assert wm.classify_warehouse("In Transit Warehouse") == WarehouseType.IN_TRANSIT
        # WIP patterns
        assert wm.classify_warehouse("WIP Area") == WarehouseType.NOT_AVAILABLE
        # Finished patterns
        assert wm.classify_warehouse("Finished Items") == WarehouseType.NEEDS_PROCESSING
        # Default to SELLABLE
        assert wm.classify_warehouse("Custom Warehouse") == WarehouseType.SELLABLE

    def test_custom_classifications(self):
        """Test custom warehouse classifications."""
        custom_classifications = {
            "custom stores": WarehouseType.SELLABLE,
            "custom transit": WarehouseType.IN_TRANSIT,
        }
        wm = WarehouseManager(custom_classifications=custom_classifications)
        assert wm.classify_warehouse("Custom Stores") == WarehouseType.SELLABLE
        assert wm.classify_warehouse("Custom Transit") == WarehouseType.IN_TRANSIT

    def test_custom_hierarchy(self):
        """Test custom warehouse hierarchy."""
        custom_hierarchy = {"custom group": ["child1", "child2"]}
        wm = WarehouseManager(custom_hierarchy=custom_hierarchy)
        children = wm.get_child_warehouses("Custom Group")
        assert "child1" in children
        assert "child2" in children

    def test_empty_warehouse_name(self):
        """Test empty warehouse name defaults to SELLABLE."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("") == WarehouseType.SELLABLE
        assert wm.classify_warehouse(None) == WarehouseType.SELLABLE

    def test_scrap_reject_pattern(self):
        """Test scrap and reject warehouses are NOT_AVAILABLE."""
        wm = WarehouseManager()
        assert wm.classify_warehouse("Scrap Warehouse") == WarehouseType.NOT_AVAILABLE
        assert wm.classify_warehouse("Rejected Items") == WarehouseType.NOT_AVAILABLE
        assert wm.classify_warehouse("Reject Bin") == WarehouseType.NOT_AVAILABLE


class TestWarehouseGroupExpansion:
    """Test group warehouse expansion."""

    def test_is_group_warehouse(self):
        """Detect group warehouses correctly."""
        wm = WarehouseManager()
        assert wm.is_group_warehouse("All Warehouses - SD") is True
        assert wm.is_group_warehouse("Stores - SD") is False

    def test_get_child_warehouses(self):
        """Get children of group warehouse."""
        wm = WarehouseManager()
        children = wm.get_child_warehouses("All Warehouses - SD")
        assert "Stores - SD" in children
        assert "Finished Goods - SD" in children
        assert "Goods In Transit - SD" in children
        assert "Work In Progress - SD" in children

    def test_expand_warehouse_list_no_groups(self):
        """Expand list with no groups returns same list."""
        wm = WarehouseManager()
        warehouses = ["Stores - SD", "Finished Goods - SD"]
        expanded = wm.expand_warehouse_list(warehouses)
        assert expanded == warehouses

    def test_expand_warehouse_list_with_group(self):
        """Expand list with group warehouse."""
        wm = WarehouseManager()
        warehouses = ["All Warehouses - SD"]
        expanded = wm.expand_warehouse_list(warehouses)
        assert "Stores - SD" in expanded
        assert "Finished Goods - SD" in expanded
        assert "All Warehouses - SD" not in expanded

    def test_expand_warehouse_list_deduplicate(self):
        """Expand list and remove duplicates."""
        wm = WarehouseManager()
        warehouses = ["Stores - SD", "All Warehouses - SD"]
        expanded = wm.expand_warehouse_list(warehouses, deduplicate=True)
        # Should have Stores - SD only once
        assert expanded.count("Stores - SD") == 1
        assert len(expanded) == 4  # All 4 children of All Warehouses - SD

    def test_filter_available_warehouses(self):
        """Filter warehouses by type."""
        wm = WarehouseManager()
        warehouses = ["Stores - SD", "Goods In Transit - SD", "Work In Progress - SD"]
        # Default filter: SELLABLE and NEEDS_PROCESSING
        available = wm.filter_available_warehouses(warehouses)
        assert "Stores - SD" in available
        assert "Goods In Transit - SD" not in available
        assert "Work In Progress - SD" not in available

    def test_expand_no_deduplicate(self):
        """Expand list without deduplication keeps duplicates."""
        wm = WarehouseManager()
        warehouses = ["Stores - SD", "Stores - SD", "Finished Goods - SD"]
        expanded = wm.expand_warehouse_list(warehouses, deduplicate=False)
        assert expanded.count("Stores - SD") == 2  # Duplicates preserved

    def test_expand_group_no_children(self):
        """Expand group warehouse with no children defined."""
        custom_hierarchy = {"empty group": []}
        wm = WarehouseManager(custom_hierarchy=custom_hierarchy)
        # Create a custom classification for this group
        wm.classifications["empty group"] = WarehouseType.GROUP
        warehouses = ["Empty Group", "Stores - SD"]
        expanded = wm.expand_warehouse_list(warehouses)
        # Empty group should be skipped (logged as warning)
        assert "Empty Group" not in expanded
        assert "Stores - SD" in expanded


class TestWarehouseAvailabilityReasons:
    """Test warehouse availability reason generation."""

    def test_sellable_reason(self):
        """SELLABLE warehouse reason."""
        wm = WarehouseManager()
        reason = wm.get_availability_reason("Stores - SD", 100)
        assert "ready to ship" in reason.lower()

    def test_needs_processing_reason(self):
        """NEEDS_PROCESSING warehouse reason."""
        wm = WarehouseManager()
        reason = wm.get_availability_reason("Finished Goods - SD", 50)
        assert "processing" in reason.lower()

    def test_in_transit_reason(self):
        """IN_TRANSIT warehouse reason."""
        wm = WarehouseManager()
        reason = wm.get_availability_reason("Goods In Transit - SD", 75)
        assert "not ship-ready" in reason.lower() or "awaiting receipt" in reason.lower()

    def test_not_available_reason(self):
        """NOT_AVAILABLE warehouse reason."""
        wm = WarehouseManager()
        reason = wm.get_availability_reason("Work In Progress - SD", 30)
        assert "not available" in reason.lower()

    def test_group_reason(self):
        """GROUP warehouse reason."""
        wm = WarehouseManager()
        reason = wm.get_availability_reason("All Warehouses - SD", 100)
        assert "group warehouse" in reason.lower()
        assert "expand" in reason.lower()


class TestPromiseCalculationWithWarehouses:
    """Test promise calculations respect warehouse types."""

    @pytest.fixture
    def mock_supply(self):
        """Mock supply service with test data."""
        return MockSupplyService("data/Sales Invoice.csv")

    @pytest.fixture
    def promise_service(self, mock_supply):
        """Promise service with warehouse manager."""
        return PromiseService(mock_supply)

    def test_in_transit_stock_not_available_now(self, promise_service):
        """Stock in Goods In Transit should NOT be available immediately."""
        # SKU004 has 80 units in "Goods In Transit - SD" per stock.csv
        # This should NOT count as available stock
        today = date(2026, 1, 27)

        items = [ItemRequest(item_code="SKU004", qty=10, warehouse="Goods In Transit - SD")]
        rules = PromiseRules(no_weekends=False, lead_time_buffer_days=0)

        # Override _get_today
        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: today

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # IN_TRANSIT stock should NOT be used for immediate fulfillment
            # Check that any stock fulfillment did NOT come from IN_TRANSIT
            stock_sources = [f for f in result.plan[0].fulfillment if f.source == "stock"]
            for source in stock_sources:
                # Either no stock fulfillment, or stock came from a different (SELLABLE) warehouse
                assert (
                    source.warehouse != "Goods In Transit - SD"
                ), "Stock should not be allocated from IN_TRANSIT warehouse"

            # Any fulfillment should come from PO or have shortage
            if result.plan[0].shortage == 0:
                # Must be fulfilled by PO
                po_sources = [f for f in result.plan[0].fulfillment if f.source == "purchase_order"]
                assert len(po_sources) > 0, "Should be fulfilled by PO, not IN_TRANSIT stock"

        finally:
            promise_service._get_today = original_get_today

    def test_wip_stock_ignored(self, promise_service):
        """Stock in Work In Progress should be ignored."""
        # SKU001 has 120 units in "Work In Progress - SD" per stock.csv
        today = date(2026, 1, 27)

        items = [ItemRequest(item_code="SKU001", qty=10, warehouse="Work In Progress - SD")]
        rules = PromiseRules(no_weekends=False, lead_time_buffer_days=0)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: today

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # WIP stock should NOT be used for immediate fulfillment
            stock_sources = [f for f in result.plan[0].fulfillment if f.source == "stock"]
            for source in stock_sources:
                assert (
                    source.warehouse != "Work In Progress - SD"
                ), "Stock should not be allocated from WIP warehouse"

            # Any fulfillment should come from PO or have shortage
            if result.plan[0].shortage == 0:
                # Must be fulfilled by PO
                po_sources = [f for f in result.plan[0].fulfillment if f.source == "purchase_order"]
                assert len(po_sources) > 0, "Should be fulfilled by PO, not WIP stock"

        finally:
            promise_service._get_today = original_get_today

    def test_sellable_warehouse_available_immediately(self, promise_service):
        """Stock in Stores should be available immediately."""
        # SKU005 has 90 units in "Stores - SD"
        today = date(2026, 1, 27)

        items = [ItemRequest(item_code="SKU005", qty=10, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=False, lead_time_buffer_days=0)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: today

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # Should NOT have shortage - stock is available
            assert result.plan[0].shortage == 0, "SELLABLE warehouse stock should be available"

            # Should have stock fulfillment
            stock_sources = [f for f in result.plan[0].fulfillment if f.source == "stock"]
            assert len(stock_sources) > 0
            assert stock_sources[0].qty >= 10

        finally:
            promise_service._get_today = original_get_today

    def test_promise_date_never_weekend(self, promise_service):
        """Promise date should never land on Friday or Saturday."""
        today = date(2026, 1, 27)  # Monday

        items = [ItemRequest(item_code="SKU005", qty=10, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=True, lead_time_buffer_days=0)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: today

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # Promise date should not be Friday(4) or Saturday(5)
            assert result.promise_date.weekday() not in (
                4,
                5,
            ), f"Promise date {result.promise_date} falls on weekend"

        finally:
            promise_service._get_today = original_get_today

    def test_reasons_explain_warehouse_decisions(self, promise_service):
        """Reasons should explain warehouse-based decisions."""
        today = date(2026, 1, 27)

        items = [ItemRequest(item_code="SKU004", qty=10, warehouse="Goods In Transit - SD")]
        rules = PromiseRules(no_weekends=False, lead_time_buffer_days=0)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: today

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # Should have some explanation in reasons
            assert len(result.reasons) > 0, "Should have reasons explaining fulfillment"

            # Check that we don't falsely promise from IN_TRANSIT stock
            stock_sources = [f for f in result.plan[0].fulfillment if f.source == "stock"]
            for source in stock_sources:
                assert source.warehouse != "Goods In Transit - SD"

        finally:
            promise_service._get_today = original_get_today


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
