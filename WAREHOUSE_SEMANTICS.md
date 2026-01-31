# Order Promise Engine (OTP) — Real-World Warehouse Semantics

## Core Principle

Warehouses are not just locations; they represent **operational inventory stages**. Companies physically move inventory between stages (Raw Materials → WIP → Finished Goods → Stores → Customer). OTP must respect warehouse stages to prevent false delivery promises.

---

## Warehouse Classification & Availability Rules

### STORES (SELLABLE / Ship-Ready)
**Examples:** `Stores - SD`, `Warehouse - Main`, `Ship-Ready Inventory`

**Semantics:**
- Stock is physically ready for customer shipment NOW
- No additional processing required
- Counts as **available immediately** at base_date

**OTP Behavior:**
- Use stock quantity directly for fulfillment
- Ship-ready date = base_date + processing_lead_time (working days only)
- Example: 100 units in Stores on Monday 2026-01-27 → ship-ready Wednesday 2026-01-29 (with 1-day buffer, no weekends)

**Confidence:** HIGH (if stock exists and is confirmed)

---

### FINISHED_GOODS (Processing Required)
**Examples:** `Finished Goods - SD`, `QA Inventory`, `Packing Station`

**Semantics:**
- Stock exists but requires ADDITIONAL processing (QA, labeling, packaging, carrier booking)
- Processing is internal warehouse operation; time is deterministic but longer than STORES
- Counts as available BUT requires extra lead time before becoming ship-ready

**OTP Behavior:**
- Use stock quantity for fulfillment
- Ship-ready date = base_date + processing_lead_time + extra_processing_lead_time (working days only)
- Extra processing time accounts for: QA (0.5 days), packing (0.5 days), labeling (0.25 days), carrier booking (0.25 days) ≈ 1 day
- Example: 50 units in Finished Goods on Monday → ship-ready Thursday (1 base + 1 extra + 1 buffer = 3 days)

**Confidence:** HIGH (if stock confirmed) or MEDIUM (if requires QA sign-off)

---

### GOODS_IN_TRANSIT (Future Supply Only)
**Examples:** `Goods In Transit - SD`, `In Transit - SD`, `Receiving - Transit`

**Semantics:**
- Stock physically exists but is en route; NOT at the fulfillment warehouse
- Becomes usable ONLY on the expected receipt date (from Purchase Order or Goods Receipt)
- Must NOT be counted as available stock today
- Must be converted to future supply events with firm ETAs

**OTP Behavior:**
- **DO NOT** include in available_now calculation
- Fetch incoming supply from Purchase Orders/Purchase Receipts with schedule dates
- Only promise fulfillment if:
  1. PO exists (is submitted)
  2. Receipt date is accessible (not forbidden by permissions)
  3. Receipt date + lead time ≤ desired_date (if desired_date provided)
- If PO data is inaccessible (403 permission denied):
  - Mark supply as UNKNOWN
  - Set confidence to LOW
  - Return blocker: "PO data unavailable; cannot reliably promise stock in transit"
  - Set promise_date = null

**Example Scenarios:**

*Scenario A: 100 units in Goods In Transit, PO receipt scheduled 2026-02-03 (Tuesday)*
- Order requested: Friday 2026-01-31
- OTP result: CANNOT_FULFILL (receipt after desired date)
- Reason: "Goods In Transit quantity not available until 2026-02-03 (Monday); promise date would be 2026-02-04 (Tuesday)"

*Scenario B: 100 units in Goods In Transit, PO receipt scheduled 2026-01-28 (Tuesday)*
- Order requested: Friday 2026-01-31, quantity 50
- OTP result: CAN_FULFILL (receipt before desired date, qty sufficient)
- Plan: "50 units from incoming supply → 2026-01-28 (receipt, Tuesday) + 1-day buffer = ship-ready 2026-01-29 (Wednesday)"

