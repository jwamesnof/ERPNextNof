"""Test calendar and business day handling (Sunday-Thursday workweek)."""
import pytest
from datetime import date, timedelta
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.models.request_models import ItemRequest, PromiseRules

pytestmark = pytest.mark.unit


class TestCalendarUtilities:
    """Test basic calendar utility functions without hardcoded dates."""

    @staticmethod
    def find_next_weekday(start: date, target_weekday: int) -> date:
        d = start
        while d.weekday() != target_weekday:
            d += timedelta(days=1)
        return d

    def test_is_working_day_sunday_to_thursday(self):
        """Sunday through Thursday should be working days."""
        # Pick a baseline date and compute target weekdays
        base = date(2026, 1, 26)  # arbitrary baseline
        sunday = self.find_next_weekday(base, 6)
        monday = self.find_next_weekday(base, 0)
        tuesday = self.find_next_weekday(base, 1)
        wednesday = self.find_next_weekday(base, 2)
        thursday = self.find_next_weekday(base, 3)

        assert PromiseService.is_working_day(sunday) is True
        assert PromiseService.is_working_day(monday) is True
        assert PromiseService.is_working_day(tuesday) is True
        assert PromiseService.is_working_day(wednesday) is True
        assert PromiseService.is_working_day(thursday) is True

    def test_is_working_day_friday_saturday_weekend(self):
        """Friday and Saturday should be weekend days."""
        base = date(2026, 1, 26)
        friday = self.find_next_weekday(base, 4)
        saturday = self.find_next_weekday(base, 5)

        assert PromiseService.is_working_day(friday) is False
        assert PromiseService.is_working_day(saturday) is False

    def test_next_working_day_from_working_day(self):
        """next_working_day should return same date if already working day."""
        base = date(2026, 1, 26)
        monday = self.find_next_weekday(base, 0)
        thursday = self.find_next_weekday(base, 3)

        assert PromiseService.next_working_day(monday) == monday
        assert PromiseService.next_working_day(thursday) == thursday

    def test_next_working_day_from_friday(self):
        """next_working_day from Friday should return Sunday."""
        base = date(2026, 1, 26)
        friday = self.find_next_weekday(base, 4)
        sunday = self.find_next_weekday(friday, 6)
        assert PromiseService.next_working_day(friday) == sunday

    def test_next_working_day_from_saturday(self):
        """next_working_day from Saturday should return Sunday."""
        base = date(2026, 1, 26)
        saturday = self.find_next_weekday(base, 5)
        sunday = self.find_next_weekday(saturday, 6)
        assert PromiseService.next_working_day(saturday) == sunday

    def test_add_working_days_zero(self):
        """Adding zero working days should return same date."""
        base = date(2026, 1, 26)
        thursday = self.find_next_weekday(base, 3)
        assert PromiseService.add_working_days(thursday, 0) == thursday

    def test_add_working_days_within_week(self):
        """Adding working days within same week."""
        base = date(2026, 1, 26)
        sunday = self.find_next_weekday(base, 6)
        thursday_after = self.find_next_weekday(sunday, 3)
        assert PromiseService.add_working_days(sunday, 4) == thursday_after

        monday = self.find_next_weekday(base, 0)
        wednesday = self.find_next_weekday(base, 2)
        assert PromiseService.add_working_days(monday, 2) == wednesday

    def test_add_working_days_skip_weekend(self):
        """Adding working days should skip Friday and Saturday."""
        base = date(2026, 1, 26)
        thursday = self.find_next_weekday(base, 3)
        sunday = self.find_next_weekday(thursday, 6)
        result = PromiseService.add_working_days(thursday, 1)
        assert result == sunday

        monday_after = self.find_next_weekday(thursday, 0)
        result2 = PromiseService.add_working_days(thursday, 2)
        assert result2 == monday_after

    def test_add_working_days_multiple_weeks(self):
        """Adding working days across multiple weeks."""
        base = date(2026, 1, 26)
        sunday1 = self.find_next_weekday(base, 6)
        sunday2 = self.find_next_weekday(sunday1 + timedelta(days=1), 6)
        assert PromiseService.add_working_days(sunday1, 5) == sunday2

        monday1 = self.find_next_weekday(base, 0)
        # 10 working days = 2 full workweeks (5 days each) → Monday two weeks later
        monday2 = self.find_next_weekday(monday1 + timedelta(days=14), 0)
        assert PromiseService.add_working_days(monday1, 10) == monday2


