# Demo Data Integration

## Overview

Sales Invoices CSV data from ERPNext has been successfully integrated into the OTP application. The CSV file contains 5 sales invoices with historical transaction data that can be used for testing and validation of the Order Promise Engine.

## Data Source

- **File**: `Sales Invoice.csv`
- **Location**: Project root directory
- **Format**: Wide CSV export from ERPNext
- **Records**: 5 invoices with multiple line items

## Data Summary

| Metric | Value |
|--------|-------|
| Total Invoices | 5 |
| Total Amount | 363,000 ILS |
| Total Items (qty) | 620 |
| Unique Customers | 3 |
| Unique Item SKUs | 5 |

### Customers

- Grant Plastics Ltd.
- Palmer Productions Ltd.
- West View Software Ltd.

### Items (SKUs)

- SKU001 (variety of products)
- SKU003
- SKU004 (Smartphone)
- SKU005
- SKU008

## API Endpoints

All demo data endpoints are prefixed with `/demo/` and return JSON responses.

### 1. Summary Endpoint

**Request:**
```
GET /demo/invoices/summary
```

**Response Example:**
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

**Request:**
```
GET /demo/invoices/all
```

**Response Example:**
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
    }
  ]
}
```

### 3. Invoices by Customer

**Request:**
```
GET /demo/invoices/customer/{customer_name}
```

**Example:**
```
GET /demo/invoices/customer/Grant%20Plastics%20Ltd.
```

**Response Example:**
```json
{
  "customer": "Grant Plastics Ltd.",
  "count": 2,
  "invoices": [...]
}
```

### 4. Invoices by Item

**Request:**
```
GET /demo/invoices/item/{item_code}
```

**Example:**
```
GET /demo/invoices/item/SKU001
```

**Response Example:**
```json
{
  "item_code": "SKU001",
  "count": 1,
  "invoices": [...]
}
```

## Implementation Details

### Service Layer

**File**: `src/services/csv_data_loader.py`

The `CSVDataLoader` class handles all CSV parsing and data access:

- `__init__(csv_filename)` - Initialize with CSV file path
- `load_sales_invoices()` - Load and parse all invoices
- `get_invoice_summary()` - Get aggregated statistics
- `get_invoices_by_customer(customer_name)` - Filter by customer
- `get_invoices_by_item(item_code)` - Find invoices containing an item

### Route Layer

**File**: `src/routes/demo_data.py`

FastAPI router exposing 4 endpoints:
- `GET /demo/invoices/summary`
- `GET /demo/invoices/all`
- `GET /demo/invoices/customer/{customer_name}`
- `GET /demo/invoices/item/{item_code}`

### Integration

**File**: `src/main.py`

Routes are registered in the main FastAPI application:
```python
from src.routes import demo_data
app.include_router(demo_data.router)
```

## Testing the Endpoints

Using curl:

```bash
# Summary
curl http://localhost:8001/demo/invoices/summary

# All invoices
curl http://localhost:8001/demo/invoices/all

# By customer
curl "http://localhost:8001/demo/invoices/customer/Grant%20Plastics%20Ltd."

# By item
curl http://localhost:8001/demo/invoices/item/SKU001
```

## Use Cases

1. **Testing Promise Calculations**: Use invoice data to test OTP promise date calculations
2. **Validation Data**: Compare against real historical transactions
3. **Demo/Reference**: Show sample data in documentation and examples
4. **API Testing**: Verify endpoint functionality with real data structure
5. **Performance Testing**: Load test with actual invoice complexity

## Future Enhancements

- [ ] Add pagination support for large result sets
- [ ] Add filtering by date range
- [ ] Add filtering by status (Paid/Unpaid)
- [ ] Add sorting options
- [ ] Cache parsed CSV data in memory
- [ ] Support for refreshing CSV data without restart
- [ ] Add export endpoints (CSV, Excel)

## Data Validation

All data has been validated:
- ✅ CSV file exists and is readable
- ✅ 5 invoices parsed successfully
- ✅ Items extracted correctly with nested column handling
- ✅ Totals and amounts calculated correctly
- ✅ Customer names extracted and deduplicated
- ✅ All endpoints return valid JSON responses
