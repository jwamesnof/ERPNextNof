# API Contract Documentation

**ERPNext Order Promise Engine (OTP) Backend**  
Version: 0.1.0  
Last Updated: January 28, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Base URL & Authentication](#base-url--authentication)
3. [Common Response Patterns](#common-response-patterns)
4. [Endpoints](#endpoints)
   - [POST /otp/promise](#post-otppromise)
   - [POST /otp/apply](#post-otpapply)
   - [POST /otp/procurement-suggest](#post-otpprocurement-suggest)
   - [GET /otp/health](#get-otphealth)
   - [GET /health](#get-health)
5. [Status Codes](#status-codes)
6. [Error Responses](#error-responses)
7. [Business Logic](#business-logic)
8. [Testing with cURL](#testing-with-curl)
9. [Debug Logging](#debug-logging)
10. [Performance](#performance)

---

## Overview

The OTP API provides RESTful endpoints for:
- Calculating order promise dates based on stock and incoming supply
- Applying promise dates to ERPNext Sales Orders
- Creating procurement suggestions (Material Requests)
- Health checks and service status

All endpoints accept and return JSON. The API follows REST conventions with standard HTTP methods and status codes.

---

## Base URL & Authentication

### Base URL

```
http://localhost:8001
```

**Production:** Update to your deployed URL (e.g., `https://api.yourcompany.com`)

### Authentication

Currently, the API does **not require authentication**. This is suitable for:
- Internal microservices
- Development environments
- Trusted network deployments

**For production**, consider adding:
- API key authentication
- JWT tokens
- OAuth2
- IP whitelisting

**Implementation example:**
```python
# In src/main.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

---

## Common Response Patterns

### Success Response Structure

All successful responses follow this pattern:

```json
{
  "status": "OK" | "CANNOT_FULFILL" | "CANNOT_PROMISE_RELIABLY",
  "...": "endpoint-specific fields"
}
```

### Timestamps & Dates

- **Date fields** use ISO 8601 format: `"2026-02-05"` (YYYY-MM-DD)
- **Datetime fields** (if any) use ISO 8601: `"2026-01-28T13:24:00Z"`
- **Timezone** is configured via `TIMEZONE` env var (default: UTC)

### Null Values

- Optional fields may be `null` when not applicable
- Required fields are always present (never `null`)

---

## Endpoints

### POST /otp/promise

**Calculate order promise date** based on customer, items, and business rules.

#### Request Schema

```json
{
  "customer": "string (required)",
  "items": [
    {
      "item_code": "string (required)",
      "qty": number (required, >0),
      "warehouse": "string (optional)"
    }
  ],
  "desired_date": "YYYY-MM-DD (optional)",
  "rules": {
    "no_weekends": boolean (default: true),
    "cutoff_time": "HH:MM (default: '14:00')",
    "timezone": "string (default: 'UTC')",
    "lead_time_buffer_days": number (default: 1, >=0),
    "processing_lead_time_days": number (default: 1, >=0),
    "desired_date_mode": "LATEST_ACCEPTABLE | STRICT_FAIL | NO_EARLY_DELIVERY (default: LATEST_ACCEPTABLE)"
  }
}
```

#### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer` | string | Yes | Customer ID or name |
| `items` | array | Yes | List of items to promise (min 1) |
| `items[].item_code` | string | Yes | ERPNext item code |
| `items[].qty` | number | Yes | Quantity required (>0) |
| `items[].warehouse` | string | No | Specific warehouse (defaults to DEFAULT_WAREHOUSE) |
| `desired_date` | date | No | Customer's requested delivery date |
| `rules` | object | No | Business rules (uses defaults if omitted) |
| `rules.no_weekends` | boolean | No | Skip Saturday/Sunday (default: true) |
| `rules.cutoff_time` | string | No | Daily cutoff (default: "14:00") |
| `rules.timezone` | string | No | Timezone (default: "UTC") |
| `rules.lead_time_buffer_days` | number | No | Extra buffer days (default: 1) |
| `rules.processing_lead_time_days` | number | No | Warehouse processing days (default: 1) |
| `rules.desired_date_mode` | enum | No | How to interpret desired_date |

**Desired Date Modes:**
- `LATEST_ACCEPTABLE`: Desired date is the latest acceptable delivery (default)
- `STRICT_FAIL`: Hard constraint - returns CANNOT_FULFILL if promise > desired
- `NO_EARLY_DELIVERY`: Customer doesn't want delivery earlier than desired

#### Response Schema

```json
{
  "status": "OK | CANNOT_FULFILL | CANNOT_PROMISE_RELIABLY",
  "promise_date": "YYYY-MM-DD (null if CANNOT_FULFILL)",
  "promise_date_raw": "YYYY-MM-DD (before desired_date adjustments)",
  "desired_date": "YYYY-MM-DD (echoed from request)",
  "desired_date_mode": "string (mode used)",
  "on_time": boolean,
  "adjusted_due_to_no_early_delivery": boolean,
  "can_fulfill": boolean,
  "confidence": "HIGH | MEDIUM | LOW",
  "plan": [
    {
      "item_code": "string",
      "qty_required": number,
      "fulfillment": [
        {
          "source": "stock | purchase_order | production",
          "qty": number,
          "available_date": "YYYY-MM-DD",
          "ship_ready_date": "YYYY-MM-DD",
          "warehouse": "string (optional)",
          "po_id": "string (optional)",
          "expected_date": "YYYY-MM-DD (optional)"
        }
      ],
      "shortage": number
    }
  ],
  "reasons": ["string"],
  "blockers": ["string"],
  "options": [
    {
      "type": "alternate_warehouse | expedite_po | ...",
      "description": "string",
      "impact": "string",
      "po_id": "string (optional)"
    }
  ]
}
```

#### Response Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `status` | enum | Overall status (OK, CANNOT_FULFILL, CANNOT_PROMISE_RELIABLY) |
| `promise_date` | date | Final computed delivery date (null if cannot fulfill) |
| `promise_date_raw` | date | Promise before desired_date adjustments |
| `desired_date` | date | Customer requested date (echoed) |
| `desired_date_mode` | string | Mode used for interpretation |
| `on_time` | boolean | True if promise_date <= desired_date |
| `adjusted_due_to_no_early_delivery` | boolean | True if delayed to match desired_date |
| `can_fulfill` | boolean | True if order is fully allocatable |
| `confidence` | enum | HIGH (100% stock), MEDIUM (stock+near POs), LOW (late POs/shortages) |
| `plan` | array | Fulfillment plan per item |
| `plan[].fulfillment` | array | Sources of supply for this item |
| `plan[].shortage` | number | Unfulfilled quantity |
| `reasons` | array | Human-readable explanation |
| `blockers` | array | Issues preventing optimal promise |
| `options` | array | Alternative suggestions |

#### Status Values

- **OK**: Promise calculated successfully, order can be fulfilled
- **CANNOT_FULFILL**: Insufficient stock/supply to fulfill order
- **CANNOT_PROMISE_RELIABLY**: Missing data (e.g., PO access denied)

#### Confidence Levels

- **HIGH**: 100% from current stock
- **MEDIUM**: Mix of stock + incoming POs (arriving <7 days)
- **LOW**: Relies on late POs (>7 days) or has shortages

#### Example Request

```json
{
  "customer": "Grant Plastics Ltd.",
  "items": [
    {
      "item_code": "SKU005",
      "qty": 50,
      "warehouse": "Stores - SD"
    }
  ],
  "desired_date": "2026-02-10",
  "rules": {
    "no_weekends": true,
    "cutoff_time": "14:00",
    "lead_time_buffer_days": 1,
    "processing_lead_time_days": 1
  }
}
```

#### Example Response (Success)

```json
{
  "status": "OK",
  "promise_date": "2026-02-05",
  "promise_date_raw": "2026-02-05",
  "desired_date": "2026-02-10",
  "desired_date_mode": "LATEST_ACCEPTABLE",
  "on_time": true,
  "adjusted_due_to_no_early_delivery": false,
  "can_fulfill": true,
  "confidence": "MEDIUM",
  "plan": [
    {
      "item_code": "SKU005",
      "qty_required": 50,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 30,
          "available_date": "2026-01-28",
          "ship_ready_date": "2026-01-29",
          "warehouse": "Stores - SD"
        },
        {
          "source": "purchase_order",
          "qty": 20,
          "available_date": "2026-02-03",
          "ship_ready_date": "2026-02-04",
          "warehouse": "Stores - SD",
          "po_id": "PO-00123",
          "expected_date": "2026-02-03"
        }
      ],
      "shortage": 0
    }
  ],
  "reasons": [
    "Item SKU005: 30 units from stock (available 2026-01-28)",
    "Item SKU005: 20 units from PO-00123 (arriving 2026-02-03)",
    "Added 1 day(s) processing lead time",
    "Added 1 day(s) lead time buffer",
    "Final promise: 2026-02-05 (on time - desired: 2026-02-10)"
  ],
  "blockers": [],
  "options": []
}
```

#### Example Response (Cannot Fulfill)

```json
{
  "status": "CANNOT_FULFILL",
  "promise_date": null,
  "promise_date_raw": null,
  "desired_date": "2026-02-10",
  "desired_date_mode": "LATEST_ACCEPTABLE",
  "on_time": false,
  "adjusted_due_to_no_early_delivery": false,
  "can_fulfill": false,
  "confidence": "LOW",
  "plan": [
    {
      "item_code": "SKU999",
      "qty_required": 100,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 10,
          "available_date": "2026-01-28",
          "ship_ready_date": "2026-01-29",
          "warehouse": "Stores - SD"
        }
      ],
      "shortage": 90
    }
  ],
  "reasons": [
    "Item SKU999: 10 units from stock",
    "Item SKU999: 90 units SHORTAGE (no incoming supply)"
  ],
  "blockers": [
    "Insufficient supply for SKU999 (need 100, have 10)"
  ],
  "options": [
    {
      "type": "create_purchase_order",
      "description": "Create emergency PO for 90 units of SKU999",
      "impact": "Could fulfill if expedited (lead time depends on supplier)"
    }
  ]
}
```

---

### POST /otp/apply

**Apply promise date** to an existing Sales Order in ERPNext.

#### Request Schema

```json
{
  "sales_order_id": "string (required)",
  "promise_date": "YYYY-MM-DD (required)",
  "confidence": "HIGH | MEDIUM | LOW (required)",
  "action": "add_comment | set_custom_field | both (default: 'both')",
  "comment_text": "string (optional)"
}
```

#### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sales_order_id` | string | Yes | Sales Order ID in ERPNext (e.g., "SO-00456") |
| `promise_date` | date | Yes | Calculated promise date to apply |
| `confidence` | enum | Yes | Confidence level (HIGH, MEDIUM, LOW) |
| `action` | enum | No | How to apply: "add_comment", "set_custom_field", or "both" |
| `comment_text` | string | No | Custom comment text (generated if omitted) |

#### Response Schema

```json
{
  "status": "success | error",
  "sales_order_id": "string",
  "actions_taken": ["string"],
  "erpnext_response": {
    "...": "raw ERPNext API response"
  },
  "error": "string (null if success)"
}
```

#### Example Request

```json
{
  "sales_order_id": "SO-00456",
  "promise_date": "2026-02-05",
  "confidence": "MEDIUM",
  "action": "both",
  "comment_text": "Promise date calculated: 2026-02-05 (MEDIUM confidence)"
}
```

#### Example Response (Success)

```json
{
  "status": "success",
  "sales_order_id": "SO-00456",
  "actions_taken": [
    "Added comment to Sales Order SO-00456",
    "Updated custom field 'promise_date' to 2026-02-05"
  ],
  "erpnext_response": {
    "name": "SO-00456",
    "custom_promise_date": "2026-02-05"
  },
  "error": null
}
```

#### Example Response (Error - Mock Mode)

```json
{
  "status": "error",
  "sales_order_id": "SO-00456",
  "actions_taken": [],
  "erpnext_response": null,
  "error": "Write operations not supported in mock mode"
}
```

**Note:** This endpoint requires ERPNext connection. Mock mode will return an error.

---

### POST /otp/procurement-suggest

**Create procurement suggestion** in ERPNext (Material Request).

#### Request Schema

```json
{
  "items": [
    {
      "item_code": "string (required)",
      "qty_needed": number (required, >0),
      "required_by": "YYYY-MM-DD (required)",
      "reason": "string (required)"
    }
  ],
  "suggestion_type": "material_request | draft_po | task (default: 'material_request')",
  "priority": "HIGH | MEDIUM | LOW (default: 'MEDIUM')"
}
```

#### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `items` | array | Yes | Items needing procurement (min 1) |
| `items[].item_code` | string | Yes | Item code |
| `items[].qty_needed` | number | Yes | Quantity to procure (>0) |
| `items[].required_by` | date | Yes | Required delivery date |
| `items[].reason` | string | Yes | Justification (e.g., "Sales Order SO-00456") |
| `suggestion_type` | enum | No | Type of suggestion (currently only "material_request" supported) |
| `priority` | enum | No | Priority level |

#### Response Schema

```json
{
  "status": "success | error",
  "suggestion_id": "string",
  "type": "Material Request | Purchase Order | Task",
  "items_count": number,
  "erpnext_url": "string",
  "error": "string (null if success)"
}
```

#### Example Request

```json
{
  "items": [
    {
      "item_code": "SKU005",
      "qty_needed": 90,
      "required_by": "2026-02-15",
      "reason": "Shortage for Sales Order SO-00456"
    }
  ],
  "suggestion_type": "material_request",
  "priority": "HIGH"
}
```

#### Example Response (Success)

```json
{
  "status": "success",
  "suggestion_id": "MR-00789",
  "type": "Material Request",
  "items_count": 1,
  "erpnext_url": "http://localhost:8080/app/material-request/MR-00789",
  "error": null
}
```

**Note:** This endpoint requires ERPNext connection. Mock mode will return an error.

---

### GET /otp/health

**Health check** for OTP service with ERPNext connectivity status.

#### Request

No parameters required.

#### Response Schema

```json
{
  "status": "healthy | degraded",
  "version": "string",
  "erpnext_connected": boolean,
  "message": "string"
}
```

#### Example Response (Mock Mode)

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": false,
  "message": "OTP Service is operational (using mock supply data)"
}
```

#### Example Response (ERPNext Connected)

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": true,
  "message": "All systems operational"
}
```

---

### GET /health

**Root health check** (alternative endpoint, same as `/otp/health`).

Same schema as `/otp/health`.

---

## Status Codes

### Success Codes

| Code | Description | When Used |
|------|-------------|-----------|
| `200 OK` | Request successful | All GET requests, successful calculations |
| `201 Created` | Resource created | (Future) When creating new resources |

### Client Error Codes

| Code | Description | When Used |
|------|-------------|-----------|
| `400 Bad Request` | Invalid request data | Missing required fields, invalid JSON, validation errors |
| `403 Forbidden` | Not authorized | (Future) Authentication failures |
| `404 Not Found` | Resource not found | Invalid endpoint |
| `422 Unprocessable Entity` | Validation error | Pydantic validation failures |

### Server Error Codes

| Code | Description | When Used |
|------|-------------|-----------|
| `500 Internal Server Error` | Unexpected error | Unhandled exceptions |
| `503 Service Unavailable` | Dependency failure | ERPNext connection errors |

---

## Error Responses

### Standard Error Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Example Errors

**400 Bad Request (Missing field):**
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "customer"],
      "msg": "Field required",
      "input": {...}
    }
  ]
}
```

**400 Bad Request (Validation):**
```json
{
  "detail": [
    {
      "type": "greater_than",
      "loc": ["body", "items", 0, "qty"],
      "msg": "Input should be greater than 0",
      "input": -5
    }
  ]
}
```

**503 Service Unavailable (ERPNext down):**
```json
{
  "detail": "ERPNext service error: Connection refused"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal error: Unexpected calculation failure"
}
```

---

## Business Logic

### Promise Calculation Algorithm

The backend calculates promises using this logic:

#### 1. Gather Fulfillment Sources

For each item:
1. **Check current stock** (available quantity)
2. **Query incoming Purchase Orders** (sorted by expected date)
3. **Build fulfillment plan** (FIFO: stock first, then POs in order)

#### 2. Determine Earliest Available Date

- Take the **latest date** among all items' fulfillment sources
- This is the date when all items are available

#### 3. Add Processing Lead Time

```
ship_ready_date = available_date + processing_lead_time_days
```

**Processing lead time** represents internal warehouse handling:
- Picking
- Packing
- Quality assurance
- Staging for shipment
- Carrier booking

#### 4. Apply Business Rules

```
promise_date = ship_ready_date + lead_time_buffer_days
```

Then:
- **Check cutoff time**: If current time > cutoff, add 1 day
- **Skip weekends**: If result is Saturday/Sunday, move to next Monday

#### 5. Apply Desired Date Logic

Depending on `desired_date_mode`:

- **LATEST_ACCEPTABLE**: No adjustment (promise can be earlier)
- **STRICT_FAIL**: If promise > desired, set status to CANNOT_FULFILL
- **NO_EARLY_DELIVERY**: If promise < desired, set promise = desired

#### 6. Calculate Confidence

```
if all_from_stock:
    confidence = HIGH
elif all_from_stock_or_near_pos (< 7 days):
    confidence = MEDIUM
else:
    confidence = LOW
```

#### 7. Generate Explanations

- **Reasons**: How each item is fulfilled
- **Blockers**: Shortages, permission issues
- **Options**: Alternate warehouses, expedite suggestions

### Example Calculation

**Input:**
- Item: SKU005, Qty: 50
- Stock: 30 available today (2026-01-28)
- PO: 20 arriving 2026-02-03
- Rules: processing=1 day, buffer=1 day, no_weekends=true

**Steps:**
1. Fulfillment: 30 from stock (2026-01-28), 20 from PO (2026-02-03)
2. Earliest available: 2026-02-03 (latest source)
3. Ship ready: 2026-02-03 + 1 = 2026-02-04
4. After buffer: 2026-02-04 + 1 = 2026-02-05
5. Check weekend: 2026-02-05 is Wednesday ✓
6. Final promise: **2026-02-05**
7. Confidence: **MEDIUM** (mix of stock + near PO)

---

## Testing with cURL

### Test Health Check

```bash
curl http://localhost:8001/health
```

**Expected:**
```json
{"status":"healthy","version":"0.1.0","erpnext_connected":false,"message":"..."}
```

### Test Promise Calculation

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Test Customer",
    "items": [
      {
        "item_code": "SKU005",
        "qty": 10,
        "warehouse": "Stores - SD"
      }
    ],
    "desired_date": "2026-02-10"
  }'
```

**Expected:**
```json
{
  "status": "OK",
  "promise_date": "2026-XX-XX",
  "confidence": "HIGH",
  "can_fulfill": true,
  "plan": [...],
  "reasons": [...]
}
```

### Test with Multiple Items

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Big Corp",
    "items": [
      {"item_code": "SKU005", "qty": 20},
      {"item_code": "SKU008", "qty": 15}
    ],
    "rules": {
      "no_weekends": true,
      "lead_time_buffer_days": 2
    }
  }'
```

### Test with NO_EARLY_DELIVERY Mode

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Specific Date Corp",
    "items": [{"item_code": "SKU005", "qty": 5}],
    "desired_date": "2026-03-01",
    "rules": {
      "desired_date_mode": "NO_EARLY_DELIVERY"
    }
  }'
```

### Test Apply Promise (Requires ERPNext)

```bash
curl -X POST http://localhost:8001/otp/apply \
  -H "Content-Type: application/json" \
  -d '{
    "sales_order_id": "SO-00456",
    "promise_date": "2026-02-05",
    "confidence": "MEDIUM",
    "action": "add_comment"
  }'
```

### Test Procurement Suggestion (Requires ERPNext)

```bash
curl -X POST http://localhost:8001/otp/procurement-suggest \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "item_code": "SKU005",
        "qty_needed": 50,
        "required_by": "2026-02-20",
        "reason": "Sales Order SO-00456"
      }
    ],
    "priority": "HIGH"
  }'
```

### Save cURL Response to File

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d @request.json \
  -o response.json
```

### View Response with Pretty Printing

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{"customer":"Test","items":[{"item_code":"SKU005","qty":10}]}' \
  | python -m json.tool
```

---

## Debug Logging

### Enable Debug Logging

**Method 1: Environment Variable**

```ini
# In .env
OTP_SERVICE_ENV=development
```

**Method 2: Code Change**

```python
# In src/main.py
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

### View Logs

**Console (when running locally):**
```bash
uvicorn src.main:app --reload
# Logs appear in terminal
```

**File (if configured):**
```bash
tail -f server.log
```

**Docker logs:**
```bash
docker-compose logs -f otp-service
```

### Log Levels

| Level | When to Use |
|-------|-------------|
| `DEBUG` | Detailed execution flow (development only) |
| `INFO` | Normal operations (requests, responses) |
| `WARNING` | Recoverable issues (missing POs, degraded performance) |
| `ERROR` | Errors that need attention (ERPNext failures) |
| `CRITICAL` | System failures (startup errors) |

### Example Log Output

```
2026-01-28 13:24:15,123 - src.routes.otp - INFO - POST /otp/promise from 127.0.0.1
2026-01-28 13:24:15,145 - src.services.stock_service - DEBUG - Querying stock for SKU005 in Stores - SD
2026-01-28 13:24:15,167 - src.services.stock_service - DEBUG - Found 30 units in stock
2026-01-28 13:24:15,189 - src.services.stock_service - DEBUG - Querying POs for SKU005
2026-01-28 13:24:15,212 - src.services.stock_service - DEBUG - Found 1 PO: PO-00123 (20 units, 2026-02-03)
2026-01-28 13:24:15,234 - src.services.promise_service - DEBUG - Building fulfillment plan
2026-01-28 13:24:15,256 - src.services.promise_service - INFO - Promise calculated: 2026-02-05 (MEDIUM confidence)
2026-01-28 13:24:15,278 - src.routes.otp - INFO - Response: 200 OK
```

### Debug Specific Services

```python
# In src/main.py
logging.getLogger("src.services.promise_service").setLevel(logging.DEBUG)
logging.getLogger("src.clients.erpnext_client").setLevel(logging.DEBUG)
```

---

## Performance

### Response Time Benchmarks

**Mock Mode (CSV data):**

| Endpoint | Avg Response Time | Notes |
|----------|-------------------|-------|
| `/health` | 5-10 ms | No external calls |
| `/otp/promise` (1 item) | 20-50 ms | Simple calculation |
| `/otp/promise` (5 items) | 50-100 ms | Multiple fulfillments |

**ERPNext Mode (live connection):**

| Endpoint | Avg Response Time | Notes |
|----------|-------------------|-------|
| `/health` | 50-100 ms | 1 ERPNext API call |
| `/otp/promise` (1 item) | 200-500 ms | Stock + PO queries |
| `/otp/promise` (5 items) | 500-1000 ms | Multiple queries |
| `/otp/apply` | 500-1000 ms | Write to ERPNext |
| `/otp/procurement-suggest` | 500-1500 ms | Create Material Request |

### Performance Optimization Tips

1. **Use mock mode** for development (10-20x faster)
2. **Cache stock data** on ERPNext side (reduce query time)
3. **Batch requests** when calculating promises for multiple orders
4. **Index ERPNext fields** (item_code, warehouse, expected_date)
5. **Monitor slow queries** with debug logging

### Load Testing

Use [Apache Bench](https://httpd.apache.org/docs/2.4/programs/ab.html):

```bash
# 100 requests, 10 concurrent
ab -n 100 -c 10 -T application/json -p request.json http://localhost:8001/otp/promise
```

Use [hey](https://github.com/rakyll/hey):

```bash
hey -n 1000 -c 50 -m POST \
  -H "Content-Type: application/json" \
  -d '{"customer":"Test","items":[{"item_code":"SKU005","qty":10}]}' \
  http://localhost:8001/otp/promise
```

### Expected Throughput

**Mock Mode:**
- 200-500 requests/second (single worker)
- 1000+ requests/second (multiple workers)

**ERPNext Mode:**
- 10-50 requests/second (depends on ERPNext performance)

### Scaling Recommendations

- **Horizontal scaling**: Deploy multiple instances behind load balancer
- **Caching**: Add Redis for frequently requested items
- **Async processing**: Queue promise calculations for large batches
- **Database read replicas**: Use ERPNext read replicas for queries

---

## Quick Reference

### All Endpoints Summary

| Endpoint | Method | Auth | Mock Mode | Purpose |
|----------|--------|------|-----------|---------|
| `/health` | GET | No | ✅ | Service health check |
| `/otp/health` | GET | No | ✅ | Service health check |
| `/otp/promise` | POST | No | ✅ | Calculate promise date |
| `/otp/apply` | POST | No | ❌ | Apply promise to Sales Order |
| `/otp/procurement-suggest` | POST | No | ❌ | Create Material Request |

### Status Code Quick Reference

- `200`: Success
- `400`: Bad request (check JSON)
- `422`: Validation error (check fields)
- `500`: Server error (check logs)
- `503`: ERPNext unavailable

### Need Help?

- **Frontend integration**: See [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)
- **General setup**: See [README.md](README.md)
- **Demo data**: See [DEMO_DATA.md](DEMO_DATA.md)
- **API playground**: Visit `http://localhost:8001/docs`

---

**Last Updated:** January 28, 2026  
**API Version:** 0.1.0  
**Questions?** Check troubleshooting in [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)
