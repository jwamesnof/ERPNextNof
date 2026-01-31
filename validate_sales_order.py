"""Live validation script for OTP with real ERPNext Sales Orders."""
import os
from datetime import datetime, date
from typing import Dict, Any, List

from src.clients.erpnext_client import ERPNextClient, ERPNextClientError
from src.services.promise_service import PromiseService
from src.models.request_models import PromiseRules, ItemRequest
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


def fetch_recent_sales_orders(client: ERPNextClient, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch recent Sales Orders from ERPNext."""
    try:
        print_section("Fetching Recent Sales Orders")
        
        orders = client.get_sales_order_list(
            filters=[],
            fields=["name", "customer", "creation", "delivery_date", "grand_total", "docstatus"],
            limit=limit,
            order_by="name asc"
        )
        
        print(f"OK Found {len(orders)} recent sales orders")
        for idx, order in enumerate(orders, 1):
            status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
            status_text = status_map.get(order.get('docstatus'), 'Unknown')
            delivery = order.get('delivery_date', 'N/A')
            print(f"  {idx}. {order.get('name')} - {order.get('customer')} - Delivery: {delivery} ({status_text})")
        
        return orders
    
    except Exception as e:
        print(f"ERROR Error fetching sales orders: {e}")
        return []


def fetch_sales_order_details(client: ERPNextClient, so_name: str) -> Dict[str, Any]:
    """Fetch full details of a specific Sales Order."""
    try:
        print_section(f"Fetching Sales Order Details: {so_name}")
        
        response = client.client.get(f"/api/resource/Sales Order/{so_name}")
        order = client._handle_response(response)
        
        print(f"OK Customer: {order.get('customer')}")
        print(f"OK Created: {order.get('creation')}")
        print(f"OK Desired Delivery: {order.get('delivery_date', 'Not specified')}")
        print(f"OK Items: {len(order.get('items', []))}")
        
        return order
    
    except Exception as e:
        print(f"ERROR Error fetching sales order details: {e}")
        return {}


def test_otp_calculation(order: Dict[str, Any]):
    """Run OTP calculation on sales order items."""
    try:
        print_section("Running OTP Calculation")
        
        customer = order.get("customer")
        items = order.get("items", [])
        
        if not items:
            print("ERROR No items found in sales order")
            return
        
        # Create OTP request items
        otp_items = []
        for item in items:
            otp_items.append({
                "item_code": item.get("item_code"),
                "qty": item.get("qty", 1),
                "warehouse": item.get("warehouse") or "Stores - SD"
            })
        
        print(f"\nTesting {len(otp_items)} items for customer: {customer}")
        
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
            print(f"\n{'-' * 80}")
            print(f"Item {idx}/{len(otp_items)}: {item_data['item_code']} (Qty: {item_data['qty']})")
            print(f"{'-' * 80}")
            
            try:
                # Show live stock snapshot
                stock_snapshot = stock_service.get_available_stock(
                    item_code=item_data['item_code'],
                    warehouse=item_data['warehouse']
                )
                print(f"  Stock in {item_data['warehouse']}:")
                print(f"     • actual: {stock_snapshot.get('actual_qty')}")
                print(f"     • reserved: {stock_snapshot.get('reserved_qty')}")
                print(f"     • available: {stock_snapshot.get('available_qty')}")
                
                # Get incoming supply
                incoming = stock_service.get_incoming_supply(item_data['item_code'])
                print(f"  Incoming Supply:")
                if incoming.get('access_error'):
                    error_type = incoming['access_error']
                    if error_type == 'permission_denied':
                        print(f"     WARNING: Permission denied (403) - cannot access PO data")
                    else:
                        print(f"     WARNING: Access error - cannot retrieve PO data")
                elif incoming['supply']:
                    for po in incoming['supply']:
                        print(f"     • {po['po_id']}: {po['qty']} units -> {po['expected_date']}")
                else:
                    print(f"     • (No open purchase orders)")
                
                # Run OTP calculation
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
                print(f"\n  OTP Result:")
                print(f"     • Can Fulfill: {promise.can_fulfill}")
                print(f"     • Confidence: {promise.confidence}")
                
                if promise.promise_date:
                    weekday = promise.promise_date.weekday()
                    day_name = promise.promise_date.strftime("%A")
                    print(f"     • Promise Date: {promise.promise_date} ({day_name})")
                    
                    # Verify working day
                    if rules.no_weekends and weekday in (4, 5):
                        print(f"     WARNING: Date is {day_name} (WEEKEND)")
                    else:
                        print(f"     OK Working day confirmed")
                else:
                    print(f"     • Promise Date: NULL (cannot fulfill)")
                
                # Show plan
                if promise.plan:
                    item_plan = promise.plan[0]
                    print(f"     • Fulfillment Plan:")
                    if item_plan.fulfillment:
                        for source in item_plan.fulfillment:
                            print(f"       - {source.source}: {source.qty} units (ship-ready: {source.ship_ready_date})")
                    if item_plan.shortage > 0:
                        print(f"       - SHORTAGE: {item_plan.shortage} units")
                
                # Show reasoning
                if promise.reasons:
                    print(f"     • Reasoning:")
                    for reason in promise.reasons:
                        print(f"       - {reason}")
                
                # Show blockers
                if promise.blockers:
                    print(f"     • ⛔ Blockers:")
                    for blocker in promise.blockers:
                        print(f"       - {blocker}")
                
            except Exception as e:
                print(f"  ERROR Error calculating promise: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print_section("Summary")
        if results:
            fulfilled = sum(1 for r in results if r.can_fulfill)
            print(f"  OK Can Fulfill: {fulfilled}/{len(results)}")
            print(f"  ERROR Cannot Fulfill: {len(results) - fulfilled}/{len(results)}")
            
            # Confidence breakdown
            high = sum(1 for r in results if r.confidence == "HIGH")
            medium = sum(1 for r in results if r.confidence == "MEDIUM")
            low = sum(1 for r in results if r.confidence == "LOW")
            print(f"  Confidence: HIGH={high}, MEDIUM={medium}, LOW={low}")
        
    except Exception as e:
        print(f"ERROR Error in OTP calculation: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main execution."""
    from src.config import settings
    
    print_section("OTP Validation with ERPNext Sales Orders")
    print(f"Connecting to: {settings.erpnext_base_url}")
    print(f"Using API Key: {settings.erpnext_api_key[:10]}...")
    print("Calendar: Sunday-Thursday workweek (Fri-Sat weekends)")
    print("Warehouse: Classification system active")
    print("Input: Sales Orders (NOT Sales Invoices)")
    
    try:
        # Initialize ERPNext client
        client = ERPNextClient()
        
        # Test connection
        print_section("Testing Connection")
        response = client.client.get("/api/method/frappe.auth.get_logged_user")
        user = client._handle_response(response)
        print(f"OK Connected as: {user}")
        
        # Fetch recent sales orders
        orders = fetch_recent_sales_orders(client, limit=10)
        
        if not orders:
            print("\nWARNING: No sales orders found.")
            print("    Create one at: http://localhost:8080/app/sales-order")
            return
        
        # Prompt user to select order
        print_section("Select Sales Order to Test")
        print("Enter order number (1-{}) or order name: ".format(len(orders)), end="")
        
        choice = input().strip()
        
        selected_order = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(orders):
                selected_order = orders[idx]
        else:
            # Search by name
            selected_order = next((o for o in orders if o.get("name") == choice), None)
        
        if not selected_order:
            print(f"ERROR Invalid selection: {choice}")
            return
        
        # Fetch full order details
        order_details = fetch_sales_order_details(client, selected_order["name"])
        
        if not order_details:
            return
        
        # Run OTP calculation
        test_otp_calculation(order_details)
        
        print_section("Complete")
        print("OK OTP validation complete!")
        print("Review results above for fulfillment status and confidence levels")
        
    except ERPNextClientError as e:
        print(f"\nERROR ERPNext Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check ERPNext is running: http://localhost:8080")
        print("  2. Verify API credentials are correct")
        print("  3. Ensure Sales Orders exist in the system")
        print("  4. Check API user has permission to read Sales Orders, Bins, and Purchase Orders")
    except Exception as e:
        print(f"\nERROR Unexpected Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
