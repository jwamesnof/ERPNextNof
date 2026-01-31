# Frontend Integration Specification: ERPNext OTP Service

**Generated**: January 29, 2026  
**Backend Version**: 0.1.0  
**Purpose**: Complete API contract for frontend integration with Order-to-Promise (OTP) backend service

---

## 📋 Table of Contents

1. [Service Overview](#service-overview)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [Local Development Setup](#local-development-setup)
4. [CORS & Network Configuration](#cors--network-configuration)
5. [API Endpoints (Full Contracts)](#api-endpoints-full-contracts)
6. [Data Types & Enums](#data-types--enums)
7. [Error Handling Semantics](#error-handling-semantics)
8. [Frontend Implementation Guide](#frontend-implementation-guide)
9. [Testing Strategy](#testing-strategy)
10. [Backend Files Inspected](#backend-files-inspected)

---

## Service Overview

### What This Backend Provides

The **OTP (Order-to-Promise) Service** is a FastAPI backend that calculates realistic order delivery promises based on:
- **Real-time stock availability** from ERPNext
- **Incoming Purchase Orders** with ETAs
- **Warehouse processing times** (picking, packing, QA)
- **Business rules** (working days, lead time buffers, cutoff times)

### Core Capabilities

1. **Promise Calculation** (`POST /otp/promise`)
   - Input: Customer + Items + Desired Date + Rules
   - Output: Promise date, confidence, fulfillment plan, alternatives

2. **Promise Application** (`POST /otp/apply`)
   - Writes calculated promise back to ERPNext Sales Order
   - Adds comments and updates custom fields

3. **Procurement Suggestions** (`POST /otp/procurement-suggest`)
   - Generates Material Requests for items with shortages

4. **Health Check** (`GET /health`)
   - Service status + ERPNext connectivity verification

---

## Architecture & Data Flow

### ⚠️ CRITICAL RULE: UI → Backend → ERPNext ONLY

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│   Frontend  │─────>│ OTP Backend  │─────>│   ERPNext    │
│  (Next.js)  │<─────│  (FastAPI)   │<─────│   (Frappe)   │
└─────────────┘      └──────────────┘      └──────────────┘
    React UI          Python Service       ERP Database
```

**DO NOT**:
- ❌ Frontend calls ERPNext API directly
- ❌ Frontend stores ERPNext API keys
- ❌ Frontend implements business logic

**DO**:
- ✅ All ERP queries go through OTP backend
- ✅ Frontend only knows about OTP API contracts
- ✅ Backend handles authentication, permissions, business rules

---

## Local Development Setup

### 1. Start Backend Server

```bash
# Navigate to backend repo
cd /path/to/ERPNextNof

# Activate Python virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Install dependencies (if not done)
pip install -r requirements.txt

# Start FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

### 2. Verify Backend is Running

```bash
# Health check
curl http://localhost:8001/health

# API documentation (Swagger UI)
open http://localhost:8001/docs

# ReDoc (alternative docs)
open http://localhost:8001/redoc
```

### 3. Required Environment Variables

Backend requires `.env` file with:

```env
# ERPNext Connection (backend handles this, frontend NEVER accesses)
ERPNEXT_BASE_URL=http://localhost:8080
ERPNEXT_API_KEY=<secret>
ERPNEXT_API_SECRET=<secret>

# OTP Service Configuration
OTP_SERVICE_HOST=0.0.0.0
OTP_SERVICE_PORT=8001
OTP_SERVICE_ENV=development

# Mock Mode (for frontend development without ERPNext)
USE_MOCK_SUPPLY=true              # Set to 'false' for real ERPNext data
MOCK_DATA_FILE=data/Sales Invoice.csv

# Business Rules
NO_WEEKENDS=true                  # Sunday-Thursday workweek
CUTOFF_TIME=14:00
LEAD_TIME_BUFFER_DAYS=1
```

### 4. Frontend Environment Variables

Create `.env.local` in your Next.js project:

```env
# OTP Backend API URL
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001

# Development Mode Features
NEXT_PUBLIC_ENABLE_MOCK_MODE=true
NEXT_PUBLIC_SHOW_DEBUG_INFO=true
```

---

## CORS & Network Configuration

### Current CORS Setup

✅ **CORS is ENABLED** in backend (`src/main.py` lines 26-32):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permissive for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Allowed Origins

- **Development**: `http://localhost:3000` (Next.js default)
- **Development**: `http://localhost:3001` (alternative port)
- **Current config**: `*` (all origins - change for production)

### Production CORS Configuration

⚠️ For production deployment, update `src/main.py`:

```python
allow_origins=[
    "https://your-frontend-domain.com",
    "https://www.your-frontend-domain.com"
],
```

### Network Notes

- Backend runs on port **8001** (not 8000)
- ERPNext runs on port **8080**
- Frontend typically on port **3000**
- All cross-origin requests include credentials

---

## API Endpoints (Full Contracts)

### Base URL

```
http://localhost:8001
```

All endpoints return JSON. All dates use ISO 8601 format (`YYYY-MM-DD`).

---

### 1. Calculate Promise Date

**Endpoint**: `POST /otp/promise`  
**Purpose**: Calculate delivery promise for a draft order  
**Authentication**: None required (backend handles ERPNext auth)

#### Request Schema

```typescript
interface PromiseRequest {
  customer: string;              // Customer name or ID
  items: ItemRequest[];          // Min 1 item required
  desired_date?: string;         // ISO date (YYYY-MM-DD), optional
  rules?: PromiseRules;          // Optional, uses defaults if omitted
}

interface ItemRequest {
  item_code: string;             // ERPNext item code (e.g., "SKU005")
  qty: number;                   // Quantity > 0
  warehouse?: string;            // Optional, defaults to "Stores - SD"
}

interface PromiseRules {
  no_weekends?: boolean;         // Default: true (Sun-Thu workweek)
  cutoff_time?: string;          // Default: "14:00" (HH:MM format)
  timezone?: string;             // Default: "UTC"
  lead_time_buffer_days?: number; // Default: 1
  processing_lead_time_days?: number; // Default: 1
  desired_date_mode?: "LATEST_ACCEPTABLE" | "STRICT_FAIL" | "NO_EARLY_DELIVERY";
}
```

#### Example Request

```json
{
  "customer": "Palmer Productions Ltd.",
  "items": [
    {
      "item_code": "SKU005",
      "qty": 50,
      "warehouse": "Stores - SD"
    },
    {
      "item_code": "SKU008",
      "qty": 10
    }
  ],
  "desired_date": "2026-03-10",
  "rules": {
    "no_weekends": true,
    "lead_time_buffer_days": 1,
    "desired_date_mode": "LATEST_ACCEPTABLE"
  }
}
```

#### Response Schema

```typescript
interface PromiseResponse {
  status: "OK" | "CANNOT_FULFILL" | "CANNOT_PROMISE_RELIABLY";
  promise_date: string | null;      // ISO date or null if CANNOT_FULFILL
  promise_date_raw: string | null;  // Before desired_date adjustments
  desired_date: string | null;      // Echoed from request
  desired_date_mode: string | null; // Mode used
  on_time: boolean | null;          // True if promise <= desired
  adjusted_due_to_no_early_delivery: boolean;
  can_fulfill: boolean;             // True if all items allocatable
  confidence: "HIGH" | "MEDIUM" | "LOW";
  plan: ItemPlan[];                 // Per-item fulfillment details
  reasons: string[];                // Calculation explanations
  blockers: string[];               // Issues preventing optimal promise
  options: PromiseOption[];         // Suggestions to improve promise
}

interface ItemPlan {
  item_code: string;
  qty_required: number;
  fulfillment: FulfillmentSource[];
  shortage: number;                 // Unfulfilled quantity
}

interface FulfillmentSource {
  source: "stock" | "purchase_order" | "production";
  qty: number;
  available_date: string;           // ISO date
  ship_ready_date: string;          // available_date + processing time
  warehouse: string | null;
  po_id: string | null;             // If source=purchase_order
  expected_date: string | null;     // For POs
}

interface PromiseOption {
  type: string;                     // "alternate_warehouse", "expedite_po", etc.
  description: string;
  impact: string;                   // Impact description
  po_id: string | null;
}
```

#### Example Response (Success)

```json
{
  "status": "OK",
  "promise_date": "2026-02-01",
  "promise_date_raw": "2026-02-01",
  "desired_date": "2026-03-10",
  "desired_date_mode": "LATEST_ACCEPTABLE",
  "on_time": true,
  "adjusted_due_to_no_early_delivery": false,
  "can_fulfill": true,
  "confidence": "HIGH",
  "plan": [
    {
      "item_code": "SKU005",
      "qty_required": 50.0,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 50.0,
          "available_date": "2026-01-29",
          "ship_ready_date": "2026-01-29",
          "warehouse": "Stores - SD",
          "po_id": null,
          "expected_date": null
        }
      ],
      "shortage": 0.0
    }
  ],
  "reasons": [
    "50.0 units from Stores - SD (ready to ship)",
    "Added 1 day(s) lead time buffer",
    "Adjusted from 2026-01-29 to 2026-02-01 (business rules applied)",
    "Weekend delivery avoided (Friday-Saturday excluded)"
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
      "item_code": "SKU005",
      "qty_required": 500.0,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 165.0,
          "available_date": "2026-01-29",
          "ship_ready_date": "2026-01-29",
          "warehouse": "Stores - SD",
          "po_id": null,
          "expected_date": null
        }
      ],
      "shortage": 335.0
    }
  ],
  "reasons": [],
  "blockers": [
    "Item SKU005: Shortage of 335.0 units"
  ],
  "options": [
    {
      "type": "alternate_warehouse",
      "description": "Check alternate warehouses for SKU005",
      "impact": "Could reduce promise date if stock available elsewhere",
      "po_id": null
    }
  ]
}
```

#### Error Responses

**422 Validation Error**:
```json
{
  "detail": [
    {
      "loc": ["body", "items", 0, "qty"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt"
    }
  ]
}
```

**503 Service Unavailable** (ERPNext down):
```json
{
  "detail": "ERPNext service error: Connection refused"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Internal error: <description>"
}
```

---

### 2. Apply Promise to Sales Order

**Endpoint**: `POST /otp/apply`  
**Purpose**: Write calculated promise back to ERPNext Sales Order  
**Authentication**: None required (backend handles ERPNext auth)

#### Request Schema

```typescript
interface ApplyPromiseRequest {
  sales_order_id: string;        // ERPNext SO ID (e.g., "SAL-ORD-2026-00015")
  promise_date: string;          // ISO date
  confidence: "HIGH" | "MEDIUM" | "LOW";
  action?: "add_comment" | "set_custom_field" | "both"; // Default: "both"
  comment_text?: string;         // Optional custom comment
}
```

#### Example Request

```json
{
  "sales_order_id": "SAL-ORD-2026-00015",
  "promise_date": "2026-02-01",
  "confidence": "HIGH",
  "action": "both",
  "comment_text": "Promise calculated by OTP system with HIGH confidence"
}
```

#### Response Schema

```typescript
interface ApplyPromiseResponse {
  status: "success" | "error";
  sales_order_id: string;
  actions_taken: string[];       // List of actions performed
  erpnext_response: object | null;
  error: string | null;
}
```

#### Example Response (Success)

```json
{
  "status": "success",
  "sales_order_id": "SAL-ORD-2026-00015",
  "actions_taken": [
    "Added comment to Sales Order",
    "Updated custom_promise_date field"
  ],
  "erpnext_response": {
    "message": "Comment added successfully"
  },
  "error": null
}
```

#### Example Response (Error)

```json
{
  "status": "error",
  "sales_order_id": "SAL-ORD-2026-00015",
  "actions_taken": [],
  "erpnext_response": null,
  "error": "Sales Order not found or permission denied"
}
```

---

### 3. Create Procurement Suggestion

**Endpoint**: `POST /otp/procurement-suggest`  
**Purpose**: Generate Material Request in ERPNext for items with shortages  
**Authentication**: None required

#### Request Schema

```typescript
interface ProcurementSuggestionRequest {
  items: ProcurementItem[];      // Min 1 item
  suggestion_type?: "material_request" | "draft_po" | "task"; // Default: "material_request"
  priority?: "HIGH" | "MEDIUM" | "LOW"; // Default: "MEDIUM"
}

interface ProcurementItem {
  item_code: string;
  qty_needed: number;            // > 0
  required_by: string;           // ISO date
  reason: string;
}
```

#### Example Request

```json
{
  "items": [
    {
      "item_code": "SKU005",
      "qty_needed": 335.0,
      "required_by": "2026-02-15",
      "reason": "Shortage for Sales Order SAL-ORD-2026-00015"
    }
  ],
  "suggestion_type": "material_request",
  "priority": "HIGH"
}
```

#### Response Schema

```typescript
interface ProcurementSuggestionResponse {
  status: "success" | "error";
  suggestion_id: string;         // Created doc ID in ERPNext
  type: string;                  // Doc type created
  items_count: number;
  erpnext_url: string;           // Link to view in ERPNext
  error: string | null;
}
```

#### Example Response

```json
{
  "status": "success",
  "suggestion_id": "MAT-REQ-2026-00042",
  "type": "Material Request",
  "items_count": 1,
  "erpnext_url": "http://localhost:8080/app/material-request/MAT-REQ-2026-00042",
  "error": null
}
```

---

### 4. Health Check

**Endpoint**: `GET /health`  
**Purpose**: Verify service status and ERPNext connectivity  
**Authentication**: None required

#### Response Schema

```typescript
interface HealthResponse {
  status: "healthy" | "degraded";
  version: string;
  erpnext_connected: boolean;
  message: string | null;
}
```

#### Example Response

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": true,
  "message": "All systems operational"
}
```

---

### 5. ⚠️ MISSING ENDPOINT: Sales Order List

**Status**: **NOT IMPLEMENTED in API routes**

The backend has the **capability** (`ERPNextClient.get_sales_order_list()`) but **no exposed REST endpoint** yet.

#### What Frontend Needs

```typescript
GET /otp/sales-orders?limit=20&customer=<name>
```

#### Recommended Frontend Behavior

**Option A**: Request backend to add this endpoint (minimal change):

```python
# Add to src/routes/otp.py
@router.get("/sales-orders")
async def get_sales_orders(
    limit: int = 20,
    customer: Optional[str] = None,
    client: ERPNextClient = Depends(get_erpnext_client)
):
    filters = []
    if customer:
        filters.append(["customer", "=", customer])
    
    return client.get_sales_order_list(
        filters=filters,
        limit=limit,
        order_by="name desc"
    )
```

**Option B**: Use mock data for dropdown in development:

```typescript
const MOCK_SALES_ORDERS = [
  { name: "SAL-ORD-2026-00015", customer: "Palmer Productions Ltd.", delivery_date: "2026-02-13" },
  { name: "SAL-ORD-2026-00014", customer: "West View Software Ltd.", delivery_date: "2026-03-15" }
];
```

---

## Data Types & Enums

### Status Values

```typescript
type PromiseStatus = "OK" | "CANNOT_FULFILL" | "CANNOT_PROMISE_RELIABLY";
```

- **OK**: Promise calculated successfully, all items allocatable
- **CANNOT_FULFILL**: Insufficient stock/supply to meet demand
- **CANNOT_PROMISE_RELIABLY**: Missing critical data (e.g., PO access denied)

### Confidence Levels

```typescript
type Confidence = "HIGH" | "MEDIUM" | "LOW";
```

- **HIGH**: Full data access, no shortages, PO data available
- **MEDIUM**: Some limitations (e.g., partial supply data)
- **LOW**: Significant blockers (e.g., permission denied, large shortage)

### Desired Date Modes

```typescript
type DesiredDateMode = 
  | "LATEST_ACCEPTABLE"    // Default: allow early delivery
  | "STRICT_FAIL"          // Fail if promise > desired
  | "NO_EARLY_DELIVERY";   // Delay promise to match desired if early
```

### Fulfillment Source Types

```typescript
type SourceType = "stock" | "purchase_order" | "production";
```

### Option Types

```typescript
type OptionType = 
  | "alternate_warehouse" 
  | "expedite_po" 
  | "split_shipment"
  | "backorder";
```

### Action Types (Apply Endpoint)

```typescript
type ApplyAction = "add_comment" | "set_custom_field" | "both";
```

### Priority Levels (Procurement)

```typescript
type Priority = "HIGH" | "MEDIUM" | "LOW";
```

---

## Error Handling Semantics

### HTTP Status Codes

| Code | Meaning | Cause | Frontend Action |
|------|---------|-------|-----------------|
| **200** | Success | Normal response | Display results |
| **422** | Validation Error | Invalid request body | Show field errors |
| **500** | Internal Error | Backend bug | Show generic error + retry |
| **503** | Service Unavailable | ERPNext down | Show "service degraded" + enable mock mode |

### Business Logic "Errors" (Not HTTP Errors)

These return **200 OK** but with `status` field indicating issue:

#### CANNOT_FULFILL

```json
{
  "status": "CANNOT_FULFILL",
  "promise_date": null,
  "can_fulfill": false,
  "confidence": "LOW",
  "blockers": ["Item SKU005: Shortage of 335.0 units"]
}
```

**Frontend should**:
- Show **warning banner** (not error)
- Display shortage amount
- Show `options` array with alternatives
- Allow user to adjust quantity or items

#### CANNOT_PROMISE_RELIABLY

```json
{
  "status": "CANNOT_PROMISE_RELIABLY",
  "promise_date": "2026-02-05",
  "can_fulfill": true,
  "confidence": "LOW",
  "blockers": ["Permission denied (403) - cannot access PO data"]
}
```

**Frontend should**:
- Show **info banner** "Promise calculated with limited data"
- Display promise date with disclaimer
- Show confidence badge ("LOW")

#### STRICT_FAIL Mode Violation

When `desired_date_mode: "STRICT_FAIL"` and promise > desired:

```json
{
  "detail": "Cannot meet desired delivery date 2026-02-01. Earliest possible promise: 2026-02-05 (4 days late)."
}
```

**Returns**: **400 Bad Request**

**Frontend should**:
- Show **error modal** with detailed message
- Suggest user to adjust desired date or reduce quantities
- Provide link to re-run with `LATEST_ACCEPTABLE` mode

### Permission Errors (PO Access)

Backend handles gracefully, degrades confidence:

```json
{
  "status": "OK",
  "confidence": "MEDIUM",
  "blockers": ["Purchase Order data unavailable due to permissions"]
}
```

**Frontend**: Show "Calculated without PO data" badge.

---

## Frontend Implementation Guide

### 1. Create TypeScript API Client

**File**: `lib/api/otpClient.ts`

```typescript
import axios, { AxiosError, AxiosInstance } from 'axios';

// Types (copy from above or generate from OpenAPI)
export interface PromiseRequest { /* ... */ }
export interface PromiseResponse { /* ... */ }
// ... other types

class OTPApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001') {
    this.client = axios.create({
      baseURL,
      timeout: 30000, // 30s for promise calculations
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true, // CORS credentials
    });
  }

  async calculatePromise(request: PromiseRequest): Promise<PromiseResponse> {
    const response = await this.client.post<PromiseResponse>('/otp/promise', request);
    return response.data;
  }

  async applyPromise(request: ApplyPromiseRequest): Promise<ApplyPromiseResponse> {
    const response = await this.client.post<ApplyPromiseResponse>('/otp/apply', request);
    return response.data;
  }

  async healthCheck(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/health');
    return response.data;
  }

  // Add other methods...
}

export const otpApi = new OTPApiClient();
```

### 2. Add React Query Hooks

**File**: `hooks/usePromiseCalculation.ts`

```typescript
import { useMutation, useQuery } from '@tanstack/react-query';
import { otpApi, PromiseRequest, PromiseResponse } from '@/lib/api/otpClient';

export function usePromiseCalculation() {
  return useMutation<PromiseResponse, Error, PromiseRequest>({
    mutationFn: (request) => otpApi.calculatePromise(request),
    onError: (error) => {
      console.error('Promise calculation failed:', error);
    },
  });
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => otpApi.healthCheck(),
    refetchInterval: 60000, // Check every minute
  });
}
```

### 3. Map Backend Status to UI State

```typescript
type UIState = 'success' | 'warning' | 'error' | 'info';

function getUIState(response: PromiseResponse): UIState {
  switch (response.status) {
    case 'OK':
      return response.confidence === 'HIGH' ? 'success' : 'warning';
    case 'CANNOT_FULFILL':
      return 'warning'; // Not error - user can adjust
    case 'CANNOT_PROMISE_RELIABLY':
      return 'info';
    default:
      return 'error';
  }
}

function getConfidenceBadgeColor(confidence: string): string {
  switch (confidence) {
    case 'HIGH': return 'green';
    case 'MEDIUM': return 'yellow';
    case 'LOW': return 'red';
    default: return 'gray';
  }
}
```

### 4. Mock Mode for Development

When backend is unavailable:

```typescript
// lib/api/mockOtpClient.ts
export class MockOTPClient {
  async calculatePromise(request: PromiseRequest): Promise<PromiseResponse> {
    await new Promise(resolve => setTimeout(resolve, 500)); // Simulate delay
    
    return {
      status: 'OK',
      promise_date: '2026-02-01',
      promise_date_raw: '2026-02-01',
      desired_date: request.desired_date,
      on_time: true,
      can_fulfill: true,
      confidence: 'HIGH',
      plan: request.items.map(item => ({
        item_code: item.item_code,
        qty_required: item.qty,
        fulfillment: [{
          source: 'stock',
          qty: item.qty,
          available_date: '2026-01-29',
          ship_ready_date: '2026-01-29',
          warehouse: 'Stores - SD',
          po_id: null,
          expected_date: null,
        }],
        shortage: 0,
      })),
      reasons: ['Mock data - backend unavailable'],
      blockers: [],
      options: [],
      desired_date_mode: null,
      adjusted_due_to_no_early_delivery: false,
    };
  }
}

// Use in client
export const otpApi = process.env.NEXT_PUBLIC_ENABLE_MOCK_MODE === 'true'
  ? new MockOTPClient()
  : new OTPApiClient();
```

### 5. Error Boundary Component

```typescript
// components/PromiseErrorBoundary.tsx
export function PromiseErrorDisplay({ error }: { error: Error }) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 422) {
      return <ValidationErrorDisplay errors={error.response.data.detail} />;
    }
    if (error.response?.status === 503) {
      return (
        <Alert severity="warning">
          <AlertTitle>Backend Service Unavailable</AlertTitle>
          ERPNext connection lost. Enable mock mode or contact support.
        </Alert>
      );
    }
  }
  
  return (
    <Alert severity="error">
      <AlertTitle>Promise Calculation Failed</AlertTitle>
      {error.message}
    </Alert>
  );
}
```

---

## Testing Strategy

### Testability Hooks

Use `data-testid` attributes for E2E tests:

```tsx
<Button data-testid="calculate-promise-btn" onClick={handleCalculate}>
  Calculate Promise
