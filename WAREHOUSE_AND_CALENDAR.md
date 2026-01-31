# Warehouse Classification and Calendar Handling

## Overview

The Order Promise Engine (OTP) now includes comprehensive warehouse classification and business calendar handling to prevent false delivery promises.

## Features Implemented

### 1. Warehouse Classification System

**Location:** `src/utils/warehouse_utils.py`

Warehouses are classified into 5 types based on inventory availability:

#### Warehouse Types

| Type | Description | Examples | Stock Availability |
|------|-------------|----------|-------------------|
| **SELLABLE** | Ready to ship immediately | Stores - SD, Stores - WH | Available now |
| **NEEDS_PROCESSING** | Requires processing before shipping | Finished Goods - SD | Available after processing lead time |
| **IN_TRANSIT** | Not available now; future supply only | Goods In Transit - SD | NOT available (PO-based only) |
| **NOT_AVAILABLE** | Cannot satisfy demand | Work In Progress - SD, Rejected, Scrap | Ignored |
| **GROUP** | Logical container; must expand to children | All Warehouses - SD | Must expand |

#### Key Functions

```python
from src.utils.warehouse_utils import WarehouseManager, WarehouseType

wm = WarehouseManager()

# Classify a warehouse
wh_type = wm.classify_warehouse("Goods In Transit - SD")
# Returns: WarehouseType.IN_TRANSIT

# Check if group warehouse
is_group = wm.is_group_warehouse("All Warehouses - SD")
# Returns: True

# Expand group to children
children = wm.get_child_warehouses("All Warehouses - SD")
# Returns: ["Stores - SD", "Finished Goods - SD", "Goods In Transit - SD", "Work In Progress - SD"]

# Expand and deduplicate
expanded = wm.expand_warehouse_list(["Stores - SD", "All Warehouses - SD"], deduplicate=True)
# Returns: ["Stores - SD", "Finished Goods - SD", "Goods In Transit - SD", "Work In Progress - SD"]

# Filter to available warehouses
available = wm.filter_available_warehouses(
    ["Stores - SD", "Goods In Transit - SD", "Work In Progress - SD"]
)
# Returns: ["Stores - SD"]  # Only SELLABLE and NEEDS_PROCESSING by default
```

### 2. Business Calendar (Sunday-Thursday Workweek)

**Location:** `src/services/promise_service.py`

All date calculations follow a **Sunday-Thursday workweek**:
- **Working days:** Sunday, Monday, Tuesday, Wednesday, Thursday
- **Weekend days:** Friday, Saturday

#### Calendar Utilities

```python
from src.services.promise_service import PromiseService

# Check if working day
is_working = PromiseService.is_working_day(date(2026, 1, 31))  # Friday
# Returns: False

# Get next working day
next_day = PromiseService.next_working_day(date(2026, 1, 31))  # Friday
# Returns: date(2026, 2, 2)  # Sunday

# Add working days (skips weekends)
result = PromiseService.add_working_days(date(2026, 1, 30), 1)  # Thursday + 1
# Returns: date(2026, 2, 2)  # Sunday (skips Fri, Sat)
```

#### Calendar Rules Applied

1. **Base Date:** If today is Friday/Saturday and `no_weekends=True`, base_date moves to next Sunday
2. **Processing Lead Time:** Counts ONLY working days (Thursday + 1 day = Sunday)
3. **Cutoff Rule:** Adds 1 working day (skips Friday/Saturday)
4. **Incoming PO Dates:** If PO arrives Friday/Saturday, treated as Sunday
5. **Final Promise Date:** Never lands on Friday/Saturday when `no_weekends=True`

### 3. Stock Allocation Logic

Stock is allocated based on warehouse type:

```
SELLABLE (Stores):
  └─> Available immediately at base_date
  └─> Ship-ready date = base_date + processing_lead_time

NEEDS_PROCESSING (Finished Goods):
  └─> Available after processing
  └─> Ship-ready date = base_date + processing_lead_time + 1 day

IN_TRANSIT:
  └─> Stock NOT counted as available
  └─> Logged as "not ship-ready; awaiting receipt"
  └─> Only PO-based supply used

NOT_AVAILABLE (WIP, Rejected):
  └─> Stock completely ignored
  └─> Logged as "not available for fulfillment"

GROUP:
  └─> Should be expanded before reaching allocation logic
  └─> Warning logged if not expanded
```

## Test Coverage

### Unit Tests

All tests located in `tests/unit/`:

#### Calendar Tests (`test_calendar_workweek.py`)
- 17 tests validating Sunday-Thursday workweek
- Working day detection
- Next working day calculation
- Adding working days with weekend skipping
- Business rule integration

#### Warehouse Tests (`test_warehouse_handling.py`)
- 21 tests validating warehouse classification
- Pattern matching for unmapped warehouses
- Group warehouse expansion and deduplication
- Stock allocation respects warehouse types
- IN_TRANSIT and WIP stock ignored
- SELLABLE stock immediately available
- Promise dates never on weekends

#### Desired Date Tests (`test_desired_date.py`)
- 10 tests for LATEST_ACCEPTABLE, STRICT_FAIL, NO_EARLY_DELIVERY modes
- Dynamic recalculation
- Enhanced options generation

