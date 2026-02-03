# Fix: Purchase Order Item Permission Error (403)

## Problem
The OTP backend cannot read Purchase Order items due to permission error:
- Endpoint: `/api/resource/Purchase Order Item`
- Status: **403 Permission Denied**
- Reason: Your API user doesn't have "Read" permission on the "Purchase Order Item" doctype

## Solution Steps

### Step 1: Open Role Permission Manager
1. Go to ERPNext Dashboard
2. Search for **"Role Permission Manager"**
3. Click to open

### Step 2: Find Purchase Order Item
1. In the search box, type **"Purchase Order Item"**
2. Click on the result to select it

### Step 3: Grant Read Permission
1. Find the role your API user has (likely **"System Manager"** or a custom role)
2. Check the **"Read"** checkbox for that role
3. Save the permissions

### Step 4: Verify
If you need to verify the fix worked:
1. Run this command in terminal:
```bash
cd /c/Users/NofJawamis/Desktop/ERPNextNof && source .venv/Scripts/activate && python -c "
import requests, json, os
from dotenv import load_dotenv
load_dotenv()
params = {
    'filters': json.dumps([['item_code', '=', 'SKU001'], ['docstatus', '=', 1]]),
    'fields': json.dumps(['parent', 'item_code', 'qty']),
    'limit_page_length': 5
}
response = requests.get(
    f'{os.getenv(\"ERPNEXT_BASE_URL\")}/api/resource/Purchase Order Item',
    params=params,
    headers={'Authorization': f'token {os.getenv(\"ERPNEXT_API_KEY\")}:{os.getenv(\"ERPNEXT_API_SECRET\")}'}
)
print('✅ Success!' if response.status_code == 200 else f'❌ Status {response.status_code}')
print(f'POs found: {len(response.json()) if response.status_code == 200 else \"N/A\"}')
"
```

2. If you see `✅ Success!` and a number > 0, permissions are fixed!

## After Fixing Permissions

Once permissions are granted, the OTP workflow will:
1. Show incoming purchase orders when stock is insufficient
2. Calculate promise dates using available PO supply
3. Demonstrate proper shortage handling

Then re-run the validation:
```bash
cd /c/Users/NofJawamis/Desktop/ERPNextNof && source .venv/Scripts/activate && python validate_otp_workflow.py
```