*Scenario C: PO fetch returns HTTP 403 (permission denied)*
- Order requested, stock only in Goods In Transit
- OTP result: CANNOT_PROMISE_RELIABLY
- Promise date: null
- Reason: "Goods In Transit quantity requires PO data; access forbidden (permission denied). Cannot promise reliably without ETA confirmation."

**Confidence:** MEDIUM (if PO exists and ETA confirmed) or LOW (if PO access forbidden)

---

### WORK_IN_PROGRESS (NOT SELLABLE)
**Examples:** `WIP - SD`, `Work In Progress - SD`, `Manufacturing - SD`, `Assembly Line`

**Semantics:**
- Stock exists but is NOT yet finished; still undergoing manufacturing/assembly
- Cannot promise to customer without explicit manufacturing completion ETA
- Should be ignored for customer fulfillment unless production lead time is explicitly configured (out of scope for MVP)

**OTP Behavior:**
- **Completely ignore** WIP stock in fulfillment calculations
- Do NOT include in available_now or future_qty
- Log reason: "WIP inventory ignored; not available for customer promise without explicit production ETA"

**Confidence:** N/A (not used)

---

### GROUP (Logical Container)
**Examples:** `All Warehouses - SD`, `All Stores`, `Group Warehouse`

**Semantics:**
- Not a physical location; represents a hierarchy/group of child warehouses
- Used for reporting and hierarchy navigation, not for direct stock allocation
- Must be expanded to child warehouses before any allocation

**OTP Behavior:**
- Detect Group warehouse type from classification
- If selected, expand to child warehouses (e.g., `All Warehouses - SD` → `[Stores - SD, Finished Goods - SD, Goods In Transit - SD, WIP - SD]`)
- Allocate per child warehouse type (STORES first, FINISHED_GOODS second, etc.)
- Prevent double-counting (if 100 units in Stores and 50 in Finished Goods, total available now = 100, not 150)
- Log: "Group warehouse expanded into children: [Stores - SD, Finished Goods - SD, ...]. Allocated per warehouse type."

**Confidence:** Depends on children

---

## Allocation Algorithm

### Step 1: Classify Warehouse(s)
- If Group → expand to children
- For each child, determine type: STORES, FINISHED_GOODS, GOODS_IN_TRANSIT, WIP

### Step 2: Allocate in Priority Order
1. **STORES (available now, no extra processing):**
   - Use quantity directly
   - Ship-ready date = base_date + processing_lead_time

2. **FINISHED_GOODS (available now, add processing):**
   - Use quantity if base_date + processing_lead_time + extra_processing ≤ earliest_deadline
   - Ship-ready date = base_date + processing_lead_time + extra_processing

3. **GOODS_IN_TRANSIT (future supply, if PO accessible):**
   - Fetch incoming POs/receipts
   - If no PO exists: cannot fulfill from this warehouse now (but may fulfill from STORES/FG)
   - If PO exists and receipt_date + lead_time ≤ desired_date: use it
   - If receipt_date + lead_time > desired_date: too late
   - If PO access forbidden (403): mark as UNKNOWN, degrade confidence

4. **WIP (not sellable):**
   - Skip; log reason

### Step 3: Calculate Promise Date
- If quantity is zero → CANNOT_FULFILL, promise_date = null
- If quantity > 0:
  - Base date = today (or next working day if today is Fri/Sat)
  - Promise date = max(ship-ready dates across fulfillment sources)
  - If promise_date is Fri or Sat → adjust to next Sunday (working day)

### Step 4: Determine Status & Confidence
- **CAN_FULFILL:**
  - Status: all required quantity allocated from available or incoming stock
  - Confidence: HIGH (all from STORES) | MEDIUM (includes FINISHED_GOODS or PO) | LOW (depends on PO + access issues)
  - Promise date: date when all items ship-ready

- **CANNOT_FULFILL:**
  - Status: insufficient stock + incoming supply even with full allocation
  - Promise date: null
  - Reason: "Shortage of X units; only Y available in [warehouse list]"