#### Promise Service Tests (`test_promise_service.py`)
- 6 core algorithm tests
- Stock allocation, PO fulfillment, shortage handling

**Total: 61 unit tests, all passing ✅**

## API Usage Examples

### Test Scenarios

#### 1. Stock in SELLABLE Warehouse (Stores - SD)

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Grant Plastics Ltd.",
    "items": [{
      "item_code": "SKU005",
      "qty": 10,
      "warehouse": "Stores - SD"
    }],
    "rules": {
      "no_weekends": true,
      "lead_time_buffer_days": 1
    }
  }'
```

**Expected:** Stock immediately available, promise includes processing + buffer working days.

#### 2. Stock in IN_TRANSIT Warehouse

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Grant Plastics Ltd.",
    "items": [{
      "item_code": "SKU004",
      "qty": 10,
      "warehouse": "Goods In Transit - SD"
    }],
    "rules": {
      "no_weekends": true,
      "lead_time_buffer_days": 0
    }
  }'
```

**Expected:** Stock NOT counted as available; fulfillment via PO or shortage.

#### 3. Weekend Handling

```bash
# Request on Thursday with 1 day buffer
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Grant Plastics Ltd.",
    "items": [{
      "item_code": "SKU005",
      "qty": 10,
      "warehouse": "Stores - SD"
    }],
    "rules": {
      "no_weekends": true,
      "lead_time_buffer_days": 1
    }
  }'
```

**Expected:** Promise date = Sunday (skips Friday, Saturday).

#### 4. Desired Date with Calendar Rules

```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Grant Plastics Ltd.",
    "items": [{
      "item_code": "SKU005",
      "qty": 10,
      "warehouse": "Stores - SD"
    }],
    "desired_date": "2026-02-05",
    "rules": {
      "no_weekends": true,
      "lead_time_buffer_days": 0,
      "desired_date_mode": "LATEST_ACCEPTABLE"
    }
  }'
```

**Expected:** Promise calculated using working days, compared to desired_date, `on_time` flag returned.

## Implementation Details

### Warehouse Classification Pattern Matching

Unmapped warehouses are classified by name patterns:

- Contains "transit" or "in transit" → IN_TRANSIT
- Contains "wip" or "work in progress" → NOT_AVAILABLE
- Contains "finished goods" or "finished" → NEEDS_PROCESSING
- Contains "all" or "group" → GROUP
- Contains "scrap" or "reject" → NOT_AVAILABLE
- Default → SELLABLE

### Custom Classifications

Override default classifications:

```python
from src.utils.warehouse_utils import WarehouseManager, WarehouseType

custom_wm = WarehouseManager(
    custom_classifications={
        "custom warehouse - sd": WarehouseType.SELLABLE,
        "special transit": WarehouseType.IN_TRANSIT
    },
    custom_hierarchy={
        "custom group": ["Child Warehouse 1", "Child Warehouse 2"]
    }
)

# Use in PromiseService
promise_service = PromiseService(
    stock_service=stock_service,
    warehouse_manager=custom_wm
)
```

## Validation

Run all tests:

```bash
# Activate virtual environment
source /C/Users/NofJawamis/Desktop/ERPNextNof/.venv/Scripts/activate

# Run all unit tests
python -m pytest tests/unit -v

# Run specific test suites
python -m pytest tests/unit/test_warehouse_handling.py -v
python -m pytest tests/unit/test_calendar_workweek.py -v

# Check coverage
python -m pytest tests/unit --cov=src --cov-report=term-missing
```

**Current Coverage:**
- `promise_service.py`: 89%
- `warehouse_utils.py`: 88%
- Overall: 68%

## Key Points

✅ **Prevents False Promises:** IN_TRANSIT and WIP stock NOT counted as available  
✅ **Calendar-Aware:** All calculations follow Sunday-Thursday workweek  
✅ **Group Expansion:** Handles warehouse hierarchies correctly  
✅ **Deterministic:** Same inputs always produce same outputs  
✅ **Testable:** 61 unit tests validate behavior  
✅ **Explainable:** Reasons detail warehouse and calendar decisions  
✅ **Configurable:** Custom classifications and hierarchies supported

## Troubleshooting

### Issue: Stock from IN_TRANSIT warehouse used incorrectly

**Check:** Verify warehouse classification
```python
wm.classify_warehouse("Goods In Transit - SD")
# Should return: WarehouseType.IN_TRANSIT
```

### Issue: Promise date lands on Friday or Saturday

**Check:** Ensure `no_weekends=True` in rules
```python
rules = PromiseRules(no_weekends=True)
```

### Issue: Group warehouse not expanded

**Check:** Verify hierarchy is defined
```python
children = wm.get_child_warehouses("All Warehouses - SD")
# Should return list of children
```

## Next Steps

Potential enhancements:
1. Add support for custom processing lead times per warehouse type
2. Implement warehouse priority ordering for allocation
3. Add manufacturing lead time handling for NOT_AVAILABLE stock
4. Support multi-site warehouse hierarchies
5. Add warehouse capacity constraints

---

**OTP calculations are calendar-aware and follow a Sunday–Thursday workweek.**  
**Warehouse types prevent false delivery promises.**
