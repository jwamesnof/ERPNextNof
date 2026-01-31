# Desired Date Handling - Feature Documentation

## Overview

The Order Promise Engine (OTP) now supports customer-requested delivery dates (`desired_date`) with three configurable interpretation modes. This feature enables deterministic, testable promise calculations that automatically reflect changes in stock, reservations, and incoming supply.

## Key Features

✅ **Three Interpretation Modes**: LATEST_ACCEPTABLE, STRICT_FAIL, NO_EARLY_DELIVERY  
✅ **On-Time Indicator**: Boolean flag showing if promise meets desired date  
✅ **Dynamic Recalculation**: Promise automatically adjusts when stock/supply changes  
✅ **Enhanced Suggestions**: Split shipment, expedite PO, alternate warehouse options when late  
✅ **Fully Tested**: 10 unit tests covering all modes and edge cases  
✅ **Backward Compatible**: Existing code works unchanged (desired_date is optional)

---

## Interpretation Modes

### Mode A: LATEST_ACCEPTABLE (Default)

**Use Case**: Customer wants delivery by a certain date (latest acceptable).

**Behavior**:
- If `promise_date <= desired_date`: ✅ `on_time = True`
- If `promise_date > desired_date`: ❌ `on_time = False` + suggestions returned

**Response**:
```json
{
  "promise_date": "2026-02-15",
  "promise_date_raw": "2026-02-15",
  "desired_date": "2026-02-10",
  "desired_date_mode": "LATEST_ACCEPTABLE",
  "on_time": false,
  "reasons": [
    "Desired delivery: 2026-02-10. Late by 5 days."
  ],
  "options": [
    {
      "type": "expedite_po",
      "description": "Expedite PO-001 for SKU001",
      "impact": "Could reduce promise date by up to 7 days"
    }
  ]
}
```

---

### Mode B: STRICT_FAIL

**Use Case**: Hard constraint - promise MUST meet desired date or fail.

**Behavior**:
- If `promise_date <= desired_date`: ✅ Succeeds, `on_time = True`
- If `promise_date > desired_date`: ❌ **Raises ValueError** with reasons and options

**Example Error**:
```python
ValueError: Cannot meet desired delivery date 2026-02-10. 
Earliest possible promise: 2026-02-15 (5 days late). 
Check response 'options' for alternative scenarios.
```

**Use in API**: Return HTTP 409 Conflict with error details:
```json
{
  "error": "Cannot meet desired delivery date",
  "earliest_promise": "2026-02-15",
  "days_late": 5,
  "options": [...]
}
```

---

### Mode C: NO_EARLY_DELIVERY

**Use Case**: Customer does NOT want delivery earlier than desired date.

**Behavior**:
- If `promise_date < desired_date`: Adjust promise to `desired_date`
  - ✅ `on_time = True`
  - `adjusted_due_to_no_early_delivery = True`
  - Reason: "Can deliver earlier on X, but adjusted to desired date Y"
  
- If `promise_date > desired_date`: Promise unchanged
  - ❌ `on_time = False`

**Response**:
```json
{
  "promise_date": "2026-02-10",
  "promise_date_raw": "2026-02-05",
  "desired_date": "2026-02-10",
  "desired_date_mode": "NO_EARLY_DELIVERY",
  "on_time": true,
  "adjusted_due_to_no_early_delivery": true,
  "reasons": [
    "Can deliver earlier on 2026-02-05, but adjusted to desired date 2026-02-10 (no early delivery requested)."
  ]
}
```

---

## API Usage

### Request Format

```json
POST /api/promise
{
  "customer": "CUST-001",
  "items": [
    {
      "item_code": "SKU001",
      "qty": 10,
      "warehouse": "Warehouse-A"
    }
  ],
  "desired_date": "2026-02-10",
  "rules": {
    "desired_date_mode": "LATEST_ACCEPTABLE",
    "lead_time_buffer_days": 1,
    "processing_lead_time_days": 1,
    "no_weekends": true,
    "cutoff_time": "14:00",
    "timezone": "UTC"
  }
}
```

### Response Schema

