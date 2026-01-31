# Test Commands - OTP Application Scenarios

## Quick Test Commands

Run these commands from the project root directory to test different OTP scenarios.

---

## Scenario 1: Available Stock - Simple Order (Should Fulfill)

Test a simple order that should be fulfilled from available stock.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules
from datetime import date

service = PromiseService(MockSupplyService(), default_warehouse_manager)
request = PromiseRequest(
    customer='Test Customer',
    items=[ItemRequest(item_code='SKU005', qty=50, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
print(f'\nStatus: {result.status}')
print(f'Promise Date: {result.promise_date}')
print(f'Can Fulfill: {result.can_fulfill}')
print(f'Confidence: {result.confidence}')
"
```

**Expected**: Status=OK, Promise Date set, Can Fulfill=True, Confidence=HIGH

---

## Scenario 2: Insufficient Stock (Cannot Fulfill)

Test order with quantity exceeding available stock.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules

service = PromiseService(MockSupplyService(), default_warehouse_manager)
request = PromiseRequest(
    customer='Big Order Customer',
    items=[ItemRequest(item_code='SKU005', qty=500, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
print(f'\nStatus: {result.status}')
print(f'Promise Date: {result.promise_date}')
print(f'Can Fulfill: {result.can_fulfill}')
print(f'Shortage: {result.items[0].shortage}')
for blocker in result.blockers:
    print(f'Blocker: {blocker}')
"
```

**Expected**: Status=CANNOT_FULFILL, Promise Date=None, Can Fulfill=False, Shortage shown

---

## Scenario 3: Multi-Item Order (Coordination Test)

Test order with multiple items to verify coordination.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules

service = PromiseService(MockSupplyService(), default_warehouse_manager)
request = PromiseRequest(
    customer='Multi-Item Customer',
    items=[
        ItemRequest(item_code='SKU005', qty=20, warehouse='Stores - SD'),
        ItemRequest(item_code='SKU008', qty=10, warehouse='Stores - SD')
    ],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
print(f'\nStatus: {result.status}')
print(f'Promise Date: {result.promise_date}')
print(f'Can Fulfill: {result.can_fulfill}')
print(f'\nItem Details:')
for item in result.items:
    print(f'  {item.item_code}: Shortage={item.shortage}, Ready={item.estimated_available_date}')
"
```

**Expected**: Status=OK, Single coordinated promise date, All items fulfilled

---

## Scenario 4: Desired Date - On Time vs Late

Test order with desired delivery date to check on-time detection.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules
from datetime import date

service = PromiseService(MockSupplyService(), default_warehouse_manager)
request = PromiseRequest(
    customer='Urgent Customer',
    desired_date=date(2026, 2, 10),
    items=[ItemRequest(item_code='SKU005', qty=30, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
print(f'\nStatus: {result.status}')
print(f'Promise Date: {result.promise_date}')
print(f'Desired Date: {result.desired_date}')
print(f'On Time: {result.on_time}')
print(f'Days Early/Late: {(result.desired_date - result.promise_date).days if result.promise_date else \"N/A\"}')
"
```

**Expected**: Status=OK, On Time=True, Shows days early

---

## Scenario 5: Calendar Enforcement (No Friday/Saturday)

Test that promises never fall on Friday or Saturday.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules
from datetime import date

service = PromiseService(MockSupplyService(), default_warehouse_manager)
request = PromiseRequest(
    customer='Calendar Test',
    items=[ItemRequest(item_code='SKU005', qty=10, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
day_name = result.promise_date.strftime('%A') if result.promise_date else 'None'
print(f'\nPromise Date: {result.promise_date}')
print(f'Day of Week: {day_name}')
print(f'Is Working Day: {day_name in [\"Sunday\", \"Monday\", \"Tuesday\", \"Wednesday\", \"Thursday\"]}')
"
```

**Expected**: Promise date is Sunday, Monday, Tuesday, Wednesday, or Thursday (never Friday/Saturday)

---

## Scenario 6: Different Warehouse Types

Test items from different warehouse types with different processing times.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules

service = PromiseService(MockSupplyService(), default_warehouse_manager)

# Test SELLABLE warehouse (Stores - SD)
request1 = PromiseRequest(
    customer='Test',
    items=[ItemRequest(item_code='SKU005', qty=10, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result1 = service.calculate_promise(request1)

# Test NEEDS_PROCESSING warehouse (Finished Goods - SD)
request2 = PromiseRequest(
    customer='Test',
    items=[ItemRequest(item_code='SKU005', qty=10, warehouse='Finished Goods - SD')],
    rules=PromiseRules(no_weekends=True)
)
result2 = service.calculate_promise(request2)

print(f'\nStores (SELLABLE): {result1.promise_date}')
print(f'Finished Goods (NEEDS_PROCESSING): {result2.promise_date}')
print(f'Processing adds 1 day: {result2.promise_date > result1.promise_date if result1.promise_date and result2.promise_date else \"N/A\"}')
"
```

**Expected**: NEEDS_PROCESSING warehouse adds 1 day processing time

---

## Scenario 7: Incoming Supply (Purchase Orders)

Test fulfillment using incoming PO supply.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules

service = PromiseService(MockSupplyService(), default_warehouse_manager)
request = PromiseRequest(
    customer='PO Test Customer',
    items=[ItemRequest(item_code='SKU004', qty=30, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
print(f'\nStatus: {result.status}')
print(f'Promise Date: {result.promise_date}')
print(f'Confidence: {result.confidence}')
print(f'\nFulfillment Plan:')
for item in result.items:
    print(f'  {item.item_code}:')
    for plan in item.fulfillment_plan:
        print(f'    - {plan.quantity} units from {plan.source} (ready: {plan.date})')
"
```

**Expected**: Status=OK, Shows stock + PO sources in fulfillment plan

---

## Scenario 8: Permission Error Handling (Mock)

Test system behavior when PO access is denied.

```bash
python -c "
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.utils.warehouse_utils import default_warehouse_manager
from src.models.request_models import PromiseRequest, ItemRequest, PromiseRules

# Mock service with simulated permission error
mock_service = MockSupplyService()
original_method = mock_service.get_incoming_supply
def mock_permission_error(item_code):
    return {'supply': [], 'access_error': 'permission_denied'}
mock_service.get_incoming_supply = mock_permission_error

service = PromiseService(mock_service, default_warehouse_manager)
request = PromiseRequest(
    customer='Permission Test',
    items=[ItemRequest(item_code='SKU005', qty=50, warehouse='Stores - SD')],
    rules=PromiseRules(no_weekends=True)
)
result = service.calculate_promise(request)
print(f'\nStatus: {result.status}')
print(f'Confidence: {result.confidence}')
print(f'Blockers: {result.blockers}')
"
```

**Expected**: Confidence=LOW or MEDIUM, Blocker message about PO access

---

## Scenario 9: Full Demo (All Scenarios)

Run the comprehensive demo script with all scenarios:

```bash
python demo_otp.py
```

**Expected**: 4 complete scenarios with detailed output for each

---

## Scenario 10: Real ERPNext Integration (If ERPNext Running)

Test with actual Sales Orders from ERPNext:

```bash
python test_sales_order.py
```

**Expected**: Fetches real sales orders and runs OTP calculation on them

---

## Unit Tests

Run the full test suite:

```bash
# All tests
pytest tests/ -v

# Only unit tests
pytest tests/unit/ -v

# Only calendar tests
pytest tests/unit/ -v -k "calendar"

# Only warehouse tests
pytest tests/unit/ -v -k "warehouse"

# With coverage
pytest tests/ --cov=src --cov-report=html
```

**Expected**: 73+ tests passing (96%+ pass rate)

---

## Quick Validation Checklist

Use these commands to verify core functionality:

```bash
# 1. Check calendar logic
python -c "from src.utils.calendar_utils import WorkingDayCalendar; from datetime import date; print('Friday is working day:', WorkingDayCalendar.is_working_day(date(2026, 1, 30))); print('Sunday is working day:', WorkingDayCalendar.is_working_day(date(2026, 2, 1)))"

# 2. Check warehouse classification
python -c "from src.utils.warehouse_utils import default_warehouse_manager; wh = default_warehouse_manager.get_warehouse_config('Stores - SD'); print(f'Stores type: {wh.warehouse_type.value}')"

# 3. Check mock data loaded
python -c "from src.services.mock_supply_service import MockSupplyService; service = MockSupplyService(); stock = service.get_available_stock('SKU005', 'Stores - SD'); print(f'SKU005 available: {stock}')"

# 4. Check ERPNext connectivity (if running)
python -c "from src.clients.erpnext_client import ERPNextClient; client = ERPNextClient(); print('ERPNext connected')"
```

---

## Environment Setup

Before running tests, ensure:

```bash
# 1. Virtual environment activated
source .venv/Scripts/activate  # Windows Git Bash
# or
.venv\Scripts\activate  # Windows CMD

# 2. Environment variables set (check .env file)
cat .env

# 3. Dependencies installed
pip install -r requirements.txt
```

---

## Expected Results Summary

| Scenario | Status | Promise Date | Can Fulfill | Confidence |
|----------|--------|--------------|-------------|------------|
| Available Stock | OK | Set | True | HIGH |
| Insufficient Stock | CANNOT_FULFILL | None | False | LOW |
| Multi-Item | OK | Coordinated | True | HIGH |
| On Time | OK | Before Desired | True | HIGH |
| Calendar Check | OK | Sun-Thu only | True | HIGH |
| Warehouse Types | OK | With Processing | True | HIGH |
| Incoming Supply | OK | With PO | True | HIGH |
| Permission Error | OK/CANNOT_PROMISE | Set/None | Varies | LOW/MEDIUM |

All tests should respect:
- ✅ Sunday-Thursday workweek (no Friday/Saturday promises)
- ✅ Warehouse semantics (SELLABLE, NEEDS_PROCESSING, IN_TRANSIT, etc.)
- ✅ Multi-item coordination (single promise date)
- ✅ Graceful error handling (permission errors → LOW confidence)
- ✅ Clear status messages (OK, CANNOT_FULFILL, CANNOT_PROMISE_RELIABLY)
