"""Unit tests for MockSupplyService - consolidated version."""
import pytest
from pathlib import Path
from src.services.mock_supply_service import MockSupplyService


pytestmark = pytest.mark.unit


class TestMockSupplyService:
    """Tests for MockSupplyService integration and edge cases."""

    def test_missing_data_file(self):
        """Test graceful handling when data file is missing."""
        service = MockSupplyService("data/nonexistent-file-xyz.csv")
        result = service.get_available_stock("ANY-ITEM")
        assert result["actual_qty"] == 0.0
        result = service.get_incoming_supply("ANY-ITEM")
        assert result["supply"] == []

    def test_with_existing_csv_and_queries(self):
        """Test loading CSV and various queries."""
        service = MockSupplyService("data/Sales Invoice.csv")
        # Verify existing item
        result = service.get_available_stock("SKU001")
        assert isinstance(result, dict)
        # Non-existent item returns zeros
        result = service.get_available_stock("NON-EXISTENT-ITEM")
        assert result["actual_qty"] == 0.0
        # Non-existent PO returns empty
        result = service.get_incoming_supply("NON-EXISTENT-ITEM")
        assert result["supply"] == []

    def test_date_filtering_and_warehouse_handling(self):
        """Test after_date filter and warehouse-specific queries."""
        from datetime import date
        service = MockSupplyService("data/Sales Invoice.csv")
        
        # Test after_date filter
        all_pos = service.get_incoming_supply("SKU001")
        filtered_pos = service.get_incoming_supply("SKU001", after_date=date(2030, 1, 1))
        assert len(filtered_pos["supply"]) <= len(all_pos["supply"])
        
        # Test specific warehouse
        result = service.get_available_stock("SKU001", warehouse="Stores - SD")
        assert "actual_qty" in result
        
        # Fallback warehouse handling
        result = service.get_available_stock("SKU001", warehouse="NON-EXISTENT-WH")
        assert isinstance(result, dict)

    def test_case_insensitive_and_sorting(self):
        """Test case-insensitive lookup and PO sorting."""
        service = MockSupplyService("data/Sales Invoice.csv")
        
        # Case insensitivity
        r_upper = service.get_available_stock("SKU001")
        r_lower = service.get_available_stock("sku001")
        r_mixed = service.get_available_stock("Sku001")
        assert r_upper == r_lower == r_mixed
        
        # PO sorting
        result = service.get_incoming_supply("SKU001")
        if len(result["supply"]) > 1:
            dates = [po["expected_date"] for po in result["supply"]]
            assert dates == sorted(dates)


