# Processing Lead Time Feature

## Overview

Processing Lead Time represents the internal warehouse handling time between when an item becomes available and when it's ready for shipment. This includes activities such as:
- Picking items from bins
- Quality assurance/inspection
- Packing and labeling
- Staging for carrier pickup
- Carrier booking and documentation

By modeling this realistic warehouse delay, the Order Promise Engine produces reliable, achievable promise dates that account for operational realities.

## Configuration

### System Default

Set in `src/config.py`:
```python
processing_lead_time_days_default: int = 1
```

This 1-day default applies to all items and warehouses unless overridden.

### Per-Request Override

In the PromiseRules model (API request):
```json
{
  "customer": "CUST-001",
  "items": [{"item_code": "SKU001", "qty": 10}],
  "rules": {
    "processing_lead_time_days": 2
  }
}
```

### Warehouse-Specific Override

Configure in PromiseService initialization:
```python
promise_service = PromiseService(
    stock_service,
    warehouse_lead_times={
        "Warehouse-A": 1,      # 1-day lead time
        "Warehouse-B": 2,      # 2-day lead time
        "Expedited-WH": 0      # Same-day processing
    }
)
```

### Item-Specific Override

Configure in PromiseService initialization:
```python
promise_service = PromiseService(
    stock_service,
    item_lead_times={
        "FAST-SKU": 0,         # No processing time (drop-ship)
        "BULKY-SKU": 3,        # 3-day processing (special handling)
        "CUSTOM-SKU": 5        # 5-day processing (requires QA)
    }
)
```

## Override Hierarchy

The promise engine resolves processing lead time using a deterministic priority hierarchy:

1. **Item-Specific Override** (highest priority)
   - Use when specific items require custom handling
   - Example: Drop-shipped items (0 days), custom orders (5 days)

2. **Warehouse-Specific Override**
   - Use for warehouse operational characteristics
   - Example: Expedited warehouse (0 days), standard warehouse (1 day)

3. **Request-Level Override**
   - Use for per-request business logic
   - Example: Rush orders (1 day), standard orders (2 days)

4. **System Default** (lowest priority)
   - Fallback value: 1 day
   - Applied when no other override matches

**Deterministic Behavior**: The hierarchy ensures the same item/warehouse combination always produces the same lead time, making promise calculations reproducible and testable.

## How It Works in Promise Calculations

### Step-by-Step Process

1. **Determine Item Availability**
   - Check stock available today
   - OR find incoming PO expected delivery date
   - Result: `available_date`

2. **Apply Processing Lead Time**
   - Resolve lead time from override hierarchy
   - Calculate: `ship_ready_date = available_date + processing_lead_time_days`
   - Result: `ship_ready_date` (when item is ready for shipment)

3. **Apply Business Rules**
   - Add lead time buffer (configured separately)
   - Apply cutoff time rule (if order placed after cutoff)
   - Skip weekends if configured
   - Result: `promise_date` (final customer promise)

### Example

**Scenario**: Order placed for SKU001 at 10am UTC
- Stock available today: Jan 26
- Processing lead time (warehouse override): 2 days
- Lead time buffer (rule): 1 day
- Weekend skip: No

**Calculation**:
```
available_date = Jan 26 (today)
ship_ready_date = Jan 26 + 2 days = Jan 28
promise_date = Jan 28 + 1 day buffer = Jan 29
```

**With PO**:
- Stock available: Jan 26 (5 units in stock)
- PO available: Jan 31 (required additional 15 units)
- Processing lead time: 2 days

**Calculation**:
```
stock:       available_date = Jan 26 → ship_ready_date = Jan 28
po:          available_date = Jan 31 → ship_ready_date = Feb 02
latest:      max(Jan 28, Feb 02) = Feb 02
promise_date = Feb 02 + 1 day buffer = Feb 03
```

## API Usage

### Basic Request with Processing Lead Time

```json
POST /api/promise

{
  "customer": "ACC-CUST-00001",
  "items": [
    {
      "item_code": "SKU001",
      "qty": 10,
      "warehouse": "Warehouse-A"
    }
  ],
  "rules": {
    "lead_time_buffer_days": 1,
    "no_weekends": true,
    "cutoff_time": "14:00",
    "timezone": "UTC",
    "processing_lead_time_days": 2
  }
}
```

### Response with Ship Ready Date

```json
{
  "promise_date": "2026-01-29",
  "confidence": "HIGH",
  "plan": [
    {
      "item_code": "SKU001",
      "qty_required": 10,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 10,
          "available_date": "2026-01-26",
          "ship_ready_date": "2026-01-28",
          "warehouse": "Warehouse-A"
        }
      ],
      "shortage": 0
    }
  ],
  "reasons": [
    "Item SKU001: 10.0 units from stock",
    "Added 1 day(s) lead time buffer",
    "Adjusted from 2026-01-28 to 2026-01-29 (business rules applied)"
  ]
}
```

## Implementation Details

### Code Location

**Configuration**: [src/config.py](../src/config.py)
```python
processing_lead_time_days_default: int = 1
```

**Request Model**: [src/models/request_models.py](../src/models/request_models.py)
```python
class PromiseRules(BaseModel):
    processing_lead_time_days: int = Field(1, ge=0, description="Warehouse processing days before shipment")
```

