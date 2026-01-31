"""Live validation script for OTP with real ERPNext data."""
import os
import sys
from datetime import datetime, date
from typing import Dict, Any, List
import json

# Set credentials before importing
os.environ["ERPNEXT_BASE_URL"] = "http://localhost:8080"
os.environ["ERPNEXT_API_KEY"] = "44137efbddf113a"
os.environ["ERPNEXT_API_SECRET"] = "89a1be678b591f2"
os.environ["USE_MOCK_SUPPLY"] = "False"  # Use real ERPNext data

from src.clients.erpnext_client import ERPNextClient, ERPNextClientError
from src.services.promise_service import PromiseService
from src.models.request_models import PromiseRequest, PromiseRules
from src.services.stock_service import StockService
from src.utils.warehouse_utils import default_warehouse_manager


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_item(label: str, value: Any, indent: int = 0):
    """Print formatted key-value pair."""
    spaces = "  " * indent
    print(f"{spaces}{label}: {value}")


def fetch_recent_invoices(client: ERPNextClient, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch recent Sales Invoices from ERPNext."""
    try:
        print_section("Fetching Recent Sales Invoices")
        
        # ERPNext API endpoint for Sales Invoices
        response = client.client.get(
            "/api/resource/Sales Invoice",
            params={
                "fields": '["name","customer","posting_date","grand_total","status"]',
                "limit_page_length": limit,
                "order_by": "creation desc",
                "filters": '[]'
            }
        )
        
        data = client._handle_response(response)
        invoices = data if isinstance(data, list) else data.get("data", [])
        
        print(f"✅ Found {len(invoices)} recent invoices")
        for idx, inv in enumerate(invoices, 1):
            print(f"  {idx}. {inv.get('name')} - {inv.get('customer')} - {inv.get('posting_date')} ({inv.get('status')})")
        
        return invoices
    
    except Exception as e:
        print(f"❌ Error fetching invoices: {e}")
        return []


def fetch_invoice_details(client: ERPNextClient, invoice_name: str) -> Dict[str, Any]:
    """Fetch full details of a specific Sales Invoice."""
    try:
        print_section(f"Fetching Invoice Details: {invoice_name}")
        
        response = client.client.get(f"/api/resource/Sales Invoice/{invoice_name}")
        invoice = client._handle_response(response)
        
        print(f"✅ Customer: {invoice.get('customer')}")
        print(f"✅ Date: {invoice.get('posting_date')}")
        print(f"✅ Items: {len(invoice.get('items', []))}")
        
        return invoice
    
    except Exception as e:
        print(f"❌ Error fetching invoice details: {e}")
        return {}


def test_otp_calculation(invoice: Dict[str, Any]):
    """Run OTP calculation on invoice items."""
    try:
        print_section("Running OTP Calculation")
        
        customer = invoice.get("customer")
        items = invoice.get("items", [])
        
        if not items:
            print("❌ No items found in invoice")
            return
        
        # Create OTP request
        otp_items = []
        for item in items:
            otp_items.append({
                "item_code": item.get("item_code"),
                "qty": item.get("qty", 1),
                "warehouse": item.get("warehouse") or "Stores - SD"
            })
        
        print(f"\n📦 Testing {len(otp_items)} items for customer: {customer}")
        
        # Initialize services with ERPNext client
        client = ERPNextClient()
        stock_service = StockService(erpnext_client=client)
        promise_service = PromiseService(
            stock_service=stock_service,
            warehouse_manager=default_warehouse_manager
        )
        
        # Define rules with calendar handling
        rules = PromiseRules(
            no_weekends=True,  # Sunday-Thursday workweek
            lead_time_buffer_days=1,
            cutoff_time="14:00"
        )
        
        # Calculate promise for each item
        results = []
        for idx, item_data in enumerate(otp_items, 1):
            print(f"\n{'─' * 80}")
            print(f"Item {idx}/{len(otp_items)}: {item_data['item_code']}")
            print(f"{'─' * 80}")
            
            try:
                from src.models.request_models import ItemRequest

                # Show live stock snapshot before calculating promise
                stock_snapshot = stock_service.get_available_stock(
                    item_code=item_data['item_code'],
                    warehouse=item_data['warehouse']
                )
                print(f"  📊 Live Stock -> actual: {stock_snapshot.get('actual_qty')}, reserved: {stock_snapshot.get('reserved_qty')}, available: {stock_snapshot.get('available_qty')}")
                
                item_request = ItemRequest(
                    item_code=item_data['item_code'],
                    qty=item_data['qty'],
                    warehouse=item_data['warehouse']
                )
                
                promise = promise_service.calculate_promise(
                    customer=customer,
                    items=[item_request],
                    rules=rules
                )
                results.append(promise)
                
                # Display results
                item_plan = promise.plan[0]
                print(f"  📅 Promise Date: {promise.promise_date}")
                print(f"  📦 Quantity: {item_data['qty']}")
                print(f"  🏭 Warehouse: {item_data['warehouse']}")
                print(f"  🔍 Warehouse Type: {default_warehouse_manager.classify_warehouse(item_data['warehouse']).value}")
                print(f"  💪 Confidence: {promise.confidence}")
                
                can_fulfill = item_plan.shortage == 0
                if can_fulfill:
                    print(f"  ✅ CAN FULFILL")
                    print(f"  📊 Fulfillment Sources: {len(item_plan.fulfillment)}")
                    for source in item_plan.fulfillment:
                        print(f"     • {source.source}: {source.qty} (ship-ready: {source.ship_ready_date})")
                else:
                    print(f"  ❌ CANNOT FULFILL")
                    print(f"  ⚠️  Shortage: {item_plan.shortage}")
                
                # Display reasoning
                if promise.reasons:
                    print(f"  💬 Reasoning:")
                    for reason in promise.reasons:
                        print(f"     • {reason}")
                
                # Check if promise date is a working day
                if rules.no_weekends:
                    weekday = promise.promise_date.weekday()
                    day_name = promise.promise_date.strftime("%A")
                    if weekday in (4, 5):  # Friday or Saturday
                        print(f"  ⚠️  WARNING: Promise date is {day_name} (WEEKEND) - Should be working day!")
                    else:
                        print(f"  ✅ Promise date is {day_name} (Working day)")
                
            except Exception as e:
                print(f"  ❌ Error calculating promise: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print_section("Summary")
        fulfilled = sum(1 for r in results if r.plan[0].shortage == 0)
        print(f"  ✅ Fulfilled: {fulfilled}/{len(results)}")
        print(f"  ❌ Cannot fulfill: {len(results) - fulfilled}/{len(results)}")
        
    except Exception as e:
        print(f"❌ Error in OTP calculation: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main execution."""
    print_section("Live OTP Validation with ERPNext")
    print("📍 Connecting to: http://localhost:8080")
    print("🔑 Using API Key: 44137efbddf113a")
    print("📅 Calendar: Sunday-Thursday workweek (Fri-Sat weekends)")
    print("🏭 Warehouse: Classification system active")
    
    try:
        # Initialize ERPNext client
        client = ERPNextClient()
        
        # Test connection
        print_section("Testing Connection")
        response = client.client.get("/api/method/frappe.auth.get_logged_user")
        user = client._handle_response(response)
        print(f"✅ Connected as: {user}")
        
        # Fetch recent invoices
        invoices = fetch_recent_invoices(client, limit=10)
        
        if not invoices:
            print("\n⚠️  No invoices found. Create one at: http://localhost:8080/app/sales-invoice")
            return
        
        # Prompt user to select invoice
        print_section("Select Invoice to Test")
        print("Enter invoice number (1-{}) or invoice name: ".format(len(invoices)), end="")
        
        choice = input().strip()
        
        selected_invoice = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(invoices):
                selected_invoice = invoices[idx]
        else:
            # Search by name
            selected_invoice = next((inv for inv in invoices if inv.get("name") == choice), None)
        
        if not selected_invoice:
            print(f"❌ Invalid selection: {choice}")
            return
        
        # Fetch full invoice details
        invoice_details = fetch_invoice_details(client, selected_invoice["name"])
        
        if not invoice_details:
            return
        
        # Run OTP calculation
        test_otp_calculation(invoice_details)
        
        print_section("Complete")
        print("✅ Live validation complete!")
        print("📊 Check results above for warehouse and calendar handling")
        
    except ERPNextClientError as e:
        print(f"\n❌ ERPNext Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check ERPNext is running: http://localhost:8080")
        print("  2. Verify API credentials are correct")
        print("  3. Ensure network connectivity")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
