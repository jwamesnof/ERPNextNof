# Demo Data API Testing Guide

## Quick Start

The OTP application is running with Sales Invoices demo data accessible via REST API endpoints.

### Test Environment

- **Server**: http://127.0.0.1:8001
- **Protocol**: HTTP
- **Data Format**: JSON
- **Status**: ✅ Running

## Endpoint Testing

### 1. Summary Endpoint

Get aggregated statistics about all invoices.

```bash
curl http://127.0.0.1:8001/demo/invoices/summary | python -m json.tool
```

**Response** (200 OK):
```json
{
  "total_invoices": 5,
  "total_amount": 363000.0,
  "total_items": 620,
  "unique_customers": 3,
  "unique_items": 5,
  "customers": [
    "Grant Plastics Ltd.",
    "Palmer Productions Ltd.",
    "West View Software Ltd."
  ],
  "items": [
    "SKU001",
    "SKU003",
    "SKU004",
    "SKU005",
    "SKU008"
  ]
}
```

### 2. All Invoices Endpoint

Retrieve complete list of all invoices with line items.

```bash
curl http://127.0.0.1:8001/demo/invoices/all | python -m json.tool | head -50
```

**Response Structure**:
```json
{
  "count": 5,
  "invoices": [
    {
      "id": "ACC-SINV-2026-00005",
      "date": "2026-11-02",
      "customer": "Grant Plastics Ltd.",
      "customer_id": "Grant Plastics Ltd.",
      "company": "Samana (Demo)",
      "status": "Unpaid",
      "total_qty": 20.0,
      "grand_total": 20000.0,
      "currency": "ILS",
      "posting_date": "11:35:12.961489",
      "items": [
        {
          "item_code": "SKU004",
          "item_name": "Smartphone",
          "qty": 20.0,
          "rate": 1000.0,
          "amount": 20000.0
        }
      ]
    },
    // ... more invoices
  ]
}
```

### 3. Filter by Customer

Find all invoices for a specific customer.

```bash
# Grant Plastics Ltd.
curl "http://127.0.0.1:8001/demo/invoices/customer/Grant%20Plastics%20Ltd." | python -m json.tool

# West View Software Ltd.
curl "http://127.0.0.1:8001/demo/invoices/customer/West%20View%20Software%20Ltd." | python -m json.tool

# Palmer Productions Ltd.
curl "http://127.0.0.1:8001/demo/invoices/customer/Palmer%20Productions%20Ltd." | python -m json.tool
```

**Response**:
```json
{
  "customer": "Grant Plastics Ltd.",
  "count": 2,
  "invoices": [ ... ]
}
```

### 4. Filter by Item Code

Find all invoices containing a specific item.

```bash
# SKU001
curl http://127.0.0.1:8001/demo/invoices/item/SKU001 | python -m json.tool

# SKU004 (Smartphone)
curl http://127.0.0.1:8001/demo/invoices/item/SKU004 | python -m json.tool
```

**Response**:
```json
{
  "item_code": "SKU001",
  "count": 1,
  "invoices": [ ... ]
}
```

## Test Scenarios

### Scenario 1: Customer Analysis

**Objective**: Analyze purchasing patterns by customer

```bash
# Get all customers
curl -s http://127.0.0.1:8001/demo/invoices/summary | python -c "
import json, sys
data = json.load(sys.stdin)
for customer in data['customers']:
    print(f'Customer: {customer}')
"

# For each customer, get their invoices
for customer in "Grant Plastics Ltd." "West View Software Ltd." "Palmer Productions Ltd."; do
  echo "=== $customer ==="
  curl -s "http://127.0.0.1:8001/demo/invoices/customer/$(echo $customer | sed 's/ /%20/g')" | \
    python -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Invoices: {data[\"count\"]}')
total = sum(inv['grand_total'] for inv in data['invoices'])
print(f'  Total Amount: {total} ILS')
"
done
```

### Scenario 2: Item Availability Analysis

**Objective**: Determine which items are most sold

```bash
# Get all items
curl -s http://127.0.0.1:8001/demo/invoices/summary | python -c "
import json, sys
data = json.load(sys.stdin)
print('Items in invoices:')
for item in sorted(data['items']):
    print(f'  - {item}')
"

# Get frequency for each item
for item in SKU001 SKU003 SKU004 SKU005 SKU008; do
  count=$(curl -s "http://127.0.0.1:8001/demo/invoices/item/$item" | python -c "import json, sys; print(json.load(sys.stdin)['count'])")
  echo "$item: $count invoices"
done
```

### Scenario 3: Revenue Analysis

**Objective**: Calculate revenue metrics