class TestMockSupplyServiceParsing:
    """Tests of private parsing methods - consolidated."""

    def test_parse_stock_rows_edge_cases(self):
        """Test _parse_stock_row with valid and invalid data."""
        service = MockSupplyService("data/Sales Invoice.csv")
        initial = sum(len(v) for v in service.stock_index.values())
        
        # Valid row
        service._parse_stock_row({
            "item_code": "TEST-STOCK", "warehouse": "WH-1",
            "actual_qty": "100", "reserved_qty": "10", "projected_qty": "90"
        })
        after_valid = sum(len(v) for v in service.stock_index.values())
        assert after_valid > initial
        
        # Missing item_code (should skip)
        service._parse_stock_row({
            "item_code": "", "warehouse": "WH-1", 
            "actual_qty": "50", "reserved_qty": "5", "projected_qty": "45"
        })
        assert sum(len(v) for v in service.stock_index.values()) == after_valid
        
        # Missing warehouse (should skip)
        service._parse_stock_row({
            "item_code": "TEST-ITEM", "warehouse": "",
            "actual_qty": "50", "reserved_qty": "5", "projected_qty": "45"
        })
        assert sum(len(v) for v in service.stock_index.values()) == after_valid

    def test_safe_float_conversion(self):
        """Test _safe_float with all data types and edge cases."""
        service = MockSupplyService("data/Sales Invoice.csv")
        
        # Valid conversions
        assert service._safe_float("42.5") == 42.5
        assert service._safe_float(100) == 100.0
        assert service._safe_float("-50.5") == -50.5
        assert service._safe_float("+100.5") == 100.5
        
        # Edge cases
        assert service._safe_float("  99  ") == 99.0
        assert service._safe_float("0") == 0.0
        
        # Error cases (should return 0.0)
        assert service._safe_float(None) == 0.0
        assert service._safe_float([1, 2]) == 0.0
        assert service._safe_float({"a": 1}) == 0.0
        assert service._safe_float("not_a_number") == 0.0
        assert service._safe_float("") == 0.0

    def test_parse_po_rows_edge_cases(self):
        """Test _parse_po_row with valid and invalid data."""
        service = MockSupplyService("data/Sales Invoice.csv")
        initial = sum(len(v) for v in service.po_index.values())
        
        # Valid PO
        service._parse_po_row({
            "po_id": "PO-001", "item_code": "ITEM-PO-001",
            "qty": "50", "expected_date": "2026-03-15", "warehouse": "WH"
        })
        after_valid = sum(len(v) for v in service.po_index.values())
        assert after_valid > initial
        
        # Missing po_id (should skip)
        service._parse_po_row({
            "po_id": "", "item_code": "ITEM-NO-POID",
            "qty": "50", "expected_date": "2026-03-15", "warehouse": "WH"
        })
        assert sum(len(v) for v in service.po_index.values()) == after_valid
        
        # Missing item_code (should skip)
        service._parse_po_row({
            "po_id": "PO-002", "item_code": "",
            "qty": "50", "expected_date": "2026-03-15", "warehouse": "WH"
        })
        assert sum(len(v) for v in service.po_index.values()) == after_valid
        
        # Missing expected_date (should skip)
        service._parse_po_row({
            "po_id": "PO-003", "item_code": "ITEM-NO-DATE",
            "qty": "50", "expected_date": "", "warehouse": "WH"
        })
        assert sum(len(v) for v in service.po_index.values()) == after_valid
        
        # Invalid date (should skip)
        service._parse_po_row({
            "po_id": "PO-004", "item_code": "ITEM-BAD-DATE",
            "qty": "50", "expected_date": "not-a-date", "warehouse": "WH"
        })
        assert sum(len(v) for v in service.po_index.values()) == after_valid

    def test_parse_po_row_from_row_all_cases(self):
        """Test _parse_po_row_from_row with enriched and standard columns."""
        service = MockSupplyService("data/Sales Invoice.csv")
        
        # Enriched columns (valid)
        initial = sum(len(v) for v in service.po_index.values())
        service._parse_po_row_from_row({
            "PO_ID": "PO-ENR-001", "Item (Items)": "ITEM-ENR-001",
            "PO_Quantity": "100", "PO_Expected_Date": "2026-04-01", "PO_Warehouse": "WH"
        })
        after = sum(len(v) for v in service.po_index.values())
        assert after > initial
        
        # Fallback columns (valid) 
        service._parse_po_row_from_row({
            "po_id": "PO-FB-001", "item_code": "ITEM-FB-001",
            "qty": "75", "expected_date": "2026-04-15", "warehouse": "WH"
        })
        after_fb = sum(len(v) for v in service.po_index.values())
        assert after_fb > after
        
        # Missing fields (should skip)
        service._parse_po_row_from_row({
            "PO_ID": "", "Item (Items)": "ITEM-MISSING",
            "PO_Quantity": "100"
        })
        assert sum(len(v) for v in service.po_index.values()) == after_fb
        
        # Invalid date (should skip)
        service._parse_po_row_from_row({
            "PO_ID": "PO-BADDATE", "Item (Items)": "ITEM-BADDATE",
            "PO_Quantity": "100", "PO_Expected_Date": "invalid-date", "PO_Warehouse": "WH"
        })
        assert sum(len(v) for v in service.po_index.values()) == after_fb

    def test_po_sorting_and_retrieval(self):
        """Test that POs are sorted by expected_date when retrieved."""
        service = MockSupplyService("data/Sales Invoice.csv")
        
        # Add POs in non-chronological order
        service._parse_po_row({
            "po_id": "PO-LATE", "item_code": "SORT-TEST",
            "qty": "50", "expected_date": "2026-04-01", "warehouse": "WH"
        })
        service._parse_po_row({
            "po_id": "PO-EARLY", "item_code": "SORT-TEST",
            "qty": "50", "expected_date": "2026-02-01", "warehouse": "WH"
        })
        
        # Verify sorting
        pos = service.po_index.get("sort-test", [])
        if len(pos) >= 2:
            dates = [po["expected_date"] for po in pos]
            assert dates == sorted(dates)