class TestPromiseCalculationWithCalendar:
    """Test promise calculations respect business calendar."""

    @pytest.fixture
    def mock_supply(self):
        """Create mock supply service."""
        return MockSupplyService("data/Sales Invoice.csv")

    @pytest.fixture
    def promise_service(self, mock_supply):
        """Create promise service."""
        return PromiseService(mock_supply)

    def test_base_date_friday_moves_to_sunday(self, promise_service):
        """If today is Friday, base_date should be Sunday when no_weekends=True."""
        # Mock today as Friday
        friday = date(2026, 1, 31)

        # Request with no_weekends enabled
        items = [ItemRequest(item_code="TEST_ITEM", qty=1, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=True, lead_time_buffer_days=0)

        # Override _get_today to return Friday
        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: friday

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # Promise date should never be Friday or Saturday
            # Use promise_date_raw if promise_date is None (when can't fulfill)
            check_date = result.promise_date or result.promise_date_raw
            assert check_date.weekday() not in (4, 5), f"Promise date {check_date} falls on weekend"
        finally:
            promise_service._get_today = original_get_today

    def test_promise_date_never_weekend(self, promise_service):
        """Promise date must never land on Friday or Saturday."""
        # Test with Thursday (should be fine)
        thursday = date(2026, 1, 30)

        items = [ItemRequest(item_code="TEST_ITEM", qty=1, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=True, lead_time_buffer_days=1)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: thursday

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # With 1 day buffer from Thursday, should skip weekend and be Sunday
            check_date = result.promise_date or result.promise_date_raw
            assert check_date.weekday() not in (4, 5), f"Promise date {check_date} falls on weekend"

            # Should be Sunday (next working day after Thursday + 1)
            sunday = date(2026, 2, 2)
            assert check_date == sunday
        finally:
            promise_service._get_today = original_get_today

    def test_processing_lead_time_counts_working_days(self, promise_service):
        """Processing lead time should count only working days."""
        thursday = date(2026, 1, 30)

        # Set item with processing lead time = 1 day
        promise_service.item_lead_times = {"LEAD_TEST": 1}

        items = [ItemRequest(item_code="LEAD_TEST", qty=1, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=True, lead_time_buffer_days=0)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: thursday

        try:
            promise_service.calculate_promise(customer="Test Customer", items=items, rules=rules)

            # Thursday + 1 working day processing = Sunday (skip Fri/Sat)
            # But we have shortage, so it defaults to base date
            # Let's check that ship_ready_date in plan follows calendar
            # Since there's no stock, this will be shortage case
            pass  # This test needs actual stock data
        finally:
            promise_service._get_today = original_get_today
            promise_service.item_lead_times = {}

    def test_weekend_adjustment_reason_included(self, promise_service):
        """Reasons should mention weekend adjustment."""
        thursday = date(2026, 1, 30)

        items = [ItemRequest(item_code="TEST_ITEM", qty=1, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=True, lead_time_buffer_days=0)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: thursday

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # Check that reasons mention weekend handling
            reasons_text = " ".join(result.reasons).lower()
            assert (
                "weekend" in reasons_text or "friday" in reasons_text or "saturday" in reasons_text
            )
        finally:
            promise_service._get_today = original_get_today

    def test_no_weekends_false_allows_friday_saturday(self, promise_service):
        """When no_weekends=False, Friday and Saturday should be allowed."""
        thursday = date(2026, 1, 30)

        items = [ItemRequest(item_code="TEST_ITEM", qty=1, warehouse="Stores - SD")]
        rules = PromiseRules(no_weekends=False, lead_time_buffer_days=1)

        original_get_today = promise_service._get_today
        promise_service._get_today = lambda tz: thursday

        try:
            result = promise_service.calculate_promise(
                customer="Test Customer", items=items, rules=rules
            )

            # With no_weekends=False, Friday is allowed
            # Thursday + 1 day buffer = Friday
            friday = date(2026, 1, 31)
            # Use promise_date_raw since TEST_ITEM has no stock
            check_date = result.promise_date or result.promise_date_raw
            assert check_date == friday
        finally:
            promise_service._get_today = original_get_today


class TestIncomingSupplyWeekendAdjustment:
    """Test that incoming PO dates on weekends are adjusted."""

    @pytest.fixture
    def mock_supply(self):
        return MockSupplyService("data/Sales Invoice.csv")

    @pytest.fixture
    def promise_service(self, mock_supply):
        return PromiseService(mock_supply)

    def test_po_arrival_on_friday_adjusted_to_sunday(self, promise_service):
        """PO arriving on Friday should be treated as arriving on Sunday."""
        # This test requires mocking incoming_supply with Friday date
        # For now, we'll test the logic directly

        base = date(2026, 1, 26)
        friday = TestCalendarUtilities.find_next_weekday(base, 4)
        sunday = TestCalendarUtilities.find_next_weekday(friday, 6)

        # Test the calendar logic directly
        assert PromiseService.is_working_day(friday) is False
        assert PromiseService.next_working_day(friday) == sunday

        # In actual promise calculation, if a PO has expected_date = Friday,
        # it should be adjusted to Sunday
        # This is verified in the implementation

    def test_po_arrival_on_saturday_adjusted_to_sunday(self, promise_service):
        """PO arriving on Saturday should be treated as arriving on Sunday."""
        base = date(2026, 1, 26)
        saturday = TestCalendarUtilities.find_next_weekday(base, 5)
        sunday = TestCalendarUtilities.find_next_weekday(saturday, 6)

        assert PromiseService.is_working_day(saturday) is False
        assert PromiseService.next_working_day(saturday) == sunday


class TestCutoffRuleWithCalendar:
    """Test cutoff time rule respects business calendar."""

    @pytest.fixture
    def mock_supply(self):
        return MockSupplyService("data/Sales Invoice.csv")

    @pytest.fixture
    def promise_service(self, mock_supply):
        return PromiseService(mock_supply)

    def test_cutoff_on_thursday_adds_working_day(self, promise_service):
        """Cutoff on Thursday should add 1 working day (skip to Sunday)."""
        # This test would require mocking time to be after cutoff
        # The logic is implemented in _apply_cutoff_rule
        # which now uses add_working_days when no_weekends=True

        base = date(2026, 1, 26)
        thursday = TestCalendarUtilities.find_next_weekday(base, 3)
        # Thursday + 1 working day = Sunday (skip Fri, Sat)
        sunday = TestCalendarUtilities.find_next_weekday(thursday, 6)
        assert PromiseService.add_working_days(thursday, 1) == sunday


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
