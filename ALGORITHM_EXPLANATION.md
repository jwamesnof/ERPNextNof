# 🧠 Promise Calculation Algorithm - Deep Dive

## Executive Summary

The **Order Promise Engine (OTP)** implements a **deterministic, explainable promise calculation algorithm** that considers real-time inventory, incoming supply chains, and business rules to provide reliable delivery date commitments.

**Key Principle**: Every promise is backed by data and explained with reasons. The algorithm is 100% deterministic - the same order input always produces the same output.

---

## Table of Contents
1. [Algorithm Overview](#algorithm-overview)
2. [5-Step Core Algorithm](#5-step-core-algorithm)
3. [Warehouse Classification](#warehouse-classification)
4. [Fulfillment Planning](#fulfillment-planning)
5. [Business Rules](#business-rules)
6. [Confidence Scoring](#confidence-scoring)
7. [Desired Date Modes](#desired-date-modes)
8. [Edge Cases & Handling](#edge-cases--handling)
9. [Examples & Walkthroughs](#examples--walkthroughs)

---

## Algorithm Overview

### High-Level Flow

```
Sales Order with Items & Desired Date
                ↓
        ┌───────────────────────┐
        │ STEP 1: BUILD PLAN    │
        │ Gather stock & POs    │
        └───────────┬───────────┘
                    ↓
        ┌───────────────────────┐
        │ STEP 2: ALLOCATION    │
        │ Map fulfillment       │
        └───────────┬───────────┘
                    ↓
        ┌───────────────────────┐
        │ STEP 3: APPLY RULES   │
        │ Calendar & buffers    │
        └───────────┬───────────┘
                    ↓
        ┌───────────────────────┐
        │ STEP 4: DESIRED DATE  │
        │ Check constraints     │
        └───────────┬───────────┘
                    ↓
        ┌───────────────────────┐
        │ STEP 5: CONFIDENCE    │
        │ Score & explanations  │
        └───────────┬───────────┘
                    ↓
            Promise Response
    (Date, Confidence, Reasons)
```

---

## 5-Step Core Algorithm

### Step 1: Build Fulfillment Plan

**Goal**: For each item, identify all sources of supply and when they're available.

#### 1a. Query Current Stock

```python
# Query ERPNext Bin table
stock = erpnext_client.get_bin_details(
    item_code="ITEM-001",
    warehouse="Stores - WH"
)

# Response:
{
    "actual_qty": 15.0,        # Physical stock count
    "reserved_qty": 5.0,       # Reserved for other orders
    "projected_qty": 10.0      # Available: actual - reserved
}

# Available now is min(actual, projected)
available_now = 10.0
available_date = today  # Can ship today
```

**Warehouse Classification Check**:
```python
warehouse_type = warehouse_manager.classify_warehouse("Stores - WH")

# Only SELLABLE warehouses are used for fulfillment
# NEEDS_PROCESSING warehouses: add processing_lead_time_days
# IN_TRANSIT warehouses: ignored (stock is locked)
# NOT_AVAILABLE warehouses: ignored
# GROUP warehouses: sum of components
```

#### 1b. Query Incoming Purchase Orders

```python
# Get all open POs for this item
pos = erpnext_client.get_incoming_purchase_orders(item_code="ITEM-001")

# Response: List of POs
[
    {
        "po_id": "PO-001",
        "item_code": "ITEM-001",
        "qty": 20.0,
        "received_qty": 0.0,
        "pending_qty": 20.0,
        "schedule_date": "2026-02-20",
        "warehouse": "Goods In Transit - SD",
        "supplier": "SUPPLIER-A"
    },
    {
        "po_id": "PO-002",
        "item_code": "ITEM-001",
        "qty": 30.0,
        "received_qty": 5.0,
        "pending_qty": 25.0,
        "schedule_date": "2026-02-25",
        "warehouse": "Goods In Transit - SD",
        "supplier": "SUPPLIER-B"
    }
]

# Convert to fulfillment sources:
# - PO-001: 20 units available on 2026-02-20
# - PO-002: 25 units available on 2026-02-25
```

#### 1c. Build Item Plan

```python
# For ITEM-001, customer requests 50 units

item_plan = ItemPlan(
    item_code="ITEM-001",
    requested_qty=50.0,
    fulfilled_qty=0.0,
    shortage=50.0,
    fulfillment_sources=[
        # Source 1: Current stock
        FulfillmentSource(
            source_type="Stock",
            warehouse="Stores - WH",
            qty=10.0,
            available_date=today,
            confidence="HIGH"
        ),
        # Source 2: First PO
        FulfillmentSource(
            source_type="PurchaseOrder",
            po_id="PO-001",
            warehouse="Goods In Transit - SD",
            qty=20.0,
            available_date=date(2026, 2, 20),
            confidence="MEDIUM"
        ),
        # Source 3: Second PO
        FulfillmentSource(
            source_type="PurchaseOrder",
            po_id="PO-002",
            warehouse="Goods In Transit - SD",
            qty=20.0,  # Only 20 of 25 needed
            available_date=date(2026, 2, 25),
            confidence="LOW"
        )
    ]
)

# Summary: 10 + 20 + 20 = 50 units fulfilled
# Latest availability: max(today, 2026-02-20, 2026-02-25) = 2026-02-25
```

---

### Step 2: Allocate Fulfillment Sources

**Goal**: Assign fulfillment sources to items chronologically.

```python
# Algorithm: Chronological Fulfillment
# Principle: Promise the EARLIEST date when ALL quantities are available

def allocate_fulfillment(items, rules):
    """
    Allocate stock to items in order they become available.
    """
    
    # Collect all fulfillment sources from all items
    all_sources = []
    for item in items:
        all_sources.extend(item.fulfillment_sources)
    
    # Sort by availability date (earliest first)
    all_sources.sort(key=lambda s: s.available_date)
    
    # Allocate quantities chronologically
    total_fulfilled = 0
    total_needed = sum(item.requested_qty for item in items)
    
    latest_fulfillment_date = today
    
    for source in all_sources:
        if total_fulfilled >= total_needed:
            break
        
        quantity_to_fulfill = min(
            source.qty,
            total_needed - total_fulfilled
        )
        
        # This source is available on source.available_date
        # Update the latest promised date
        latest_fulfillment_date = max(
            latest_fulfillment_date,
            source.available_date
        )
        
        total_fulfilled += quantity_to_fulfill
    
    # The promise date is when the LAST item becomes available
    promise_date_raw = latest_fulfillment_date
    
    return promise_date_raw
```

**Example**:
```
Sources sorted by date:
1. Stock: 10 units, available today (Feb 7)
2. PO-001: 20 units, available Feb 20
3. PO-002: 25 units, available Feb 25

Order for 50 units:
- Take 10 from stock (today) → Need 40 more
- Take 20 from PO-001 (Feb 20) → Need 20 more
- Take 20 from PO-002 (Feb 25) → Fulfilled

Promise Date Raw: Feb 25 (when last source available)
```

---

### Step 3: Apply Business Rules

**Goal**: Transform the raw promise date into a final date considering business constraints.

#### Rule 1: Add Lead Time Buffer

```python
def add_working_days(start_date, working_days, skip_weekends=False):
    """
    Add N working days to a date.
    In OTP, workweek is Sunday-Thursday (Friday=4, Saturday=5 are weekend).
    """
    
    if not skip_weekends:
        # Simple addition if weekends allowed
        return start_date + timedelta(days=working_days)
    else:
        # Count only working days (Sun-Thu)
        current = start_date
        days_added = 0
        
        while days_added < working_days:
            current += timedelta(days=1)
            
            # Skip if Friday(4) or Saturday(5)
            if current.weekday() not in [4, 5]:
                days_added += 1
        
        return current

# Example:
# promise_date_raw = Feb 25, 2026 (Tuesday)
# lead_time_buffer_days = 2
# no_weekends = True

promise_date = add_working_days(
    date(2026, 2, 25),  # Tuesday
    working_days=2,
    skip_weekends=True
)
# Result: Thursday, Feb 27 (skip Wed+Thu = 2 working days past Tue)
```

#### Rule 2: Apply Cutoff Time

```python
def apply_cutoff_rule(promise_date, cutoff_time="14:00", today=None):
    """
    If order placed after cutoff time, add 1 working day.
    
    Logic:
    - If current time > cutoff_time (e.g., 14:00)
    - Tomorrow is earliest day promise can have impact
    - Add 1 day to promise date
    """
    
    if today is None:
        today = date.today()
    
    current_time = datetime.now().time()
    cutoff = datetime.strptime(cutoff_time, "%H:%M").time()
    
    if current_time > cutoff:
        # Order placed after cutoff
        # Promise date pushed to next day
        promise_date += timedelta(days=1)
    
    return promise_date

# Example:
# Current time: 15:30 (3:30 PM)
# Cutoff time: 14:00 (2:00 PM)
# promise_date_before = Feb 27
# promise_date_after = Feb 28 (add 1 day)
```

#### Rule 3: Skip Weekends

```python
def skip_weekends(target_date):
    """
    Ensure promise date is NOT on Friday or Saturday.
    If it falls on weekend, move to next Sunday.
    """
    
    # Friday=4, Saturday=5 in Python's weekday()
    while target_date.weekday() in [4, 5]:
        target_date += timedelta(days=1)
    
    return target_date

# Example:
# target_date = Friday, Feb 28
# Result: Sunday, Mar 1
```

#### Combined Rule Application

```python
def apply_business_rules(base_date, rules, today):
    """
    Apply all rules in sequence.
    """
    
    promise_date = base_date
    
    # Rule 1: Add lead time buffer (working days only if no_weekends=True)
    if rules.no_weekends:
        promise_date = add_working_days(
            promise_date,
            rules.lead_time_buffer_days,
            skip_weekends=True
        )
    else:
        promise_date += timedelta(days=rules.lead_time_buffer_days)
    
    # Rule 2: Apply cutoff time
    promise_date = apply_cutoff_rule(promise_date, rules.cutoff_time, today)
    
    # Rule 3: Skip weekends
    if rules.no_weekends:
        promise_date = skip_weekends(promise_date)
    
    return promise_date

# Example execution:
# base_date = Feb 25 (Tue)
# rules.lead_time_buffer_days = 2
# rules.no_weekends = True
# rules.cutoff_time = "14:00"
# current_time = 15:30

# Step 1: Add 2 working days (Sun-Thu only)
#   Feb 25 (Tue) + 1 working day = Feb 26 (Wed)
#   Feb 26 (Wed) + 1 working day = Feb 27 (Thu)
#   Result: Feb 27 (Thu)

# Step 2: Apply cutoff (add 1 day since past 14:00)
#   Feb 27 (Thu) + 1 = Feb 28 (Fri)

# Step 3: Skip weekends
#   Feb 28 (Fri) is weekend
#   Next working day = Mar 1 (Sun)

# FINAL PROMISE DATE: Mar 1, 2026
```

---

### Step 4: Apply Desired Date Constraints

**Goal**: If customer specified a desired date, ensure promise respects it.

#### Four Modes for Handling Desired Date

```python
class DesiredDateMode(str, Enum):
    """How to interpret customer's desired delivery date."""
    
    LATEST_ACCEPTABLE = "LATEST_ACCEPTABLE"
    # Meaning: "Deliver by Feb 28 at latest"
    # Promise: min(calculated_date, desired_date)
    # Customer happy if we deliver earlier
    
    NO_EARLY_DELIVERY = "NO_EARLY_DELIVERY"
    # Meaning: "Don't deliver before Feb 28"
    # Promise: max(calculated_date, desired_date)
    # Prevent "too early" delivery disrupting warehouse
    
    STRICT_FAIL = "STRICT_FAIL"
    # Meaning: "Must deliver by Feb 20 or don't bother"
    # Promise: calculated_date if <= desired_date, else NULL
    # Hard constraint - cannot promise if too late
```

#### Implementation

```python
def apply_desired_date_constraints(promise_date_raw, desired_date, mode, plan):
    """
    Adjust promise date based on desired_date_mode.
    """
    
    if not desired_date:
        # No desired date provided
        return {
            "promise_date": promise_date_raw,
            "on_time": None,
            "adjusted": False
        }
    
    if mode == DesiredDateMode.LATEST_ACCEPTABLE:
        # Promise the EARLIER of the two dates
        adjusted_date = min(promise_date_raw, desired_date)
        on_time = (adjusted_date <= desired_date)
        
        return {
            "promise_date": adjusted_date,
            "on_time": on_time,
            "adjusted": (adjusted_date != promise_date_raw),
            "mode": "LATEST_ACCEPTABLE"
        }
    
    elif mode == DesiredDateMode.NO_EARLY_DELIVERY:
        # Promise the LATER of the two dates
        adjusted_date = max(promise_date_raw, desired_date)
        on_time = (adjusted_date <= desired_date)
        
        return {
            "promise_date": adjusted_date,
            "on_time": on_time,
            "adjusted": (adjusted_date != promise_date_raw),
            "mode": "NO_EARLY_DELIVERY"
        }
    
    elif mode == DesiredDateMode.STRICT_FAIL:
        # Can only promise if we can meet the desired date
        if promise_date_raw <= desired_date:
            return {
                "promise_date": promise_date_raw,
                "on_time": True,
                "adjusted": False,
                "mode": "STRICT_FAIL"
            }
        else:
            return {
                "promise_date": None,  # Cannot promise
                "on_time": False,
                "adjusted": False,
                "can_fulfill": False,
                "mode": "STRICT_FAIL"
            }

# Examples:
# Case 1: LATEST_ACCEPTABLE
#   promised = Mar 5, desired = Mar 8
#   result = min(Mar 5, Mar 8) = Mar 5 ✓ On time
#
# Case 2: LATEST_ACCEPTABLE
#   promised = Mar 15, desired = Mar 8
#   result = min(Mar 15, Mar 8) = Mar 8 ✗ Early promise fails
#
# Case 3: NO_EARLY_DELIVERY
#   promised = Mar 5, desired = Mar 8
#   result = max(Mar 5, Mar 8) = Mar 8 (delay to respect request)
#
# Case 4: STRICT_FAIL
#   promised = Mar 15, desired = Mar 8
#   result = NULL (cannot fulfill requirement)
```

---

### Step 5: Calculate Confidence & Explanations

**Goal**: Score the promise reliability and explain the reasoning.

#### Confidence Scoring

```python
class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"      # 80%+ confidence we'll deliver on time
    MEDIUM = "MEDIUM"  # 50-80% confidence
    LOW = "LOW"        # <50% confidence or external risks

def calculate_confidence(plan, promise_date, today):
    """
    Score confidence based on fulfillment sources and lead times.
    """
    
    score = 100.0  # Start at 100%
    
    # Factor 1: Reduce confidence if fulfilled from POs (lead time uncertainty)
    for item in plan:
        for source in item.fulfillment_sources:
            if source.source_type == "Stock":
                # Stock confidence: HIGH (we have it now)
                pass
            elif source.source_type == "PurchaseOrder":
                # PO confidence depends on lead time
                days_until_delivery = (source.available_date - today).days
                
                if days_until_delivery <= 3:
                    # Short lead time, relatively safe
                    score -= 5  # Minimal penalty
                elif days_until_delivery <= 7:
                    # Medium lead time
                    score -= 15  # Moderate penalty
                elif days_until_delivery <= 14:
                    # Long lead time
                    score -= 25  # Significant penalty
                else:
                    # Very long lead time
                    score -= 35  # Major penalty
    
    # Factor 2: Check for inventory shortage
    total_requested = sum(item.requested_qty for item in plan)
    total_fulfilled = sum(
        sum(src.qty for src in item.fulfillment_sources)
        for item in plan
    )
    
    if total_fulfilled < total_requested:
        shortage = total_requested - total_fulfilled
        shortage_pct = (shortage / total_requested) * 100
        score -= min(shortage_pct * 2, 50)  # Penalize shortages
    
    # Factor 3: Check if promise was constrained by desired_date
    # (indicates external pressure)
    if adjusted_due_to_no_early_delivery:
        score -= 10  # Slight penalty
    
    # Convert score to level
    if score >= 75:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    else:
        return "LOW"
```

#### Generating Explanations

```python
def generate_reasons(plan, promise_date, base_date, rules):
    """
    Create human-readable explanations for the promise.
    """
    
    reasons = []
    
    for item in plan:
        sources_str = []
        for source in item.fulfillment_sources:
            if source.source_type == "Stock":
                sources_str.append(f"{source.qty}u from {source.warehouse} (available now)")
            else:  # PurchaseOrder
                sources_str.append(f"{source.qty}u from PO {source.po_id} (arriving {source.available_date})")
        
        reason = f"ITEM-{item.item_code}: Fulfilled by {', '.join(sources_str)}"
        reasons.append(reason)
    
    # Add rule applications
    if (promise_date - base_date).days > 0:
        buffer_days = (promise_date - base_date).days
        reasons.append(f"Applied {buffer_days} day lead time buffer")
    
    if rules.no_weekends:
        reasons.append("Excluded weekends from promise date")
    
    return reasons
```

#### Identifying Blockers

```python
def identify_blockers(plan, has_po_access_error=False):
    """
    Identify issues that might affect fulfillment.
    """
    
    blockers = []
    
    # Check for shortages
    for item in plan:
        if item.shortage > 0:
            blockers.append(f"Shortage: {item.shortage}u of {item.item_code}")
    
    # Check for late POs
    for item in plan:
        for source in item.fulfillment_sources:
            if source.source_type == "PurchaseOrder":
                days_away = (source.available_date - today).days
                if days_away > 7:
                    blockers.append(f"PO {source.po_id} is {days_away} days out (high uncertainty)")
    
    # Check for permission issues
    if has_po_access_error:
        blockers.append("PO data access denied - confidence reduced")
    
    return blockers
```

#### Suggesting Options

```python
def suggest_options(plan, blockers, desired_date=None):
    """
    Suggest alternative fulfillment approaches.
    """
    
    options = []
    
    # Option 1: Split shipment (partial now, balance later)
    stock_available = sum(
        src.qty for item in plan
        for src in item.fulfillment_sources
        if src.source_type == "Stock"
    )
    
    if stock_available > 0:
        options.append(
            PromiseOption(
                option_type="SPLIT_SHIPMENT",
                description=f"Ship {stock_available}u now, remainder with next PO",
                proposed_date_1=today,
                proposed_date_2=promise_date
            )
        )
    
    # Option 2: Rush order from alternate supplier
    if "Shortage" in str(blockers):
        options.append(
            PromiseOption(
                option_type="RUSH_PROCUREMENT",
                description="Expedite PO or source from alternate supplier",
                risk_level="MEDIUM"
            )
        )
    
    # Option 3: Desired date adjustment (if STRICT_FAIL)
    if desired_date and promise_date > desired_date:
        days_gap = (promise_date - desired_date).days
        options.append(
            PromiseOption(
                option_type="DESIRED_DATE_EXTENSION",
                description=f"Extend desired date by {days_gap} days to meet fulfillment",
                gap_days=days_gap
            )
        )
    
    return options
```

---

## Warehouse Classification

**Purpose**: Different warehouses have different fulfillment capabilities.

```python
class WarehouseType(Enum):
    SELLABLE = "SELLABLE"
    # Can ship directly to customer
    # Examples: "Stores - SD", "Finished Goods - WH"
    # Lead time: 0 days
    
    NEEDS_PROCESSING = "NEEDS_PROCESSING"
    # Stock must be processed before shipment
    # Examples: "Raw Materials - WH", "QC - WH", "Work in Process - WH"
    # Lead time: Add processing_lead_time_days (default 1)
    
    IN_TRANSIT = "IN_TRANSIT"
    # Stock is in transit and locked
    # Examples: "Goods In Transit - SD", "In Transit - WH"
    # Lead time: Available on schedule_date from PO
    
    NOT_AVAILABLE = "NOT_AVAILABLE"
    # Warehouse not used for fulfillment
    # Examples: "QC Failed - WH", "Scrap - WH", "Damaged - WH"
    # Lead time: Ignore completely
    
    GROUP = "GROUP"
    # Virtual warehouse (sum of child warehouses)
    # Examples: Any warehouse set as "parent_warehouse"
    # Lead time: Sum from child warehouses

# Classification logic
def classify_warehouse(warehouse_doc: Dict) -> WarehouseType:
    """
    Classify warehouse based on attributes.
    """
    
    if warehouse_doc.get("disabled"):
        return WarehouseType.NOT_AVAILABLE
    
    warehouse_type = warehouse_doc.get("warehouse_type", "").lower()
    
    if "sellable" in warehouse_type or "finished" in warehouse_type:
        return WarehouseType.SELLABLE
    
    if "processing" in warehouse_type or "qc" in warehouse_type:
        return WarehouseType.NEEDS_PROCESSING
    
    if "transit" in warehouse_type or "in_transit" in warehouse_type:
        return WarehouseType.IN_TRANSIT
    
    if warehouse_doc.get("parent_warehouse"):
        return WarehouseType.GROUP
    
    # Default based on warehouse name patterns
    name_lower = warehouse_doc.get("name", "").lower()
    
    if any(x in name_lower for x in ["raw", "semi", "process"]):
        return WarehouseType.NEEDS_PROCESSING
    
    if any(x in name_lower for x in ["transit", "incoming"]):
        return WarehouseType.IN_TRANSIT
    
    return WarehouseType.SELLABLE  # Default
```

---

## Fulfillment Planning

### Stock Allocation Algorithm

```python
def build_fulfillment_plan(item, warehouses, rules):
    """
    Determine fulfillment sources for an item.
    
    Preference order:
    1. SELLABLE warehouse stock (ship now)
    2. NEEDS_PROCESSING stock (ship after processing)
    3. IN_TRANSIT (POs) sorted by arrival date
    """
    
    fulfillment_sources = []
    
    # Phase 1: Sellable stock
    for warehouse in warehouses:
        if classify_warehouse(warehouse) == WarehouseType.SELLABLE:
            stock = get_bin_details(item.item_code, warehouse.name)
            if stock.projected_qty > 0:
                fulfillment_sources.append(
                    FulfillmentSource(
                        source_type="Stock",
                        warehouse=warehouse.name,
                        qty=min(stock.projected_qty, item.qty),
                        available_date=today,
                        confidence="HIGH"
                    )
                )
    
    # Phase 2: Processing stock
    for warehouse in warehouses:
        if classify_warehouse(warehouse) == WarehouseType.NEEDS_PROCESSING:
            stock = get_bin_details(item.item_code, warehouse.name)
            if stock.projected_qty > 0:
                processing_days = rules.processing_lead_time_days
                fulfillment_sources.append(
                    FulfillmentSource(
                        source_type="Stock",
                        warehouse=warehouse.name,
                        qty=min(stock.projected_qty, item.qty),
                        available_date=today + timedelta(days=processing_days),
                        confidence="MEDIUM"
                    )
                )
    
    # Phase 3: Purchase orders (sorted by date)
    pos = get_incoming_purchase_orders(item.item_code)
    pos.sort(key=lambda p: p['schedule_date'])
    
    for po in pos:
        if po['pending_qty'] > 0:
            fulfillment_sources.append(
                FulfillmentSource(
                    source_type="PurchaseOrder",
                    po_id=po['po_id'],
                    warehouse=po['warehouse'],
                    qty=po['pending_qty'],
                    available_date=parse_date(po['schedule_date']),
                    confidence="LOW" if (po['schedule_date'] - today).days > 7 else "MEDIUM"
                )
            )
    
    return fulfillment_sources
```

---

## Business Rules

### Calendar System

```python
class WorkweekCalendar:
    """
    OTP uses Islamic workweek: Sunday-Thursday
    Friday-Saturday are non-working days
    
    This is customizable per region/company in settings.
    """
    
    WORKING_DAYS = [0, 1, 2, 3, 4]  # Sun, Mon, Tue, Wed, Thu
    WEEKEND_DAYS = [5, 6]            # Fri, Sat
    
    @staticmethod
    def is_working_day(date_obj):
        """Check if date is on a working day."""
        return date_obj.weekday() in WorkweekCalendar.WORKING_DAYS
    
    @staticmethod
    def next_working_day(date_obj):
        """Get next working day."""
        while not WorkweekCalendar.is_working_day(date_obj):
            date_obj += timedelta(days=1)
        return date_obj
```

### Lead Time Buffer

```python
# Lead time buffer accounts for:
# - Warehouse processing time
# - Transit time from warehouse to customer
# - Buffer for unforeseen delays

rules = PromiseRules(
    lead_time_buffer_days=2,  # Add 2 working days
    processing_lead_time_days=1,  # 1 day warehouse processing
    no_weekends=True,  # Skip weekends
    cutoff_time="14:00"  # Orders after 2PM pushed to next day
)
```

---

## Desired Date Modes

### Visual Comparison

```
CASE 1: LATEST_ACCEPTABLE
Customer says: "I need it by Mar 8"
Calculated date: Mar 5

     Today    Mar 5 (promise)    Mar 8 (desired)
                    ✓ Early delivery acceptable
Result: Deliver Mar 5 ✓ On time

---

CASE 2: LATEST_ACCEPTABLE (miss deadline)
Customer says: "I need it by Mar 8"
Calculated date: Mar 15

     Today    Mar 8 (desired)    Mar 15 (promise)
                             ✗ Can't meet deadline
Result: Promise Mar 8 but alert that risky

---

CASE 3: NO_EARLY_DELIVERY
Customer says: "Don't deliver before Mar 10"
Calculated date: Mar 5

     Today    Mar 5 (promise)    Mar 10 (desired)
                             Hold until Mar 10
Result: Promise Mar 10 (prevent early delivery disruption)

---

CASE 4: STRICT_FAIL
Customer says: "Must arrive by Mar 5"
Calculated date: Mar 15

          Mar 5 (hard deadline)          Mar 15 (promise)
                                              ✗ Fail
Result: Cannot promise (return NULL/CANNOT_FULFILL)
```

---

## Edge Cases & Handling

### Edge Case 1: Zero Available Stock

```python
# Order for 50 units, no stock available
available_stock = 0
incoming_pos = [
    {"schedule_date": "2026-02-20", "qty": 30},
    {"schedule_date": "2026-02-25", "qty": 25}
]

# Allocate:
# - Take 30 from first PO (Feb 20)
# - Need 20 more, take 20 from second PO (Feb 25)
# Promise date: Feb 25

# Blockers: ["Shortage: 50u requested but only PO supply available"]
# Confidence: LOW (fully dependent on external POs)
```

### Edge Case 2: Insufficient Supply

```python
# Order for 100 units, available:
# - Stock: 10
# - PO-1: 40
# - PO-2: 30
# Total available: 80 < 100

shortage = 100 - 80 = 20

response = {
    "status": "CANNOT_FULFILL",
    "promise_date": None,
    "can_fulfill": False,
    "shortage": 20,
    "blockers": ["Shortage: 20 units cannot be fulfilled"],
    "options": [
        {
            "type": "SPLIT_SHIPMENT",
            "description": "Ship 80 units now, backorder 20 units"
        },
        {
            "type": "RUSH_PROCUREMENT",
            "description": "Expedite PO for missing 20 units"
        }
    ]
}
```

### Edge Case 3: Permission Denied (PO Access)

```python
# ERPNext returns HTTP 403 when querying POs
# (user lacks permission to view PO table)

try:
    pos = client.get_incoming_purchase_orders(item_code)
except ERPNextPermissionError:
    # Degrade gracefully
    has_po_access_error = True
    
    # Don't fail - calculate based on stock alone
    # But lower confidence significantly
    
    confidence = "LOW"  # Reduced due to missing PO data
    blockers.append("PO data unavailable (permission denied)")
    reasons.append("Promise based on stock only - PO visibility limited")
```

### Edge Case 4: Order Placed After Cutoff

```python
# Order placed at 16:00 (4 PM)
# Cutoff time: 14:00 (2 PM)
# Calculated promise: Feb 25

# After cutoff rule:
# promise_date = Feb 25 + 1 day = Feb 26

# Rationale: Order too late to process today,
# earliest processing is tomorrow
```

### Edge Case 5: Promise Date Falls on Weekend

```python
# Calculated: Friday, Feb 28
# no_weekends=True

# Skip weekend
# Friday Feb 28 → Weekend (skip)
# Saturday Mar 1 → Weekend (skip)
# Sunday Mar 2 → Working day ✓
# Result: Promise Mar 2
```

---

## Examples & Walkthroughs

### Example 1: Simple Stock-Only Promise

**Scenario**: Customer orders 20 units of ITEM-001, wants by Mar 10

**Data**:
```
Current stock (Stores - WH): 25 units available
Incoming POs: None
Desired date: Mar 10 (LATEST_ACCEPTABLE)
Rules: lead_time_buffer=1 day, no_weekends=True, cutoff_time=14:00
Current time: 10:00 AM (before cutoff)
```

**Step 1: Build Plan**
```
ITEM-001: 20 units
  Source: Stock at Stores - WH
  Available: 25 units
  Date: Today (Feb 7, 2026 - Thursday)
```

**Step 2: Allocate**
```
Total need: 20 units
Available: 25 units from stock
Latest date: Today (Feb 7)
```

**Step 3: Apply Rules**
```
Base date: Feb 7 (Thu)
+ Lead time: 1 working day
  Feb 7 (Thu) → Feb 8 (Fri)
+ Cutoff: 10:00 < 14:00 (no change)
+ Weekend: Feb 8 (Fri) is weekend
  Feb 8 (Fri) → Feb 9 (Sun) [next working day]
Final: Feb 9 (Sun)
```

**Step 4: Desired Date**
```
Calculated: Feb 9
Desired: Mar 10
Mode: LATEST_ACCEPTABLE
Result: min(Feb 9, Mar 10) = Feb 9
On-time: Yes ✓
```

**Step 5: Confidence**
```
Source: 100% from stock (HIGH confidence)
Lead time: 2 days (short)
Score: 100 - 0 = 100 → HIGH
```

**Response**:
```json
{
  "status": "OK",
  "promise_date": "2026-02-09",
  "confidence": "HIGH",
  "can_fulfill": true,
  "reasons": [
    "20 units available from stock (Stores - WH)",
    "Applied 1 day lead time buffer",
    "Excluded weekends"
  ],
  "blockers": [],
  "plan": [{
    "item_code": "ITEM-001",
    "requested_qty": 20,
    "fulfilled_qty": 20,
    "fulfillment_sources": [{
      "source_type": "Stock",
      "warehouse": "Stores - WH",
      "qty": 20,
      "available_date": "2026-02-07"
    }]
  }]
}
```

---

### Example 2: Complex Multi-Source Promise

**Scenario**: Customer orders 100 units of ITEM-002, needs by Feb 20

**Data**:
```
Current stock (Stores - WH): 30 units
Current stock (Raw Materials - WH): 25 units (needs processing)
Incoming POs:
  - PO-001: 30 units, arrive Feb 18
  - PO-002: 20 units, arrive Feb 25
Desired date: Feb 20 (LATEST_ACCEPTABLE)
Rules: lead_time_buffer=2, no_weekends=True, processing_lead_time=1 day
```

**Step 1: Build Plan**
```
Sources (sorted by date):
1. Stores - WH: 30 units (Feb 7, SELLABLE)
2. Raw Materials - WH: 25 units (Feb 8 after processing, NEEDS_PROCESSING)
3. PO-001: 30 units (Feb 18, IN_TRANSIT)
4. PO-002: 20 units (Feb 25, IN_TRANSIT)

Total available: 105 units
Request: 100 units ✓ Sufficient
```

**Step 2: Allocate (Chrono)**
```
1. Take 30 from Stores (Feb 7) → Need 70 more
2. Take 25 from Raw Materials (Feb 8) → Need 45 more
3. Take 30 from PO-001 (Feb 18) → Need 15 more
4. Take 15 from PO-002 (Feb 25) → Fulfilled!

Latest date: max(Feb 7, Feb 8, Feb 18, Feb 25) = Feb 25
```

**Step 3: Apply Rules**
```
Base: Feb 25 (Wed)
+ Buffer: 2 working days
  Feb 25 (Wed) → Feb 26 (Thu) → Feb 27 (Fri)
+ Cutoff: No impact (assume before 14:00)
+ Weekend: Feb 27 (Fri) is weekend
  Feb 27 (Fri) → Feb 28-Mar 1-Mar 2 (skip to Sun)
Final: Mar 1 (Sun)
```

**Step 4: Desired Date**
```
Calculated: Mar 1
Desired: Feb 20
Mode: LATEST_ACCEPTABLE

min(Mar 1, Feb 20) = Feb 20
But promise of Feb 20 is RISKY (can only guarantee Mar 1)
```

**Result**:
```json
{
  "status": "OK",
  "promise_date": "2026-02-20",  // Promised as requested
  "promise_date_raw": "2026-03-01",  // But really need this long
  "confidence": "LOW",  // Low confidence in Feb 20 deadline
  "on_time": false,  // Risk flagged
  "reasons": [
    "30u from stock (Stores - WH, Feb 7)",
    "25u from processing (Raw Materials - WH, Feb 8 after 1 day processing)",
    "30u from PO-001 (arriving Feb 18)",
    "15u from PO-002 (arriving Feb 25)",
    "Fulfillment completion: Feb 25"
  ],
  "blockers": [
    "PO-002 arrives on Feb 25 (5 days after desired date)",
    "Promising Feb 20 but need until Mar 1 - RISKY"
  ],
  "options": [{
    "option_type": "SPLIT_SHIPMENT",
    "description": "Ship 85u by Feb 20, backorder 15u until Mar 1"
  }, {
    "option_type": "DESIRED_DATE_EXTENSION",
    "description": "Extend to Mar 1 for full order",
    "gap_days": 9
  }]
}
```

---

## Summary

The OTP promise calculation algorithm is:

1. **Deterministic**: Same input always produces same output
2. **Data-driven**: Backed by real inventory and PO data
3. **Explainable**: Every decision is justified with reasons
4. **Business-aware**: Respects calendars, lead times, and constraints
5. **Resilient**: Handles edge cases gracefully
6. **Transparent**: Provides confidence levels and options

This algorithm ensures **reliable promises that customers can count on**.