```bash
curl -s http://127.0.0.1:8001/demo/invoices/all | python -c "
import json, sys
data = json.load(sys.stdin)

# Calculate metrics
total_amount = sum(inv['grand_total'] for inv in data['invoices'])
avg_amount = total_amount / len(data['invoices'])
paid_count = sum(1 for inv in data['invoices'] if inv['status'] == 'Paid')
unpaid_count = sum(1 for inv in data['invoices'] if inv['status'] == 'Unpaid')

print(f'Total Invoices: {data[\"count\"]}')
print(f'Total Revenue: {total_amount:,.0f} ILS')
print(f'Average Per Invoice: {avg_amount:,.0f} ILS')
print(f'Paid: {paid_count}')
print(f'Unpaid: {unpaid_count}')
"
```

### Scenario 4: Promise Date Testing

**Objective**: Use demo invoice items to test OTP promise calculations

```bash
# Get an invoice's items
ITEMS=$(curl -s http://127.0.0.1:8001/demo/invoices/all | python -c "
import json, sys
data = json.load(sys.stdin)
items = data['invoices'][0]['items']
for item in items:
    print(f'{item[\"item_code\"]}:{item[\"qty\"]}')
" | head -1)

# Test OTP with demo data
curl -X POST http://127.0.0.1:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d "{
    \"items\": [
      {
        \"item_code\": \"SKU001\",
        \"qty\": 10,
        \"warehouse\": \"Stores - WH\"
      }
    ],
    \"rules\": {
      \"no_weekends\": true,
      \"cutoff_time\": \"14:00\",
      \"timezone\": \"UTC\",
      \"lead_time_buffer_days\": 1
    }
  }" | python -m json.tool
```

## Verification Checklist

- [ ] **Summary endpoint**: Returns 5 invoices
- [ ] **All invoices endpoint**: Returns complete invoice list
- [ ] **Customer filter**: Returns correct number of invoices per customer
  - [ ] Grant Plastics Ltd. = 2 invoices
  - [ ] West View Software Ltd. = expected count
  - [ ] Palmer Productions Ltd. = expected count
- [ ] **Item filter**: Returns invoices containing specific items
  - [ ] SKU001 appears in at least 1 invoice
  - [ ] SKU004 appears in invoices
- [ ] **Data validation**: All amounts, quantities are numeric
- [ ] **JSON format**: All responses are valid JSON
- [ ] **Response times**: All endpoints respond within 1 second
- [ ] **Error handling**: Invalid customer/item returns appropriate response

## Troubleshooting

### Server Not Responding

If `curl: (7) Failed to connect to 127.0.0.1 port 8001`:

```bash
# Check if server is running
lsof -i :8001

# Start the server
cd /c/Users/NofJawamis/Desktop/ERPNextNof
python -m uvicorn src.main:app --host 127.0.0.1 --port 8001
```

### 404 Not Found

If receiving `{"detail": "Not Found"}`:

1. Verify endpoint path is correct
2. Check URL encoding for customer names (spaces → %20)
3. Ensure server was restarted after code changes

### No Data Returned

If getting empty response:

1. Verify CSV file exists: `Sales Invoice.csv` in project root
2. Check CSV file has data: `head -3 Sales\ Invoice.csv`
3. Verify CSVDataLoader can parse: `python -c "from src.services.csv_data_loader import CSVDataLoader; print(CSVDataLoader('Sales Invoice.csv').get_invoice_summary())"`

## Integration with OTP

Use demo data to test the full promise workflow:

```bash
# 1. Get demo invoice item
INVOICE=$(curl -s http://127.0.0.1:8001/demo/invoices/all | python -c "
import json, sys
data = json.load(sys.stdin)
print(data['invoices'][0]['items'][0]['item_code'])
")

# 2. Calculate promise for that item
curl -X POST http://127.0.0.1:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d "{\"items\": [{\"item_code\": \"$INVOICE\", \"qty\": 5}]}" | python -m json.tool

# 3. Apply the promise
curl -X POST http://127.0.0.1:8001/otp/apply \
  -H "Content-Type: application/json" \
  -d '{
    "sales_order_id": "DEMO-SO-001",
    "promise_date": "2026-02-15",
    "confidence": "MEDIUM",
    "action": "both"
  }' | python -m json.tool
```

## Next Steps

1. **Load more data**: Add more CSV exports from ERPNext
2. **Cache optimization**: Implement in-memory caching for CSV data
3. **Real-time updates**: Add webhook support for CSV data refresh
4. **Advanced filtering**: Add date range and status filters
5. **Export functionality**: Add CSV/Excel export endpoints
