"""Test Purchase Order access after permission update."""
from src.clients.erpnext_client import ERPNextClient
from src.config import settings

print('Testing ERPNext Purchase Order Access')
print('=' * 70)
print(f'Base URL: {settings.erpnext_base_url}')
print(f'API Key: {settings.erpnext_api_key[:10]}...')
print()

client = ERPNextClient()

# Test Purchase Order access
print('Testing Purchase Order Access:')
print('-' * 70)
try:
    # Try to get POs for an item
    pos = client.get_incoming_purchase_orders('SKU001')
    print('SUCCESS! Purchase Order access granted!')
    print(f'Found {len(pos)} Purchase Orders for SKU001')
    print()
    
    if pos:
        print('Purchase Order Details:')
        for idx, po in enumerate(pos[:3], 1):
            print(f'  {idx}. PO: {po.get("po_id")}')
            print(f'     Item: {po.get("item_code")}')
            print(f'     Qty: {po.get("qty")}')
            print(f'     Expected Date: {po.get("expected_date")}')
            print(f'     Warehouse: {po.get("warehouse")}')
            print()
    
    # Try another item
    print('Testing with SKU004 (Smartphone):')
    pos2 = client.get_incoming_purchase_orders('SKU004')
    print(f'Found {len(pos2)} Purchase Orders for SKU004')
    
    if pos2:
        for idx, po in enumerate(pos2[:2], 1):
            print(f'  {idx}. PO {po.get("po_id")}: {po.get("qty")} units, ETA: {po.get("expected_date")}')
    
    print()
    print('=' * 70)
    print('PURCHASE ORDER ACCESS: FULLY OPERATIONAL!')
    print('=' * 70)
    print()
    print('OTP can now:')
    print('  - See incoming inventory from suppliers')
    print('  - Calculate promises based on PO ETAs')
    print('  - Provide HIGH confidence ratings')
    print('  - Plan fulfillment beyond current stock')
    
except Exception as e:
    error_msg = str(e)
    print()
    if '403' in error_msg:
        print('STILL BLOCKED: Permission Denied (403)')
        print('The API user still lacks Purchase Order read permission')
        print('Please ensure "Purchase User" or "Purchase Manager" role is assigned')
    elif '404' in error_msg:
        print('ACCESS OK: No POs found (404 is normal if no POs exist)')
    else:
        print(f'ERROR: {e}')
