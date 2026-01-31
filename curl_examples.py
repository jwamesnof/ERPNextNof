"""Test desired_date feature via HTTP API."""
import requests
import json
from datetime import date, timedelta

base_url = 'http://localhost:8001/otp/promise'
headers = {'Content-Type': 'application/json'}

print('=' * 80)
print('DESIRED DATE FEATURE - API TESTING')
print('=' * 80)

# Test 1: No desired_date
print('\n📋 TEST 1: No desired_date (baseline)')
print('-' * 80)
data1 = {
    'customer': 'Grant Plastics Ltd.',
    'items': [{'item_code': 'SKU001', 'qty': 10, 'warehouse': 'Goods In Transit - SD'}],
    'rules': {'no_weekends': False, 'lead_time_buffer_days': 0}
}
try:
    r1 = requests.post(base_url, json=data1, timeout=5)
    result1 = r1.json()
    print(f'Status: {r1.status_code}')
    print(f'  Promise Date: {result1["promise_date"]}')
    print(f'  On Time: {result1.get("on_time")}')
    print(f'  Desired Date: {result1.get("desired_date")}')
except Exception as e:
    print(f'Error: {e}')

# Test 2: LATEST_ACCEPTABLE - on time
print('\n📋 TEST 2: LATEST_ACCEPTABLE mode - ON TIME')
print('-' * 80)
today = date(2026, 1, 26)
desired_far = (today + timedelta(days=10)).isoformat()
data2 = {
    'customer': 'Grant Plastics Ltd.',
    'items': [{'item_code': 'SKU001', 'qty': 10, 'warehouse': 'Goods In Transit - SD'}],
    'desired_date': desired_far,
    'rules': {
        'no_weekends': False,
        'lead_time_buffer_days': 0,
        'desired_date_mode': 'LATEST_ACCEPTABLE'
    }
}
try:
    r2 = requests.post(base_url, json=data2, timeout=5)
    result2 = r2.json()
    print(f'Status: {r2.status_code}')
    print(f'  Desired Date: {result2.get("desired_date")}')
    print(f'  Promise Date: {result2["promise_date"]}')
    print(f'  On Time: {result2.get("on_time")}')
    print(f'  Mode: {result2.get("desired_date_mode")}')
except Exception as e:
    print(f'Error: {e}')

# Test 3: NO_EARLY_DELIVERY - adjust to desired
print('\n📋 TEST 3: NO_EARLY_DELIVERY mode - ADJUST TO DESIRED')
print('-' * 80)
data3 = {
    'customer': 'Grant Plastics Ltd.',
    'items': [{'item_code': 'SKU001', 'qty': 10, 'warehouse': 'Goods In Transit - SD'}],
    'desired_date': desired_far,
    'rules': {
        'no_weekends': False,
        'lead_time_buffer_days': 0,
        'desired_date_mode': 'NO_EARLY_DELIVERY'
    }
}
try:
    r3 = requests.post(base_url, json=data3, timeout=5)
    result3 = r3.json()
    print(f'Status: {r3.status_code}')
    print(f'  Desired Date: {result3.get("desired_date")}')
    print(f'  Promise Date Raw: {result3.get("promise_date_raw")}')
    print(f'  Promise Date Final: {result3["promise_date"]}')
    print(f'  Adjusted: {result3.get("adjusted_due_to_no_early_delivery")}')
    print(f'  On Time: {result3.get("on_time")}')
except Exception as e:
    print(f'Error: {e}')

# Test 4: STRICT_FAIL - should raise error
print('\n📋 TEST 4: STRICT_FAIL mode - LATE (should fail)')
print('-' * 80)
desired_soon = (today + timedelta(days=0)).isoformat()
data4 = {
    'customer': 'Grant Plastics Ltd.',
    'items': [{'item_code': 'SKU001', 'qty': 10, 'warehouse': 'Goods In Transit - SD'}],
    'desired_date': desired_soon,
    'rules': {
        'no_weekends': False,
        'lead_time_buffer_days': 0,
        'desired_date_mode': 'STRICT_FAIL'
    }
}
try:
    r4 = requests.post(base_url, json=data4, timeout=5)
    if r4.status_code == 500:
        print(f'Status: {r4.status_code} (Expected - STRICT_FAIL raises error)')
        error_detail = r4.json().get('detail', 'No detail')
        print(f'  Error: {error_detail[:200]}...')
    else:
        result4 = r4.json()
        print(f'Status: {r4.status_code} (Expected 500)')
except Exception as e:
    print(f'Error caught (expected): {str(e)[:100]}')

print('\n' + '=' * 80)
print('ALL TESTS COMPLETED')
print('=' * 80)
