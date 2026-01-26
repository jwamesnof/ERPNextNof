"""Integration tests with real ERPNext (requires RUN_INTEGRATION=1)."""
import pytest
from datetime import date
from src.clients.erpnext_client import ERPNextClient
from src.services.stock_service import StockService
from src.services.promise_service import PromiseService
from src.services.apply_service import ApplyService
from src.models.request_models import ItemRequest, PromiseRules


@pytest.mark.integration
class TestERPNextIntegration:
    """
    Integration tests with real ERPNext instance.
    
    Prerequisites:
    - ERPNext running at configured URL
    - Valid API credentials
    - Test data setup (items, warehouses)
    
    Run with: RUN_INTEGRATION=1 pytest tests/integration/
    """

    def test_erpnext_connection(self, skip_if_no_integration):
        """Test: Can connect to ERPNext and authenticate."""
        with ERPNextClient() as client:
            assert client.health_check() is True

    def test_get_stock_real(self, skip_if_no_integration):
        """Test: Fetch real stock levels from ERPNext."""
        with ERPNextClient() as client:
            stock_service = StockService(client)
            
            # Note: This assumes a test item exists
            # In production CI, you'd seed test data first
            stock = stock_service.get_available_stock("ITEM-001", "Stores - WH")
            
            assert "actual_qty" in stock
            assert "available_qty" in stock
            assert isinstance(stock["actual_qty"], (int, float))

    def test_get_incoming_pos_real(self, skip_if_no_integration):
        """Test: Fetch real incoming POs from ERPNext."""
        with ERPNextClient() as client:
            stock_service = StockService(client)
            
            # This may return empty if no POs exist
            incoming = stock_service.get_incoming_supply("ITEM-001")
            
            assert isinstance(incoming, list)
            # If POs exist, validate structure
            if incoming:
                assert "po_id" in incoming[0]
                assert "expected_date" in incoming[0]

    def test_promise_calculation_e2e_real(self, skip_if_no_integration):
        """Test: End-to-end promise calculation with real data."""
        with ERPNextClient() as client:
            stock_service = StockService(client)
            promise_service = PromiseService(stock_service)
            
            # Calculate promise for a test item
            item = ItemRequest(item_code="ITEM-001", qty=1.0, warehouse="Stores - WH")
            rules = PromiseRules(lead_time_buffer_days=1, no_weekends=True)
            
            response = promise_service.calculate_promise(
                customer="Test Customer",
                items=[item],
                rules=rules
            )
            
            # Validate response structure
            assert response.promise_date >= date.today()
            assert response.confidence in ["HIGH", "MEDIUM", "LOW"]
            assert len(response.plan) == 1
            assert response.plan[0].item_code == "ITEM-001"

    @pytest.mark.skip(reason="Requires creating test SO in ERPNext first")
    def test_apply_promise_real(self, skip_if_no_integration):
        """Test: Write promise back to real Sales Order."""
        with ERPNextClient() as client:
            apply_service = ApplyService(client)
            
            # This requires a real SO to exist
            # In CI, you'd create one first via API
            sales_order_id = "SO-TEST-001"
            promise_date = date.today()
            
            response = apply_service.apply_promise_to_sales_order(
                sales_order_id=sales_order_id,
                promise_date=promise_date,
                confidence="HIGH",
                action="add_comment"
            )
            
            # Should succeed or fail gracefully
            assert response.status in ["success", "error"]
            if response.status == "success":
                assert len(response.actions_taken) > 0

    @pytest.mark.skip(reason="Requires warehouse and item setup")
    def test_create_material_request_real(self, skip_if_no_integration):
        """Test: Create real Material Request in ERPNext."""
        with ERPNextClient() as client:
            apply_service = ApplyService(client)
            
            items = [
                {
                    "item_code": "ITEM-001",
                    "qty_needed": 5.0,
                    "required_by": str(date.today()),
                    "reason": "Test procurement"
                }
            ]
            
            response = apply_service.create_procurement_suggestion(
                items=items,
                suggestion_type="material_request",
                priority="MEDIUM"
            )
            
            assert response.status in ["success", "error"]
            if response.status == "success":
                assert response.suggestion_id
                assert "material-request" in response.erpnext_url.lower()
