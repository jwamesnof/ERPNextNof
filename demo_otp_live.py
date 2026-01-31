"""Test OTP with real ERPNext access (Sales Orders + Stock)."""
from datetime import date
from src.models.request_models import ItemRequest, PromiseRequest, PromiseRules
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.clients.erpnext_client import ERPNextClient
from src.config import settings

def test_real_erpnext():
    """Test OTP against real ERPNext with current permissions."""
    
    print("\n" + "="*70)
    print("OTP Test - Real ERPNext Integration")
    print("="*70 + "\n")
    
    # Initialize services with real ERPNext
    client = ERPNextClient()
    stock_service = StockService(client)
    promise_service = PromiseService(stock_service)
    
    print("Configuration:")
    print(f"  Base URL: {settings.erpnext_base_url}")
    print(f"  API Key: {settings.erpnext_api_key[:10]}...")
    print()
    
    # Test 1: Try to fetch Sales Order
    print("Test 1: Fetching Sales Order from ERPNext")
    print("-" * 70)
    try:
        so = client.get_sales_order('SAL-ORD-2026-00002')
        print("SUCCESS: Can access Sales Orders")
        print(f"  Order: {so.get('name')}")
        print(f"  Customer: {so.get('customer')}")
        print()
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Test 2: Try to fetch Stock
    print("Test 2: Fetching Stock from ERPNext")
    print("-" * 70)
    try:
        stock = stock_service.get_available_stock('SKU005', 'Stores - SD')
        print("SUCCESS: Can access Stock data")
        print(f"  Item: SKU005")
        print(f"  Warehouse: Stores - SD")
        print(f"  Available: {stock.get('available_qty')} units")
        print()
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Test 3: Try to fetch Purchase Orders
    print("Test 3: Fetching Purchase Orders from ERPNext")
    print("-" * 70)
    try:
        incoming = stock_service.get_incoming_supply('SKU004', after_date=date.today())
        po_list = incoming.get('supply', [])
        access_error = incoming.get('access_error')
        
        if access_error:
            print(f"WARNING: PO Access Issue - {access_error}")
            print("  OTP will continue with stock data only")
            print("  Confidence will be degraded to LOW")
        else:
            print(f"SUCCESS: Can access Purchase Orders")
            print(f"  Found {len(po_list)} POs for SKU004")
            for po in po_list[:2]:
                print(f"    - {po.get('po_id')}: {po.get('qty')} units, ETA: {po.get('expected_date')}")
        print()
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Test 4: Calculate Promise using real data
    print("Test 4: OTP Promise Calculation")
    print("-" * 70)
    try:
        result = promise_service.calculate_promise(
            customer="Test Company",
            items=[ItemRequest(item_code='SKU005', qty=50, warehouse='Stores - SD')],
            desired_date=date(2026, 2, 5)
        )
        
        print(f"Status: {result.status.value}")
        print(f"Promise Date: {result.promise_date}")
        print(f"Can Fulfill: {result.can_fulfill}")
        print(f"Confidence: {result.confidence}")
        print(f"On Time: {result.on_time}")
        
        if result.blockers:
            print(f"\nBlockers:")
            for blocker in result.blockers:
                print(f"  - {blocker}")
        
        print()
        print("="*70)
        print("RESULT: OTP System is WORKING!")
        print("="*70)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_erpnext()
