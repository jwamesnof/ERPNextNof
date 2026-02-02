"""
OTP Workflow Validation & Execution
====================================

This script validates and executes the complete Order Promise calculation workflow:
1. Fetch and display available Sales Orders from ERPNext
2. Allow interactive selection of Sales Order to test
3. Fetch detailed Sales Order data via REST API
4. Calculate promise date based on current stock and incoming purchase orders
5. Display detailed results with stock levels, confidence scoring, and business reasoning

Requirements:
- OTP service running on port 8001
- ERPNext accessible with valid API credentials
- Sales Orders available in ERPNext system
"""

import requests
import json
import os
from datetime import date
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:8001"
ERPNEXT_BASE_URL = os.getenv("ERPNEXT_BASE_URL", "http://localhost:8080")
ERPNEXT_API_KEY = os.getenv("ERPNEXT_API_KEY")
ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET")


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_json(data: Dict[Any, Any]):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=2, default=str))


def step0_list_sales_orders() -> List[Dict[Any, Any]]:
    """
    Step 0: Fetch and display available Sales Orders.
    
    Returns list of sales orders for user selection.
    """
    print_section("Fetching Available Sales Orders")
    print(f"Requesting: GET {BASE_URL}/otp/sales-orders?limit=20")
    
    response = requests.get(f"{BASE_URL}/otp/sales-orders?limit=20")
    
    if response.status_code != 200:
        print(f"\n❌ ERROR: Failed to fetch sales orders (status {response.status_code})")
        print(response.text)
        return []
    
    orders = response.json()
    
    if not orders:
        print("\n⚠️  No sales orders found in ERPNext")
        print(f"   Create one at: {ERPNEXT_BASE_URL}/app/sales-order")
        return []
    
    print(f"\n✅ Found {len(orders)} Sales Orders:")
    print()
    for idx, order in enumerate(orders, 1):
        status = order.get('status', 'Unknown')
        delivery = order.get('delivery_date', 'N/A')
        customer = order.get('customer', 'Unknown')
        total = order.get('grand_total', 0)
        print(f"  {idx:2d}. {order['name']:20s} | {customer:30s} | Delivery: {delivery} | ${total:,.2f} ({status})")
    
    return orders


def select_sales_order(orders: List[Dict[Any, Any]]) -> str:
    """
    Interactive selection of Sales Order.
    
    Returns selected Sales Order ID.
    """
    print_section("Select Sales Order to Test")
    
    while True:
        user_input = input(f"Enter order number (1-{len(orders)}) or order name: ").strip()
        
        # Try as order name first
        if user_input.startswith("SAL-ORD"):
            if any(o['name'] == user_input for o in orders):
                return user_input
            print(f"❌ Order '{user_input}' not in the list. Try again.")
            continue
        
        # Try as number
        try:
            idx = int(user_input)
            if 1 <= idx <= len(orders):
                return orders[idx - 1]['name']
            print(f"❌ Number must be between 1 and {len(orders)}. Try again.")
        except ValueError:
            print(f"❌ Invalid input. Enter a number (1-{len(orders)}) or order name (e.g., SAL-ORD-2026-00001)")



def step1_fetch_sales_order_details(so_id: str) -> Dict[Any, Any]:
    """
    Step 1: Fetch Sales Order details from ERPNext.
    
    This uses the new GET /otp/sales-orders/{id} endpoint to retrieve:
    - Customer information
    - All items with quantities and warehouses
    - Default settings for promise calculation
    - Associated purchase orders (if any)
    """
    print_section("STEP 1: Fetch Sales Order Details")
    print(f"Requesting: GET {BASE_URL}/otp/sales-orders/{so_id}")
    
    response = requests.get(f"{BASE_URL}/otp/sales-orders/{so_id}")
    
    if response.status_code == 404:
        print(f"\n❌ ERROR: Sales Order '{so_id}' not found in ERPNext")
        print("Please update SALES_ORDER_ID in this script with a valid Sales Order ID")
        return None
    
    if response.status_code != 200:
        print(f"\n❌ ERROR: Failed to fetch sales order (status {response.status_code})")
        print(response.text)
        return None
    
    so_details = response.json()
    
    print("\n✅ Sales Order Details Retrieved:")
    print(f"   ID: {so_details['id']}")
    print(f"   Customer: {so_details['customer_name']}")
    print(f"   Order Date: {so_details['transaction_date']}")
    print(f"   Status: {so_details['status']}")
    print(f"   Grand Total: ${so_details['grand_total']:.2f}" if so_details.get('grand_total') else "   Grand Total: N/A")
    print(f"\n   Items ({len(so_details['items'])}):")
    for idx, item in enumerate(so_details['items'], 1):
        print(f"     {idx}. {item['item_code']:15s} | Qty: {item['qty']:6.1f} {item['uom']:5s} | Warehouse: {item['warehouse']}")
    
    print(f"\n   Defaults for Promise Calculation:")
    print(f"     - Warehouse: {so_details['defaults']['warehouse']}")
    print(f"     - Delivery Model: {so_details['defaults']['delivery_model']}")
    print(f"     - Cutoff Time: {so_details['defaults']['cutoff_time']}")
    print(f"     - No Weekends: {so_details['defaults']['no_weekends']}")
    
    return so_details