- **CANNOT_PROMISE_RELIABLY:**
  - Status: fulfillment depends on inaccessible PO data
  - Promise date: null
  - Reason: "Fulfillment depends on Goods In Transit; PO data unavailable (permission denied)"

---

## Calendar Rules

All dates must be **business-calendar aware** using a **Sunday–Thursday workweek** (Friday–Saturday weekends):

### Date Adjustments
1. **Base date (today):**
   - If today is Friday or Saturday → advance to next Sunday
   - Example: Friday 2026-01-31 → base_date = Sunday 2026-02-02

2. **Adding lead time:**
   - Add only working days; skip Fri–Sat
   - Example: Thursday 2026-01-30 + 2 working days = Monday 2026-02-02 (skips Fri, Sat, Sun)

3. **Final promise date:**
   - If promise_date is Fri or Sat → adjust to next Sunday
   - Example: Friday 2026-01-31 → adjusted to Sunday 2026-02-02

### Examples
- Order placed: Friday 2026-01-31
  - Base date → Sunday 2026-02-02
  - +1 processing day → Monday 2026-02-03
  - +1 buffer day → Tuesday 2026-02-04
  - Promise date = Tuesday 2026-02-04 (working day) ✅

- Order placed: Thursday 2026-01-30
  - Base date → Thursday 2026-01-30
  - +2 working days → Monday 2026-02-02
  - Promise date = Monday 2026-02-02 (working day) ✅

---

## Error Handling & Permissions

### Case: PO Access Forbidden (HTTP 403)

**Trigger:** User lacks permission to read Purchase Orders

**OTP Response:**
```json
{
  "can_fulfill": false,
  "promise_date": null,
  "confidence": "LOW",
  "blockers": [
    "Fulfillment depends on Goods In Transit; PO data unavailable (permission denied)"
  ],
  "reasons": [
    "Stock found: 100 units in Goods In Transit - SD",
    "Incoming supply: Access forbidden (permission error 403)",
    "Cannot reliably promise without confirmed receipt dates"
  ]
}
```

### Case: PO Access Timeout

**Trigger:** PO API timeout

**OTP Response:**
```json
{
  "can_fulfill": false,
  "promise_date": null,
  "confidence": "LOW",
  "blockers": [
    "Incoming supply lookup timed out; cannot confirm in-transit stock receipt date"
  ]
}
```

### Case: Goods In Transit with Known ETA

**Trigger:** PO exists, receipt scheduled for 2026-02-03 (Tuesday)

**OTP Response:**
```json
{
  "can_fulfill": true,
  "promise_date": "2026-02-04",
  "confidence": "MEDIUM",
  "plan": [
    {
      "source": "incoming_supply",
      "qty": 50,
      "available_date": "2026-02-03",
      "ship_ready_date": "2026-02-04",
      "po_id": "PO-2026-00123"
    }
  ],
  "reasons": [
    "Item: 50 units from Purchase Order PO-2026-00123",
    "Receipt date: 2026-02-03 (Tuesday, working day)",
    "Added 1 day(s) lead time buffer",
    "Promise date: 2026-02-04 (Wednesday, working day)"
  ]
}
```

---

## Output Format: Transparency

Every response MUST include:

### Physical Inventory Summary
```json
{
  "physical_qty": {
    "stores": 100,
    "finished_goods": 50,
    "goods_in_transit": 75,
    "wip": 200,
    "total_physical": 425
  },
  "usable_now_qty": 150,  // stores + finished goods
  "future_qty": [
    {
      "source": "PO-2026-00123",
      "qty": 75,
      "available_date": "2026-02-03"
    }
  ]
}
```

