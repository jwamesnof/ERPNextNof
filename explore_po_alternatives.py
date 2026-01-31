"""Test PO access with direct query instead of list."""
from src.clients.erpnext_client import ERPNextClient
from src.config import settings

print('Testing ERPNext Purchase Order Query (Alternative Method)')
print('=' * 70)
print(f'Base URL: {settings.erpnext_base_url}')
print(f'API Key: {settings.erpnext_api_key[:10]}...')
print()

client = ERPNextClient()

# Test 1: Get a specific PO if we know the ID
print('Test 1: Fetching a specific Purchase Order')
print('-' * 70)
try:
    po = client.client.get("/api/resource/Purchase Order/PUR-ORD-2026-00001")
    data = client._handle_response(po)
    print('SUCCESS! Can fetch specific PO')
    print(f'PO Name: {data.get("name")}')
    print(f'Supplier: {data.get("supplier")}')
    print(f'Status: {data.get("status")}')
    print()
except Exception as e:
    print(f'Failed to fetch specific PO: {e}')
    print()

# Test 2: Try to get PO list with filters
print('Test 2: Querying PO list with filters')
print('-' * 70)
try:
    import json
    params = {
        "filters": json.dumps([["docstatus", "=", 1]]),  # Only submitted POs
        "fields": json.dumps(["name", "supplier", "status", "creation"]),
        "limit_page_length": 5
    }
    po_list = client.client.get("/api/resource/Purchase Order", params=params)
    data = client._handle_response(po_list)
    pos = data if isinstance(data, list) else data.get("data", [])
    print(f'SUCCESS! Found {len(pos)} Purchase Orders')
    for po in pos[:3]:
        print(f'  - {po.get("name")}')
except Exception as e:
    if '403' in str(e):
        print('Still getting 403 - List permission issue')
    else:
        print(f'Error: {e}')
    print()

# Test 3: Check if we can query any other purchase doctype
print('Test 3: Testing alternative - Purchase Receipt (if available)')
print('-' * 70)
try:
    import json
    params = {
        "filters": json.dumps([]),
        "fields": json.dumps(["name", "supplier"]),
        "limit_page_length": 3
    }
    pr_list = client.client.get("/api/resource/Purchase Receipt", params=params)
    data = client._handle_response(pr_list)
    prs = data if isinstance(data, list) else data.get("data", [])
    print(f'Found {len(prs)} Purchase Receipts')
except Exception as e:
    if '403' in str(e):
        print('Purchase Receipt also blocked (consistent permission issue)')
    else:
        print(f'Error: {e}')
