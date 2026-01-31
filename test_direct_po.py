"""Quick test - Direct Purchase Order list access."""
import httpx
from src.config import settings

API_KEY = settings.erpnext_api_key
API_SECRET = settings.erpnext_api_secret
BASE_URL = settings.erpnext_base_url

headers = {'Authorization': f'token {API_KEY}:{API_SECRET}'}

print("Testing Direct Purchase Order List Access")
print("=" * 70)

# Try simple list without filters
try:
    response = httpx.get(
        f"{BASE_URL}/api/resource/Purchase Order",
        headers=headers,
        params={"limit_page_length": 5},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"SUCCESS! Found {len(data.get('data', []))} Purchase Orders")
        for po in data.get('data', [])[:3]:
            print(f"  - {po.get('name')}")
    else:
        print(f"FAILED: {response.text[:200]}")
except Exception as e:
    print(f"ERROR: {e}")
