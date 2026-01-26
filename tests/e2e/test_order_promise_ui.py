"""End-to-end UI tests with Playwright."""
import pytest
from playwright.sync_api import Page, expect
from datetime import date, timedelta
import httpx
from tests.e2e.pages.erpnext_pages import LoginPage, SalesOrderListPage, SalesOrderPage
from src.config import settings


@pytest.mark.e2e
class TestOrderPromiseE2E:
    """
    End-to-end tests covering full user flow:
    1. Create Sales Order in ERPNext UI
    2. Call OTP API to calculate promise
    3. Apply promise via API
    4. Verify promise appears in ERPNext UI
    
    Prerequisites:
    - ERPNext running and accessible
    - OTP service running
    - Test credentials configured
    - Playwright installed: playwright install chromium
    
    Run with: pytest tests/e2e/ --headed (to see browser)
    """

    @pytest.fixture(scope="class")
    def base_url(self):
        """ERPNext base URL."""
        return settings.erpnext_base_url

    @pytest.fixture(scope="class")
    def otp_api_url(self):
        """OTP API base URL."""
        return f"http://localhost:{settings.otp_service_port}"

    @pytest.mark.skip(reason="Requires full ERPNext + OTP setup and test data")
    def test_create_so_and_apply_promise(self, page: Page, base_url, otp_api_url):
        """
        Full flow test:
        1. Login to ERPNext
        2. Create draft Sales Order
        3. Call OTP API to calculate promise
        4. Apply promise via API
        5. Verify in ERPNext UI
        """
        # Step 1: Login
        login_page = LoginPage(page, base_url)
        login_page.navigate()
        login_page.login(
            username=settings.erpnext_test_username,
            password=settings.erpnext_test_password
        )

        # Step 2: Create Sales Order
        so_list = SalesOrderListPage(page, base_url)
        so_list.navigate()
        so_list.create_new()

        so_page = SalesOrderPage(page, base_url)
        so_page.fill_customer("Test Customer")
        so_page.add_item("ITEM-001", 10.0)
        so_page.save()
        
        sales_order_id = so_page.get_name()
        assert sales_order_id, "Failed to create Sales Order"

        # Step 3: Calculate promise via OTP API
        with httpx.Client(base_url=otp_api_url) as client:
            promise_response = client.post(
                "/otp/promise",
                json={
                    "customer": "Test Customer",
                    "items": [
                        {
                            "item_code": "ITEM-001",
                            "qty": 10.0,
                            "warehouse": "Stores - WH"
                        }
                    ],
                    "rules": {
                        "no_weekends": True,
                        "cutoff_time": "14:00",
                        "timezone": "UTC",
                        "lead_time_buffer_days": 1
                    }
                }
            )
            
            assert promise_response.status_code == 200
            promise_data = promise_response.json()
            promise_date = promise_data["promise_date"]
            confidence = promise_data["confidence"]

        # Step 4: Apply promise via API
        with httpx.Client(base_url=otp_api_url) as client:
            apply_response = client.post(
                "/otp/apply",
                json={
                    "sales_order_id": sales_order_id,
                    "promise_date": promise_date,
                    "confidence": confidence,
                    "action": "both"
                }
            )
            
            assert apply_response.status_code == 200
            apply_data = apply_response.json()
            assert apply_data["status"] == "success"

        # Step 5: Verify in ERPNext UI
        so_page.reload()
        
        # Check if comment was added
        has_comment = so_page.has_comment_with_text(promise_date)
        assert has_comment, "Promise comment not found in Sales Order"

        # Check if custom field was set (if field exists)
        custom_field_value = so_page.get_custom_field_value("custom_otp_promise_date")
        if custom_field_value:
            assert promise_date in custom_field_value

    @pytest.mark.skip(reason="Requires full ERPNext setup")
    def test_promise_displayed_in_ui(self, page: Page, base_url, otp_api_url):
        """
        Test that promise date is displayed in Sales Order form after applying.
        
        This is a simpler version that assumes SO already exists.
        """
        # Login
        login_page = LoginPage(page, base_url)
        login_page.navigate()
        login_page.login(
            username=settings.erpnext_test_username,
            password=settings.erpnext_test_password
        )

        # Navigate to existing SO (this would be created in test setup)
        test_so_id = "SO-TEST-001"
        page.goto(f"{base_url}/app/sales-order/{test_so_id}")
        page.wait_for_load_state("networkidle")

        so_page = SalesOrderPage(page, base_url)
        
        # Check custom field
        promise_value = so_page.get_custom_field_value("custom_otp_promise_date")
        
        # If field exists and has value, verify it's a valid date
        if promise_value:
            # Should be in YYYY-MM-DD format
            assert len(promise_value) == 10
            assert promise_value.count("-") == 2

    @pytest.mark.skip(reason="Requires Material Request creation")
    def test_material_request_created(self, page: Page, base_url, otp_api_url):
        """
        Test that Material Request appears in ERPNext after procurement suggestion.
        """
        # Create MR via API
        with httpx.Client(base_url=otp_api_url) as client:
            procure_response = client.post(
                "/otp/procurement-suggest",
                json={
                    "items": [
                        {
                            "item_code": "ITEM-001",
                            "qty_needed": 5.0,
                            "required_by": str(date.today() + timedelta(days=7)),
                            "reason": "Test E2E procurement"
                        }
                    ],
                    "suggestion_type": "material_request",
                    "priority": "HIGH"
                }
            )
            
            assert procure_response.status_code == 200
            procure_data = procure_response.json()
            mr_id = procure_data["suggestion_id"]

        # Login and verify MR exists
        login_page = LoginPage(page, base_url)
        login_page.navigate()
        login_page.login(
            username=settings.erpnext_test_username,
            password=settings.erpnext_test_password
        )

        # Navigate to Material Request
        page.goto(f"{base_url}/app/material-request/{mr_id}")
        page.wait_for_load_state("networkidle")

        # Verify MR loaded successfully
        title = page.title()
        assert mr_id in title