**Response Model**: [src/models/response_models.py](../src/models/response_models.py)
```python
class FulfillmentSource(BaseModel):
    available_date: date = Field(..., description="Date when available")
    ship_ready_date: date = Field(..., description="Date ready to ship (available_date + processing_lead_time)")
```

**Business Logic**: [src/services/promise_service.py](../src/services/promise_service.py)

#### Key Methods

1. `_get_processing_lead_time(item_code, warehouse, rules)` - Resolves lead time from hierarchy
2. `_build_item_plan(item, warehouse, today, rules)` - Calculates ship_ready_date for each fulfillment source
3. `calculate_promise(customer, items, rules)` - Uses ship_ready_date in final promise calculation

## Testing

### Unit Tests

Located in `tests/unit/test_processing_lead_time.py`

- `test_processing_lead_time_default` - Verifies default 1-day processing time
- `test_processing_lead_time_warehouse_override` - Tests warehouse-specific override
- `test_processing_lead_time_item_override` - Tests item-specific override
- `test_processing_lead_time_rule_override` - Tests warehouse beats rule in hierarchy
- `test_processing_lead_time_hierarchy_item_beats_all` - Tests full override hierarchy
- `test_processing_lead_time_with_po` - Tests processing time with PO fulfillment
- `test_processing_lead_time_with_weekends` - Tests weekend skipping after processing lead time

### Integration Tests

Located in `tests/integration/test_processing_lead_time_integration.py`

- Tests with mock supply service and actual CSV data
- Validates end-to-end promise calculations with different lead time configurations
- Confirms no artificial shortages are created

### Running Tests

```bash
# Unit tests only
pytest tests/unit/test_processing_lead_time.py -v

# Integration tests only
pytest tests/integration/test_processing_lead_time_integration.py -v

# All tests
pytest tests/unit/test_processing_lead_time.py tests/integration/test_processing_lead_time_integration.py -v
```

## Real-World Examples

### Example 1: Standard Warehouse

**Configuration**:
```python
warehouse_lead_times = {
    "Standard-WH": 1  # 1 day for picking, packing, QA
}
```

**Order**: 100 units from stock
- Available: Today (Jan 26)
- Ship ready: Jan 27 (+ 1 day processing)
- Promised: Jan 28 (+ 1 day buffer)

### Example 2: Expedited Warehouse

**Configuration**:
```python
warehouse_lead_times = {
    "Expedited-WH": 0  # Same-day shipping
}
```

**Order**: 50 units from stock
- Available: Today (Jan 26)
- Ship ready: Jan 26 (+ 0 days processing)
- Promised: Jan 27 (+ 1 day buffer)

### Example 3: Drop-Ship Item

**Configuration**:
```python
item_lead_times = {
    "DROP-SHIP-001": 0  # Vendor ships directly
}
```

**Order**: 10 units from PO
- Available: Jan 31 (PO expected date)
- Ship ready: Jan 31 (+ 0 days processing)
- Promised: Feb 1 (+ 1 day buffer)

### Example 4: Custom Order (Requires QA)

**Configuration**:
```python
item_lead_times = {
    "CUSTOM-ORDER-001": 5  # Extensive QA required
}
```

**Order**: 5 custom units from stock
- Available: Today (Jan 26)
- Ship ready: Jan 31 (+ 5 days processing)
- Promised: Feb 1 (+ 1 day buffer)

## Performance Considerations

- **Memory**: Warehouse and item lead time dicts stored in PromiseService instance
- **Lookup Time**: O(1) dictionary lookups for override resolution
- **Calculation**: One addition per fulfillment source (negligible)
- **Determinism**: No randomness or external dependencies

## Future Enhancements

Potential extensions to processing lead time feature:

1. **Time-Based Overrides**: Different lead times for different times of day
2. **Seasonal Adjustments**: Longer lead times during peak seasons
3. **Customer-Specific Overrides**: Custom lead times for VIP customers
4. **Dynamic Learning**: ML-based lead time predictions from historical data
5. **Integration with WMS**: Real-time lead times from warehouse management system

## Troubleshooting

### Problem: Promise dates not reflecting processing lead time

**Check**:
1. Verify `processing_lead_time_days` is set in PromiseRules
2. Confirm warehouse/item overrides are passed to PromiseService constructor
3. Review response `ship_ready_date` field (should be available_date + lead_time)

### Problem: Override hierarchy not working

**Check**:
1. Verify item override dict is passed to PromiseService
2. Confirm warehouse name matches exactly (case-sensitive)
3. Review _get_processing_lead_time() implementation for priority order

### Problem: Artificial shortages appearing

**Check**:
1. Confirm processing lead time is reasonable (not creating backlog)
2. Verify PO expected dates are in the future
3. Check that stock availability is calculated correctly (exclude processing lead time from stock calc)

## Summary

Processing Lead Time transforms the Order Promise Engine from a pure supply-availability calculator into a realistic operation-aware system. By modeling warehouse handling time alongside supply constraints, the engine delivers promises that customer service teams can actually deliver, improving customer satisfaction and operational efficiency.