</Button>

<div data-testid="promise-result">
  {response.status === 'OK' && (
    <span data-testid="promise-date">{response.promise_date}</span>
  )}
  {response.status === 'CANNOT_FULFILL' && (
    <span data-testid="shortage-warning">Insufficient Stock</span>
  )}
</div>
```

### Deterministic Test Cases

Use these requests for **consistent backend responses** (with mock data):

#### Test Case 1: Simple Fulfillable Order

```json
{
  "customer": "Test Customer",
  "items": [{ "item_code": "SKU005", "qty": 50 }]
}
```

**Expected**: `status: "OK"`, `confidence: "HIGH"`, `promise_date: "2026-02-01"`

#### Test Case 2: Multi-Item Order

```json
{
  "customer": "Test Customer",
  "items": [
    { "item_code": "SKU005", "qty": 20 },
    { "item_code": "SKU008", "qty": 10 }
  ],
  "desired_date": "2026-03-10"
}
```

**Expected**: `status: "OK"`, `on_time: true`

#### Test Case 3: Shortage Scenario

```json
{
  "customer": "Test Customer",
  "items": [{ "item_code": "SKU005", "qty": 500 }]
}
```

**Expected**: `status: "CANNOT_FULFILL"`, `promise_date: null`, `blockers: ["Shortage..."]`

### E2E Test Example (Playwright)

```typescript
test('Calculate promise for available stock', async ({ page }) => {
  await page.goto('/promise-calculator');
  
  await page.fill('[data-testid="customer-input"]', 'Test Customer');
  await page.fill('[data-testid="item-code-0"]', 'SKU005');
  await page.fill('[data-testid="qty-0"]', '50');
  
  await page.click('[data-testid="calculate-promise-btn"]');
  
  await expect(page.locator('[data-testid="promise-date"]')).toHaveText('2026-02-01');
  await expect(page.locator('[data-testid="confidence-badge"]')).toHaveText('HIGH');
});
```

---

## Backend Files Inspected

This specification was derived from:

### Core Application Files
- `src/main.py` (FastAPI app, CORS, health check)
- `src/config.py` (settings, environment variables)
- `.env` (configuration values)

### API Layer
- `src/routes/otp.py` (all OTP endpoints)
- `src/routes/demo_data.py` (demo/mock data endpoints)

### Data Models
- `src/models/request_models.py` (request schemas, enums)
- `src/models/response_models.py` (response schemas, enums)

### Business Logic
- `src/services/promise_service.py` (promise calculation logic)
- `src/services/stock_service.py` (stock queries)
- `src/services/apply_service.py` (Sales Order updates)

### ERPNext Integration
- `src/clients/erpnext_client.py` (ERPNext API wrapper, Sales Order methods)

### Controllers
- `src/controllers/otp_controller.py` (request orchestration)

---

## Summary Checklist for Frontend Team

- [x] Backend runs on **port 8001**
- [x] **CORS enabled** for `http://localhost:3000`
- [x] **3 main endpoints**: `/otp/promise`, `/otp/apply`, `/otp/procurement-suggest`
- [x] **Health check** at `/health`
- [x] **OpenAPI docs** at `/docs`
- [ ] **Sales Order list endpoint** - NOT IMPLEMENTED (use mock or request addition)
- [x] All dates use **ISO 8601** format
- [x] **Sunday-Thursday** workweek (Friday/Saturday are weekends)
- [x] **Status-based error handling** (not just HTTP codes)
- [x] **Mock mode available** via `USE_MOCK_SUPPLY=true` backend env var

---

## Quick Start Commands

```bash
# 1. Start backend
cd ERPNextNof && source .venv/bin/activate && uvicorn src.main:app --reload --port 8001

# 2. Verify backend
curl http://localhost:8001/health

# 3. Test promise calculation
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{"customer":"Test","items":[{"item_code":"SKU005","qty":50}]}'

# 4. View interactive docs
open http://localhost:8001/docs
```

---

**End of Specification**

This document contains everything needed to integrate with the OTP backend. For questions or missing endpoints, contact the backend team or file an issue in the backend repository.