```typescript
{
  promise_date: date,              // Final promise (after desired_date constraints)
  promise_date_raw: date | null,   // Computed promise before desired_date adjustment
  desired_date: date | null,       // Echoed from request
  desired_date_mode: string | null, // "LATEST_ACCEPTABLE" | "STRICT_FAIL" | "NO_EARLY_DELIVERY"
  on_time: boolean | null,         // True if promise <= desired (null if no desired_date)
  adjusted_due_to_no_early_delivery: boolean, // True if delayed to match desired_date
  confidence: "HIGH" | "MEDIUM" | "LOW",
  plan: [...],                     // Item fulfillment plan
  reasons: string[],               // Explanation
  blockers: string[],              // Issues
  options: PromiseOption[]         // Alternative scenarios
}
```

---

## Enhanced Options

When `promise_date > desired_date`, the engine generates actionable suggestions:

### 1. Split Shipment
```json
{
  "type": "split_shipment",
  "description": "Ship 2 items from stock immediately",
  "impact": "Partial delivery by 2026-02-05, remaining items later"
}
```

### 2. Expedite Purchase Order
```json
{
  "type": "expedite_po",
  "po_id": "PO-001",
  "description": "Expedite PO-001 for SKU001",
  "impact": "Could reduce promise date by up to 7 days"
}
```

### 3. Alternate Warehouse
```json
{
  "type": "alternate_warehouse",
  "description": "Check alternate warehouses for SKU001",
  "impact": "Could reduce promise date if stock available elsewhere"
}
```

---

## Dynamic Recalculation

The promise engine **always recalculates from current data**. Changes in stock, reservations, or incoming supply automatically update promises and the `on_time` flag.

### Example: Stock Reservation Impact

**Before Reservation** (Stock available):
```python
# Stock: 15 available, 0 reserved
response = promise_service.calculate_promise(
    items=[ItemRequest(item_code="SKU001", qty=10)],
    desired_date=date(2026, 2, 5)
)
# promise_date = 2026-01-28
# on_time = True
```

**After Reservation** (Stock depleted):
```python
# Stock: 15 available, 10 reserved → only 5 available
# PO: 10 units arriving 2026-02-10
response = promise_service.calculate_promise(
    items=[ItemRequest(item_code="SKU001", qty=10)],
    desired_date=date(2026, 2, 5)
)
# promise_date = 2026-02-12 (PO + processing + buffer)
# on_time = False
```

**Result**: `on_time` changes from `True` to `False` deterministically based on current stock state.

---

## Code Examples

### Python SDK

```python
from datetime import date
from src.services.promise_service import PromiseService
from src.models.request_models import ItemRequest, PromiseRules, DesiredDateMode

# Mode 1: LATEST_ACCEPTABLE
rules = PromiseRules(
    desired_date_mode=DesiredDateMode.LATEST_ACCEPTABLE,
    lead_time_buffer_days=1,
    no_weekends=True
)

response = promise_service.calculate_promise(
    customer="CUST-001",
    items=[ItemRequest(item_code="SKU001", qty=10)],
    desired_date=date(2026, 2, 10),
    rules=rules
)

if response.on_time:
    print(f"✅ On time: {response.promise_date}")
else:
    print(f"❌ Late by {(response.promise_date - response.desired_date).days} days")
    for option in response.options:
        print(f"   Option: {option.description}")

# Mode 2: STRICT_FAIL
try:
    rules_strict = PromiseRules(desired_date_mode=DesiredDateMode.STRICT_FAIL)
    response = promise_service.calculate_promise(
        customer="CUST-001",
        items=[ItemRequest(item_code="SKU001", qty=10)],
        desired_date=date(2026, 2, 1),  # Too soon
        rules=rules_strict
    )
except ValueError as e:
    print(f"Cannot promise: {e}")

# Mode 3: NO_EARLY_DELIVERY
rules_no_early = PromiseRules(desired_date_mode=DesiredDateMode.NO_EARLY_DELIVERY)
response = promise_service.calculate_promise(
    customer="CUST-001",
    items=[ItemRequest(item_code="SKU001", qty=10)],
    desired_date=date(2026, 2, 20),  # Far future
    rules=rules_no_early
)

print(f"Can deliver: {response.promise_date_raw}")
print(f"Promised: {response.promise_date}")
print(f"Adjusted: {response.adjusted_due_to_no_early_delivery}")
```

### REST API (cURL)

