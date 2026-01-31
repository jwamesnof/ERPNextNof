"""Debug Purchase Order permissions."""
import httpx
import json

API_KEY = "267adb5cb038698"
API_SECRET = "77793bae3b7b161"
BASE_URL = "http://localhost:8080"

headers = {
    'Authorization': f'token {API_KEY}:{API_SECRET}'
}

print("="*70)
print("Purchase Order Permission Debug")
print("="*70)

# Check current user
print("\n1. Current User:")
response = httpx.get(f"{BASE_URL}/api/method/frappe.auth.get_logged_user", headers=headers, timeout=10)
print(f"   User: {response.json()['message']}")

# Check user roles
print("\n2. User Roles:")
response = httpx.get(
    f"{BASE_URL}/api/resource/User/Administrator",
    headers=headers,
    timeout=10
)
user_data = response.json()['data']
print(f"   Roles: {[role['role'] for role in user_data.get('roles', [])]}")

# Try to list Purchase Orders with different methods
print("\n3. Testing Purchase Order Access:")

# Method 1: Direct resource endpoint
print("\n   Method 1: Direct resource endpoint")
try:
    response = httpx.get(
        f"{BASE_URL}/api/resource/Purchase Order",
        headers=headers,
        params={"limit_page_length": 1},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {json.dumps(response.json(), indent=2)[:200]}")
    else:
        print(f"   Error: {response.text[:200]}")
except Exception as e:
    print(f"   Exception: {e}")

# Method 2: Using filters
print("\n   Method 2: Using get_list method")
try:
    response = httpx.get(
        f"{BASE_URL}/api/method/frappe.client.get_list",
        headers=headers,
        params={
            "doctype": "Purchase Order",
            "fields": json.dumps(["name"]),
            "limit_page_length": 1
        },
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {json.dumps(response.json(), indent=2)[:200]}")
    else:
        print(f"   Error: {response.text[:200]}")
except Exception as e:
    print(f"   Exception: {e}")

# Check if Purchase Order doctype exists
print("\n4. Checking Purchase Order DocType:")
try:
    response = httpx.get(
        f"{BASE_URL}/api/resource/DocType/Purchase Order",
        headers=headers,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    print(f"   DocType exists: {response.status_code == 200}")
except Exception as e:
    print(f"   Exception: {e}")

print("\n" + "="*70)