def step2_check_stock_levels(so_details: Dict[Any, Any]) -> Dict[str, Dict[str, float]]:
    """
    Step 2: Check current stock levels for all items.
    
    Fetches actual, reserved, and available quantities from ERPNext.
    """
    print_section("STEP 2: Check Current Stock Levels")
    
    stock_info = {}
    
    for idx, item in enumerate(so_details['items'], 1):
        item_code = item['item_code']
        warehouse = item['warehouse']
        
        print(f"\n  [{idx}] Item: {item_code}")
        print(f"      Warehouse: {warehouse}")
        
        try:
            # Call ERPNext API directly to get bin details
            response = requests.get(
                f"{ERPNEXT_BASE_URL}/api/resource/Bin",
                params={
                    "filters": json.dumps([["item_code", "=", item_code], ["warehouse", "=", warehouse]]),
                    "fields": json.dumps(["actual_qty", "reserved_qty", "projected_qty"])
                },
                headers={
                    "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                bins = data.get('data', [])
                
                if bins:
                    bin_data = bins[0]
                    actual = bin_data.get('actual_qty', 0)
                    reserved = bin_data.get('reserved_qty', 0)
                    available = actual - reserved
                    
                    stock_info[item_code] = {
                        'actual': actual,
                        'reserved': reserved,
                        'available': available
                    }
                    
                    print(f"      Stock Status:")
                    print(f"        • Actual:    {actual:8.1f} units")
                    print(f"        • Reserved:  {reserved:8.1f} units")
                    print(f"        • Available: {available:8.1f} units")
                    
                    if available >= item['qty']:
                        print(f"        ✅ Sufficient stock ({available:.1f} >= {item['qty']:.1f})")
                    elif available > 0:
                        print(f"        ⚠️  Partial stock ({available:.1f} < {item['qty']:.1f})")
                    else:
                        print(f"        🔴 No stock available")
                else:
                    print(f"      ⚠️  No bin record found (no stock)")
                    stock_info[item_code] = {'actual': 0, 'reserved': 0, 'available': 0}
            else:
                print(f"      ❌ Failed to fetch stock (HTTP {response.status_code})")
                stock_info[item_code] = {'actual': 0, 'reserved': 0, 'available': 0}
                
        except Exception as e:
            print(f"      ❌ Error fetching stock: {e}")
            stock_info[item_code] = {'actual': 0, 'reserved': 0, 'available': 0}
    
    return stock_info


def step3_build_promise_request(so_details: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Step 3: Build promise calculation request from SO details.
    
    Auto-fills the promise request using data from the Sales Order:
    - Customer from SO
    - Items with quantities and warehouses from SO
    - Business rules from defaults
    """
    print_section("STEP 3: Build Promise Calculation Request")
    
    promise_request = {
        "customer": so_details['customer_name'],
        "items": [
            {
                "item_code": item['item_code'],
                "qty": item['qty'],
                "warehouse": item['warehouse']
            }
            for item in so_details['items']
        ],
        "rules": {
            "no_weekends": so_details['defaults']['no_weekends'],
            "cutoff_time": so_details['defaults']['cutoff_time'],
            "timezone": "UTC",
            "lead_time_buffer_days": 1
        }
    }
    
    print("\n✅ Promise Request Built:")
    print_json(promise_request)
    
    return promise_request


def step4_calculate_promise(promise_request: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Step 4: Calculate promise date.
    
    Sends the request to the OTP engine which:
    - Checks available stock for each item
    - Looks up incoming purchase orders
    - Applies business rules (cutoff time, weekends, buffer)
    - Calculates confidence level
    - Generates explanations and suggestions
    """
    print_section("STEP 4: Calculate Promise Date")
    print(f"Requesting: POST {BASE_URL}/otp/promise")
    
    response = requests.post(
        f"{BASE_URL}/otp/promise",
        json=promise_request,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"\n❌ ERROR: Promise calculation failed (status {response.status_code})")
        print(response.text)
        return None
    
    promise_response = response.json()
    
    print("\n✅ Promise Date Calculated!")
    print(f"\n   📅 PROMISE DATE: {promise_response['promise_date']}")
    print(f"   🎯 CONFIDENCE: {promise_response['confidence']}")
    
    # Check if there are any purchase orders being used
    has_incoming_supply = False
    for item_plan in promise_response['plan']:
        for fulfillment in item_plan.get('fulfillment', []):
            if fulfillment['source'] == 'purchase_order':
                has_incoming_supply = True
                break
    
    # Show incoming supply section if needed
    if has_incoming_supply:
        print(f"\n   📥 Incoming Supply (Purchase Orders):")
        for item_plan in promise_response['plan']:
            for fulfillment in item_plan.get('fulfillment', []):
                if fulfillment['source'] == 'purchase_order':
                    po_id = fulfillment.get('po_id', 'N/A')
                    qty = fulfillment.get('qty', 0)
                    avail_date = fulfillment.get('available_date', 'N/A')
                    print(f"     • {po_id:20s} | {qty:6.1f} units | Available: {avail_date}")
    
    # Show fulfillment plan
    print(f"\n   📦 Fulfillment Plan:")
    for idx, item_plan in enumerate(promise_response['plan'], 1):
        print(f"\n     [{idx}] Item: {item_plan['item_code']} (Required: {item_plan['qty_required']} units)")
        
        if item_plan['fulfillment']:
            for fulfillment in item_plan['fulfillment']:
                source = fulfillment['source']
                qty = fulfillment['qty']
                avail_date = fulfillment['available_date']
                
                if source == 'stock':
                    wh = fulfillment.get('warehouse', 'N/A')
                    print(f"         ✓ {qty:6.1f} units from STOCK")
                    print(f"           Warehouse: {wh} | Available: {avail_date}")
                elif source == 'purchase_order':
                    po_id = fulfillment.get('po_id', 'N/A')
                    print(f"         ⏳ {qty:6.1f} units from PURCHASE ORDER {po_id}")
                    print(f"           Expected: {avail_date}")
        else:
            print(f"         ⚠️  No stock or incoming supply available")
        
        if item_plan['shortage'] > 0:
            print(f"         🔴 SHORTAGE: {item_plan['shortage']:6.1f} units not covered")
    
    # Show reasoning
    if promise_response.get('reasons'):
        print(f"\n   💡 Calculation Reasoning:")
        for reason in promise_response['reasons']:
            print(f"     • {reason}")
    
    # Show blockers
    if promise_response.get('blockers'):
        print(f"\n   ⚠️  Blockers:")
        for blocker in promise_response['blockers']:
            print(f"     • {blocker}")
    
    # Show options
    if promise_response.get('options'):
        print(f"\n   💭 Suggestions to Improve Promise:")
        for option in promise_response['options']:
            print(f"     • {option['description']}")
            print(f"       Impact: {option['impact']}")
    
    return promise_response


def main():
    """Execute the complete OTP workflow validation."""
    print("\n" + "=" * 80)
    print("  🚀 OTP WORKFLOW VALIDATION & EXECUTION")
    print("=" * 80)
    print(f"\n  OTP Service: {BASE_URL}")
    print(f"  ERPNext: {ERPNEXT_BASE_URL}")
    print(f"  Today's Date: {date.today()}")
    
    # Step 0: List and select Sales Order
    orders = step0_list_sales_orders()
    if not orders:
        return
    
    sales_order_id = select_sales_order(orders)
    
    # Step 1: Fetch Sales Order
    so_details = step1_fetch_sales_order_details(sales_order_id)
    if not so_details:
        return
    
    # Step 2: Check stock levels
    stock_info = step2_check_stock_levels(so_details)
    
    # Step 3: Build Promise Request
    promise_request = step3_build_promise_request(so_details)
    
    # Step 4: Calculate Promise
    promise_response = step4_calculate_promise(promise_request)
    if not promise_response:
        return
    
    # Summary
    print_section("✨ WORKFLOW COMPLETE")
    print(f"""
    Summary:
    --------
    Sales Order: {so_details['id']}
    Customer: {so_details['customer_name']}
    Items: {len(so_details['items'])}
    
    Promise Date: {promise_response['promise_date']}
    Confidence: {promise_response['confidence']}
    
    Next Steps:
    -----------
    The frontend can now:
    1. Display the promise date to the user
    2. Show confidence level and detailed reasoning
    3. Apply this promise back to the Sales Order in ERPNext (POST /otp/apply)
    4. Create procurement suggestions for shortages (POST /otp/procurement-suggest)
    """)
    
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to OTP service at " + BASE_URL)
        print("Make sure the service is running: uvicorn src.main:app --reload --port 8001")
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