```bash
# LATEST_ACCEPTABLE Mode
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [{"item_code": "SKU001", "qty": 10, "warehouse": "WH-A"}],
    "desired_date": "2026-02-10",
    "rules": {
      "desired_date_mode": "LATEST_ACCEPTABLE",
      "lead_time_buffer_days": 1
    }
  }'

# STRICT_FAIL Mode (may return 409)
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [{"item_code": "SKU001", "qty": 10}],
    "desired_date": "2026-02-01",
    "rules": {"desired_date_mode": "STRICT_FAIL"}
  }'

# NO_EARLY_DELIVERY Mode
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [{"item_code": "SKU001", "qty": 10}],
    "desired_date": "2026-02-20",
    "rules": {"desired_date_mode": "NO_EARLY_DELIVERY"}
  }'
```

---

## Testing

### Run Tests

```bash
# All desired_date tests
pytest tests/unit/test_desired_date.py -v

# Full test suite
pytest tests/unit/ -v
```

### Test Coverage

- ✅ `test_no_desired_date_provided` - on_time is None when no desired_date
- ✅ `test_latest_acceptable_on_time` - on_time = True when promise <= desired
- ✅ `test_latest_acceptable_late` - on_time = False + options generated
- ✅ `test_strict_fail_on_time` - Succeeds when promise <= desired
- ✅ `test_strict_fail_late_raises_error` - Raises ValueError when late
- ✅ `test_no_early_delivery_promise_earlier` - Adjusts promise to desired_date
- ✅ `test_no_early_delivery_promise_later` - No adjustment when already late
- ✅ `test_options_generated_when_late` - Split shipment/expedite PO suggestions
- ✅ `test_dynamic_recalculation_stock_change` - Promise changes with stock
- ✅ `test_dynamic_recalculation_with_desired_date` - on_time changes with supply

**Result**: All 23 unit tests pass (13 original + 10 desired_date)

---

## Implementation Details

### Files Modified

1. **src/models/request_models.py**
   - Added `DesiredDateMode` enum
   - Added `desired_date_mode` field to `PromiseRules`

2. **src/models/response_models.py**
   - Added `promise_date_raw`, `desired_date`, `desired_date_mode`, `on_time`, `adjusted_due_to_no_early_delivery` fields to `PromiseResponse`

3. **src/services/promise_service.py**
   - Added `_apply_desired_date_constraints()` method (implements 3 modes)
   - Updated `calculate_promise()` to call desired_date logic
   - Enhanced `_suggest_options()` to generate split shipment suggestions

4. **tests/unit/test_desired_date.py**
   - New comprehensive test suite (10 tests)

### Algorithm Flow

```
1. Build fulfillment plan (stock + POs)
   ↓
2. Calculate ship_ready_date (available_date + processing_lead_time)
   ↓
3. Apply business rules → promise_date_raw
   ↓
4. Apply desired_date constraints:
   - LATEST_ACCEPTABLE: return promise_date_raw, calculate on_time
   - STRICT_FAIL: raise error if late
   - NO_EARLY_DELIVERY: adjust promise if too early
   ↓
5. Generate options if on_time = False
   ↓
6. Return PromiseResponse
```

---

## Performance & Scalability

- **No additional queries**: Desired_date logic is pure computation
- **O(1) mode selection**: Enum comparison
- **O(n) option generation**: Linear with number of items/POs
- **Deterministic**: Same inputs → identical outputs (no randomness)

---

## Troubleshooting

### Problem: `on_time` is always None

**Solution**: Ensure `desired_date` is provided in the request.

### Problem: STRICT_FAIL always fails

**Check**:
1. Is `desired_date` too soon for current supply?
2. Review `promise_date_raw` to see earliest feasible date
3. Check `options` for suggestions to meet constraint

### Problem: NO_EARLY_DELIVERY not adjusting promise

**Check**:
1. Verify `promise_date_raw < desired_date` (must be earlier to adjust)
2. Check `adjusted_due_to_no_early_delivery` flag in response
3. Confirm mode is set correctly in request

---

## Future Enhancements

Potential extensions:
- **Alternate warehouse recalculation**: Auto-query other warehouses when late
- **Split shipment optimization**: Calculate optimal split based on cost/urgency
- **ML-based expedite suggestions**: Predict which POs are expeditable
- **Customer preferences**: Store default `desired_date_mode` per customer

---

## Summary

The desired_date feature transforms OTP from a pure supply-driven calculator into a customer-centric promise engine. With three interpretation modes, dynamic recalculation, and enhanced suggestions, it provides the flexibility needed for real-world order promising while maintaining deterministic, testable behavior.

**Key Takeaway**: The promise engine always reflects current reality (stock, reservations, incoming supply) and automatically updates `on_time` status and suggestions as conditions change.
