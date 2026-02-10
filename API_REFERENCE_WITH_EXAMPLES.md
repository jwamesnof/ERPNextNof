# 📚 API Reference & Usage Examples

## Overview

The **Order Promise Engine (OTP)** provides a **RESTful API** for calculating delivery dates and managing order promises. All endpoints return JSON and include comprehensive error handling.

**Base URL**: `http://localhost:8001`  
**Documentation**: `http://localhost:8001/docs` (Swagger UI)  
**OpenAPI Schema**: `http://localhost:8001/openapi.json`

---

## Table of Contents
1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [Stock Query Endpoints](#stock-query-endpoints)
4. [Error Handling](#error-handling)
5. [Request Examples](#request-examples)
6. [Response Examples](#response-examples)
7. [Real-World Scenarios](#real-world-scenarios)
8. [Rate Limiting](#rate-limiting)

---

## Authentication

The OTP service uses **HTTP Basic Auth** via the ERPNext API credentials configured in `.env`:

```bash
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret
```

**Note**: The OTP service itself doesn't require authentication. All requests are anonymous. The API key/secret are only used for internal ERPNext communication.

---

## Core Endpoints

### 1. Calculate Promise Date

**Endpoint**: `POST /otp/promise`

**Purpose**: Calculate delivery date for a sales order

**Request Body**:
```json
{
  "customer": "string (required)",
  "items": [
    {
      "item_code": "string (required)",
      "qty": "number (required, > 0)",
      "warehouse": "string (required)"
    }
  ],
  "desired_date": "string (optional, ISO 8601: YYYY-MM-DD)",
  "rules": {
    "no_weekends": "boolean (default: true)",
    "cutoff_time": "string (default: 14:00, HH:MM format)",
    "timezone": "string (default: UTC)",
    "lead_time_buffer_days": "integer (default: 1, >= 0)",
    "processing_lead_time_days": "integer (default: 1, >= 0)",
    "desired_date_mode": "string (default: LATEST_ACCEPTABLE)"
  }
}
```

**Response** (200 OK):
```json
{
  "status": "OK | CANNOT_FULFILL | CANNOT_PROMISE_RELIABLY",
  "promise_date": "2026-02-17 | null",
  "promise_date_raw": "2026-02-17",
  "desired_date": "2026-02-20",
  "desired_date_mode": "LATEST_ACCEPTABLE",
  "on_time": "boolean | null",
  "adjusted_due_to_no_early_delivery": "boolean",
  "can_fulfill": "boolean",
  "confidence": "HIGH | MEDIUM | LOW",
  "plan": [
    {
      "item_code": "string",
      "requested_qty": "number",
      "fulfilled_qty": "number",
      "shortage": "number",
      "fulfillment_sources": [
        {
          "source_type": "Stock | PurchaseOrder",
          "warehouse": "string",
          "qty": "number",
          "available_date": "2026-02-17",
          "confidence": "HIGH | MEDIUM | LOW"
        }
      ]
    }
  ],
  "reasons": ["string"],
  "blockers": ["string"],
  "options": [
    {
      "option_type": "string",
      "description": "string",
      "risk_level": "LOW | MEDIUM | HIGH"
    }
  ]
}
```

**HTTP Status Codes**:
- `200`: Success (promise calculated)
- `400`: Invalid request (missing fields, bad types)
- `422`: Validation error (qty <= 0, invalid date)
- `503`: ERPNext unavailable

**Business Logic**:
- Queries ERPNext for stock levels and purchase orders
- Calculates earliest fulfillment date based on available supply
- Applies business rules (weekends, lead time, cutoffs)
- Returns multiple fulfillment options if available

---

### 2. Apply Promise to Sales Order

**Endpoint**: `POST /otp/apply`

**Purpose**: Write calculated promise back to ERPNext Sales Order

**Request Body**:
```json
{
  "sales_order_name": "string (required, e.g. 'SO-00001')",
  "promise_date": "string (required, YYYY-MM-DD)",
  "confidence": "HIGH | MEDIUM | LOW (required)"
}
```

**Response** (200 OK):
```json
{
  "status": "SUCCESS | FAILED | PARTIAL",
  "message": "Promise applied successfully",
  "sales_order_name": "SO-00001",
  "updated_fields": ["promise_date"],
  "errors": []
}
```

**HTTP Status Codes**:
- `200`: Success
- `400`: Invalid request
- `403`: Permission denied (can't write to SO)
- `404`: Sales Order not found
- `503`: ERPNext unavailable

**Notes**:
- Requires write permissions on Sales Order in ERPNext
- Creates audit trail in ERPNext
- Validates promise date before writing

---

### 3. Generate Procurement Suggestion

**Endpoint**: `POST /otp/procurement-suggestion`

**Purpose**: Get recommendations for purchase orders to cover shortage

**Request Body**:
```json
{
  "items": [
    {
      "item_code": "string",
      "qty": "number",
      "warehouse": "string"
    }
  ],
  "desired_date": "string (optional)"
}
```

**Response** (200 OK):
```json
{
  "status": "SUCCESS | NO_SHORTAGE",
  "shortages": [
    {
      "item_code": "ITEM-001",
      "shortage_qty": 25.0,
      "suggested_po_qty": 30.0,
      "suggested_supplier": "SUPPLIER-A",
      "suggested_eta": "2026-02-20",
      "priority": "HIGH | MEDIUM | LOW"
    }
  ],
  "total_procurement_cost": 5000.00,
  "estimated_delivery": "2026-02-20"
}
```

---

### 4. Health Check

**Endpoint**: `GET /health`

**Purpose**: Check if service and ERPNext are operational

**Response** (200 OK):
```json
{
  "status": "healthy | degraded | down",
  "service": "OTP",
  "version": "0.1.0",
  "erpnext_connected": true,
  "message": "All systems operational",
  "timestamp": "2026-02-07T10:30:00Z"
}
```

**HTTP Status Codes**:
- `200`: Service is operational
- `503`: Service or ERPNext unavailable

**Use Cases**:
- Kubernetes liveness probes
- Load balancer health checks
- Monitoring dashboards

---

## Stock Query Endpoints

### 5. Get Stock Levels

**Endpoint**: `GET /api/items/stock/{item_code}/{warehouse}`

**Purpose**: Query current inventory levels

**Parameters**:
- `item_code` (path): Item code (e.g., "ITEM-001")
- `warehouse` (path): Warehouse name (e.g., "Stores - WH")

**Response** (200 OK):
```json
{
  "item_code": "ITEM-001",
  "warehouse": "Stores - WH",
  "actual_qty": 50.0,
  "reserved_qty": 10.0,
  "projected_qty": 40.0,
  "last_updated": "2026-02-07T10:25:00Z"
}
```

**HTTP Status Codes**:
- `200`: Success
- `404`: Item or warehouse not found
- `503`: ERPNext unavailable

---

### 6. List Warehouses for Item

**Endpoint**: `GET /api/items/{item_code}/warehouses`

**Purpose**: Get all warehouses stocking an item

**Parameters**:
- `item_code` (path): Item code

**Response** (200 OK):
```json
{
  "item_code": "ITEM-001",
  "warehouses": [
    {
      "warehouse": "Stores - WH",
      "projected_qty": 40.0,
      "warehouse_type": "SELLABLE"
    },
    {
      "warehouse": "Raw Materials - WH",
      "projected_qty": 25.0,
      "warehouse_type": "NEEDS_PROCESSING"
    }
  ]
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Error message here",
  "error_code": "INVALID_REQUEST | RESOURCE_NOT_FOUND | PERMISSION_DENIED | SERVICE_UNAVAILABLE",
  "request_id": "uuid-for-tracking",
  "timestamp": "2026-02-07T10:30:00Z"
}
```

### Common Errors

| Status | Error Code | Meaning | Solution |
|--------|-----------|---------|----------|
| 400 | `INVALID_REQUEST` | Missing required field | Check request body |
| 422 | `VALIDATION_ERROR` | Qty <= 0 or invalid date | Use positive qty, ISO date |
| 404 | `RESOURCE_NOT_FOUND` | Item/warehouse doesn't exist | Verify item code and warehouse |
| 403 | `PERMISSION_DENIED` | No access to ERPNext data | Check ERPNext API permissions |
| 500 | `INTERNAL_ERROR` | Unexpected error | Check logs, contact support |
| 503 | `SERVICE_UNAVAILABLE` | ERPNext down | Wait for ERPNext to recover |

### Retry Strategy

```python
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(
    wait=wait_exponential(multiplier=1, min=100, max=10000),
    stop=stop_after_attempt(3)
)
def call_otp_promise(request_body):
    response = requests.post(
        "http://localhost:8001/otp/promise",
        json=request_body,
        timeout=10
    )
    response.raise_for_status()
    return response.json()

# Retries automatically on 5xx errors
```

---

## Request Examples

### Example 1: Simple Promise (Stock Only)

**Scenario**: Customer needs 20 units of ITEM-001, available in Stores-WH

```bash
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 20.0,
        "warehouse": "Stores - WH"
      }
    ]
  }'
```

**Python**:
```python
import requests

response = requests.post(
    "http://localhost:8001/otp/promise",
    json={
        "customer": "CUST-001",
        "items": [{
            "item_code": "ITEM-001",
            "qty": 20.0,
            "warehouse": "Stores - WH"
        }]
    }
)

promise = response.json()
print(f"Promise Date: {promise['promise_date']}")
print(f"Confidence: {promise['confidence']}")
```

---

### Example 2: Complex Order with Desired Date

**Scenario**: Customer wants 100 units by Feb 20, willing to accept delay

```bash
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-002",
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 50.0,
        "warehouse": "Stores - WH"
      },
      {
        "item_code": "ITEM-002",
        "qty": 50.0,
        "warehouse": "Stores - WH"
      }
    ],
    "desired_date": "2026-02-20",
    "rules": {
      "no_weekends": true,
      "lead_time_buffer_days": 2,
      "desired_date_mode": "LATEST_ACCEPTABLE"
    }
  }'
```

**JavaScript**:
```javascript
async function calculatePromise() {
  const response = await fetch('/otp/promise', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer: 'CUST-002',
      items: [
        { item_code: 'ITEM-001', qty: 50, warehouse: 'Stores - WH' },
        { item_code: 'ITEM-002', qty: 50, warehouse: 'Stores - WH' }
      ],
      desired_date: '2026-02-20',
      rules: {
        no_weekends: true,
        lead_time_buffer_days: 2,
        desired_date_mode: 'LATEST_ACCEPTABLE'
      }
    })
  });
  
  const promise = await response.json();
  document.getElementById('promise-date').textContent = promise.promise_date;
  document.getElementById('confidence').textContent = promise.confidence;
}
```

---

### Example 3: NO_EARLY_DELIVERY Mode

**Scenario**: Customer can't accept delivery before Mar 8 (warehouse receiving schedule)

```bash
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-003",
    "items": [{
      "item_code": "ITEM-003",
      "qty": 30.0,
      "warehouse": "Stores - WH"
    }],
    "desired_date": "2026-03-08",
    "rules": {
      "desired_date_mode": "NO_EARLY_DELIVERY"
    }
  }'
```

---

### Example 4: Strict Failure Mode

**Scenario**: Customer has hard deadline: must deliver by Feb 15 or cancel order

```bash
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-004",
    "items": [{
      "item_code": "ITEM-004",
      "qty": 100.0,
      "warehouse": "Stores - WH"
    }],
    "desired_date": "2026-02-15",
    "rules": {
      "desired_date_mode": "STRICT_FAIL"
    }
  }'
```

If promise date > Feb 15, response:
```json
{
  "status": "CANNOT_FULFILL",
  "promise_date": null,
  "can_fulfill": false,
  "blockers": ["Cannot meet hard deadline of 2026-02-15"]
}
```

---

## Response Examples

### Response 1: Perfect Promise (HIGH Confidence)

```json
{
  "status": "OK",
  "promise_date": "2026-02-09",
  "promise_date_raw": "2026-02-09",
  "confidence": "HIGH",
  "can_fulfill": true,
  "on_time": true,
  "plan": [{
    "item_code": "ITEM-001",
    "requested_qty": 20.0,
    "fulfilled_qty": 20.0,
    "shortage": 0.0,
    "fulfillment_sources": [{
      "source_type": "Stock",
      "warehouse": "Stores - WH",
      "qty": 20.0,
      "available_date": "2026-02-07",
      "confidence": "HIGH"
    }]
  }],
  "reasons": [
    "20.0 units available from stock (Stores - WH)",
    "Applied 1 day lead time buffer",
    "Excluded weekends from promise date"
  ],
  "blockers": [],
  "options": []
}
```

### Response 2: Mixed Promise (MEDIUM Confidence)

```json
{
  "status": "OK",
  "promise_date": "2026-02-18",
  "confidence": "MEDIUM",
  "can_fulfill": true,
  "on_time": true,
  "plan": [{
    "item_code": "ITEM-002",
    "requested_qty": 100.0,
    "fulfilled_qty": 100.0,
    "shortage": 0.0,
    "fulfillment_sources": [
      {
        "source_type": "Stock",
        "warehouse": "Stores - WH",
        "qty": 30.0,
        "available_date": "2026-02-07",
        "confidence": "HIGH"
      },
      {
        "source_type": "PurchaseOrder",
        "po_id": "PO-001",
        "warehouse": "Goods In Transit - SD",
        "qty": 40.0,
        "available_date": "2026-02-12",
        "confidence": "MEDIUM"
      },
      {
        "source_type": "PurchaseOrder",
        "po_id": "PO-002",
        "warehouse": "Goods In Transit - SD",
        "qty": 30.0,
        "available_date": "2026-02-18",
        "confidence": "LOW"
      }
    ]
  }],
  "reasons": [
    "30.0u from stock (Stores - WH)",
    "40.0u from PO-001 (arriving 2026-02-12)",
    "30.0u from PO-002 (arriving 2026-02-18)",
    "Fulfillment complete on 2026-02-18"
  ],
  "blockers": [
    "PO-002 has 11-day lead time (high uncertainty)"
  ],
  "options": [{
    "option_type": "SPLIT_SHIPMENT",
    "description": "Ship 70 units by Feb 12, remaining 30 units by Feb 18",
    "risk_level": "LOW"
  }]
}
```

### Response 3: Cannot Fulfill (Shortage)

```json
{
  "status": "CANNOT_FULFILL",
  "promise_date": null,
  "confidence": "LOW",
  "can_fulfill": false,
  "plan": [{
    "item_code": "ITEM-005",
    "requested_qty": 200.0,
    "fulfilled_qty": 80.0,
    "shortage": 120.0,
    "fulfillment_sources": [
      {"source_type": "Stock", "qty": 30.0},
      {"source_type": "PurchaseOrder", "qty": 50.0}
    ]
  }],
  "reasons": [
    "Item: 200u requested, only 80u available from stock + POs"
  ],
  "blockers": [
    "Shortage: 120 units cannot be fulfilled",
    "No additional POs scheduled"
  ],
  "options": [{
    "option_type": "RUSH_PROCUREMENT",
    "description": "Create expedited PO for 120 missing units",
    "risk_level": "MEDIUM"
  }, {
    "option_type": "PARTIAL_FULFILLMENT",
    "description": "Accept partial shipment of 80 units",
    "risk_level": "HIGH"
  }]
}
```

---

## Real-World Scenarios

### Scenario 1: Rush Order (Customer Calls)

**Context**: Customer calls wanting to order 50 units ITEM-X by tomorrow

```bash
# 1. Query promise immediately
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-RUSH",
    "items": [{"item_code": "ITEM-X", "qty": 50, "warehouse": "Stores - WH"}],
    "desired_date": "2026-02-08",
    "rules": {"desired_date_mode": "LATEST_ACCEPTABLE"}
  }'

# Response: promise_date = "2026-02-09" (can meet Feb 8 deadline)

# 2. If OK, apply to SO
curl -X POST "http://localhost:8001/otp/apply" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_order_name": "SO-RUSH-001",
    "promise_date": "2026-02-09",
    "confidence": "HIGH"
  }'
```

### Scenario 2: Multi-Item Complex Order

```bash
# Customer order:
# - 50 units ITEM-A (urgent)
# - 100 units ITEM-B (can wait)
# - 25 units ITEM-C (needed for kit assembly by Feb 20)

curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-ASSEMBLY",
    "items": [
      {"item_code": "ITEM-A", "qty": 50, "warehouse": "Stores - WH"},
      {"item_code": "ITEM-B", "qty": 100, "warehouse": "Stores - WH"},
      {"item_code": "ITEM-C", "qty": 25, "warehouse": "Stores - WH"}
    ],
    "desired_date": "2026-02-20",
    "rules": {
      "desired_date_mode": "LATEST_ACCEPTABLE",
      "lead_time_buffer_days": 1
    }
  }'

# Returns: Single promise date when ALL items available
# Response could be: "2026-02-18" (bottleneck is ITEM-C)
```

### Scenario 3: Handle Shortage Gracefully

```bash
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-LOW-STOCK",
    "items": [{"item_code": "ITEM-RARE", "qty": 1000, "warehouse": "Stores - WH"}]
  }'

# Response: Cannot fulfill
# Options in response:
#   1. RUSH_PROCUREMENT - expedite PO
#   2. PARTIAL_FULFILLMENT - take available (80 units)
#   3. MULTI_SHIPMENT - split across multiple dates

# Based on response, system can:
# - Alert procurement team to rush PO
# - Offer customer split shipment option
# - Suggest alternate item if available
```

---

## Rate Limiting

OTP API doesn't enforce rate limiting by default. For production:

```python
# You can add rate limiting middleware:
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/otp/promise")
@limiter.limit("100/minute")  # 100 requests per minute per IP
async def calculate_promise(request: PromiseRequest):
    ...
```

### Recommended Limits
- `/otp/promise`: 100 req/min per IP (calculation is CPU-intensive)
- `/api/items/stock/*`: 1000 req/min per IP (lightweight)
- `/health`: 10000 req/min per IP (monitoring)

---

## Pagination & Filtering

Stock endpoints support pagination:

```bash
# Get warehouses with pagination
curl "http://localhost:8001/api/items/ITEM-001/warehouses?page=1&limit=20"
```

---

## Versioning

Current version: **v0.1.0**

No breaking changes planned in near future. Future versions will be at:
- `/v2/otp/promise` (if breaking changes needed)

---

## Summary

The OTP API is:
- ✅ **RESTful**: Standard HTTP methods and status codes
- ✅ **Well-Documented**: Swagger UI at /docs
- ✅ **Robust**: Comprehensive error handling
- ✅ **Scalable**: Efficient database queries
- ✅ **Developer-Friendly**: Clear request/response examples

For more info, visit the interactive Swagger documentation at `http://localhost:8001/docs` after starting the service.
