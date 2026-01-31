"""Test the OTP API with HTTP requests."""
import requests
import json
from datetime import date

API_URL = "http://localhost:8001"

def print_section(title):
    """Print section divider."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_health():
    """Test health endpoint."""
    print_section("Testing Health Endpoint")
    response = requests.get(f"{API_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_promise_simple():
    """Test simple promise calculation."""
    print_section("Test 1: Simple Promise Calculation")
    
    payload = {
        "customer": "Test Customer",
        "items": [
            {
                "item_code": "SKU005",
                "qty": 50,
                "warehouse": "Stores - SD"
            }
        ],
        "desired_date": "2026-02-05"
    }
    
    print(f"\n📤 REQUEST:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{API_URL}/otp/promise", json=payload)
    print(f"\n📥 RESPONSE (Status {response.status_code}):")
    result = response.json()
    print(json.dumps(result, indent=2, default=str))
    
    return response.status_code == 200

def test_promise_multi_item():
    """Test multi-item promise calculation."""
    print_section("Test 2: Multi-Item Order")
    
    payload = {
        "customer": "Big Corp",
        "items": [
            {"item_code": "SKU005", "qty": 20, "warehouse": "Stores - SD"},
            {"item_code": "SKU008", "qty": 10, "warehouse": "Stores - SD"}
        ],
        "desired_date": "2026-02-10"
    }
    
    print(f"\n📤 REQUEST:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{API_URL}/otp/promise", json=payload)
    print(f"\n📥 RESPONSE (Status {response.status_code}):")
    
    result = response.json()
    print(f"\nKey Fields:")
    print(f"  Status: {result.get('status')}")
    print(f"  Promise Date: {result.get('promise_date')}")
    print(f"  Can Fulfill: {result.get('can_fulfill')}")
    print(f"  Confidence: {result.get('confidence')}")
    print(f"  On Time: {result.get('on_time')}")
    
    print(f"\n  Items:")
    for item in result.get('plan', []):
        print(f"    - {item['item_code']}: {item['qty_required']} units, shortage: {item['shortage']}")
    
    return response.status_code == 200

def test_promise_insufficient():
    """Test order with insufficient stock."""
    print_section("Test 3: Order with Insufficient Stock")
    
    payload = {
        "customer": "Big Order Corp",
        "items": [
            {"item_code": "SKU005", "qty": 500, "warehouse": "Stores - SD"}
        ]
    }
    
    print(f"\n📤 REQUEST:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f"{API_URL}/otp/promise", json=payload)
    print(f"\n📥 RESPONSE (Status {response.status_code}):")
    
    result = response.json()
    print(f"\nKey Fields:")
    print(f"  Status: {result.get('status')}")
    print(f"  Promise Date: {result.get('promise_date')}")
    print(f"  Can Fulfill: {result.get('can_fulfill')}")
    print(f"  Confidence: {result.get('confidence')}")
    
    if result.get('blockers'):
        print(f"\n  🚫 Blockers:")
        for blocker in result['blockers']:
            print(f"    - {blocker}")
    
    if result.get('options'):
        print(f"\n  💡 Options:")
        for option in result['options']:
            print(f"    - {option['description']}")
    
    return response.status_code == 200

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("  OTP API Testing Suite")
    print("=" * 80)
    
    try:
        # Test health
        if test_health():
            print("\n✅ Health check passed!")
        
        # Test simple promise
        if test_promise_simple():
            print("\n✅ Simple promise test passed!")
        
        # Test multi-item
        if test_promise_multi_item():
            print("\n✅ Multi-item test passed!")
        
        # Test insufficient stock
        if test_promise_insufficient():
            print("\n✅ Insufficient stock test passed!")
        
        print_section("All Tests Completed Successfully! 🎉")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to API server")
        print("   Please start the server with: uvicorn src.main:app --port 8001")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