### Warehouse Allocation Details
```json
{
  "allocation": [
    {
      "warehouse": "Stores - SD",
      "type": "STORES",
      "qty_available": 100,
      "qty_used": 50,
      "ship_ready_date": "2026-01-29"
    },
    {
      "warehouse": "Finished Goods - SD",
      "type": "FINISHED_GOODS",
      "qty_available": 50,
      "qty_used": 50,
      "ship_ready_date": "2026-01-30"
    },
    {
      "warehouse": "Goods In Transit - SD",
      "type": "GOODS_IN_TRANSIT",
      "qty_available": 0,  // not counted as available now
      "qty_used": 0,
      "reason": "Not ship-ready; awaiting receipt"
    }
  ]
}
```

---

## Test Cases (MANDATORY)

1. **Stock only in STORES**
   - Input: 50 units in Stores - SD, order qty 50, no desired_date
   - Expected: CAN_FULFILL, promise_date = Wednesday (base + 1 buffer), confidence HIGH

2. **Stock only in FINISHED_GOODS**
   - Input: 50 units in FG - SD, order qty 50, no desired_date
   - Expected: CAN_FULFILL, promise_date = Thursday (base + 1 FG processing + 1 buffer), confidence HIGH

3. **Stock only in GOODS_IN_TRANSIT with known ETA**
   - Input: 50 units in GIT - SD, PO receipt = 2026-02-03, order qty 50, desired_date = 2026-02-05
   - Expected: CAN_FULFILL, promise_date = 2026-02-04 (receipt + buffer), confidence MEDIUM

4. **Stock only in GOODS_IN_TRANSIT, PO forbidden (403)**
   - Input: 50 units in GIT - SD, PO access = 403 forbidden, order qty 50
   - Expected: CANNOT_PROMISE_RELIABLY, promise_date = null, confidence LOW, blocker = "PO data unavailable"

5. **Stock only in WIP**
   - Input: 50 units in WIP - SD, order qty 50
   - Expected: CANNOT_FULFILL, promise_date = null, reason = "WIP stock ignored"

6. **Group warehouse selection**
   - Input: warehouse = "All Warehouses - SD", stock = [100 Stores, 50 FG, 75 GIT], order qty 100
   - Expected: Expand group → allocate Stores (100) → CAN_FULFILL, promise_date = Wednesday

7. **Promise date adjustment for weekends**
   - Input: base_date = Friday 2026-01-31, qty available, no buffer
   - Expected: base_date adjusted to Sunday 2026-02-02; promise_date = working day (not Fri/Sat)

8. **Multiple warehouses, mixed availability**
   - Input: 30 Stores + 50 FG + 40 GIT (receipt 2026-02-03), order qty 100
   - Expected: CAN_FULFILL, plan = [30 from Stores + 50 from FG + 20 from GIT], promise_date = max ship-ready date

9. **Permission error with fallback to STORES**
   - Input: 50 Stores + 50 GIT (PO access 403), order qty 75
   - Expected: CAN_FULFILL (from Stores), confidence HIGH, blocker note for GIT access issue

10. **Insufficient stock across all warehouses**
    - Input: 30 Stores + 20 FG + 30 GIT (inaccessible), order qty 100
    - Expected: CANNOT_FULFILL, promise_date = null, shortage = 20 units

---

## Implementation Checklist

- [ ] Warehouse classification: STORES, FINISHED_GOODS, GOODS_IN_TRANSIT, WIP, GROUP
- [ ] Allocation priority: STORES first, then FG, then GIT (if PO accessible)
- [ ] Calendar rules: base_date adjustment, working-day-only lead time, weekend date adjustment
- [ ] Permission error handling: 403 → mark as UNKNOWN, degrade confidence, return explicit blocker
- [ ] Promise date: nullable (null for CANNOT_FULFILL or CANNOT_PROMISE_RELIABLY)
- [ ] Output: physical_qty, usable_now_qty, future_qty, allocation details
- [ ] Tests: all 10 scenarios above passing
- [ ] Documentation: clear explanation per warehouse type and allocation rules

---

**Key Principle:** If you can't confirm fulfillment (due to missing PO, permission error, or insufficient stock), return `promise_date = null` and a clear blocker message. Better to say "I don't know" than to lie with a false promise date.
