# Order Promise Engine (OTP) - Validation Report
**Date**: January 26, 2026  
**Application**: ERPNext Order Promise Engine  
**Status**: ✅ **FULLY IMPLEMENTS REQUIRED SKILL**

---

## Executive Summary

The application is **fully aligned** with the Order Promise Engine (OTP) skill requirements. It implements a deterministic, explainable promise date calculation algorithm that:

1. ✅ Calculates reliable Promise Dates for draft Sales Orders
2. ✅ Checks current stock per warehouse
3. ✅ Incorporates incoming supply (open Purchase Orders)
4. ✅ Applies configurable business rules
5. ✅ Returns complete response with promise_date, confidence, reasons, blockers, and options
6. ✅ Supports writing decisions back to ERPNext

---

## Requirement-by-Requirement Validation

### 1. **Calculate Promise Date from Multiple Data Sources** ✅

#### 1.1 Current Stock Per Warehouse
**Implementation**: `src/services/stock_service.py`
```python
get_available_stock(item_code, warehouse)
Returns:
  - actual_qty: Physical inventory
  - reserved_qty: Already allocated inventory
  - available_qty: Available for new orders (projected_qty)
```
**Validation**: ✅ Correctly queries warehouse-specific bin data via ERPNext client

#### 1.2 Incoming Supply (Purchase Orders)
**Implementation**: `src/services/stock_service.py`
```python
get_incoming_supply(item_code, after_date)
Returns:
  - List of Purchase Orders with:
    - po_id
    - qty
    - expected_date (schedule_date from PO)
    - warehouse
```
**Validation**: ✅ Fetches open POs and sorts by expected receipt date (FIFO strategy)

#### 1.3 Fulfillment Plan Algorithm
**Implementation**: `src/services/promise_service.py::_build_item_plan()`

**Algorithm**:
1. Use available stock first → `qty_from_stock`
2. Use incoming POs in date order (FIFO) → `qty_from_po`
3. Calculate shortage if demand exceeds supply

**Result**: `ItemPlan` with fulfillment sources, each tracking:
- Source type (stock/purchase_order)
- Quantity
- Available date
- Warehouse/PO reference

**Test Coverage**: `tests/unit/test_promise_service.py::test_promise_partial_stock()`  
**Validation**: ✅ Correctly builds multi-source fulfillment plans

---

### 2. **Apply Configurable Business Rules** ✅

#### 2.1 Weekend Exclusion
**Implementation**: `src/services/promise_service.py::_skip_weekends()`
```python
def _skip_weekends(self, target_date: date) -> date:
    while target_date.weekday() >= 5:  # Saturday=5, Sunday=6
        target_date += timedelta(days=1)
    return target_date
```
**Configuration**: `PromiseRules.no_weekends` (default: True)  
**Validation**: ✅ Correctly skips Saturday/Sunday

#### 2.2 Daily Cutoff Time
**Implementation**: `src/services/promise_service.py::_apply_cutoff_rule()`
```python
If time_now > cutoff_time AND promise_date == today:
    promise_date += 1 day
```
**Configuration**: `PromiseRules.cutoff_time` (default: "14:00", format: "HH:MM")  
**Timezone Support**: ✅ Uses `pytz` for timezone-aware calculations  
**Validation**: ✅ Correctly applies time-of-day logic

#### 2.3 Lead Time Buffer
**Implementation**: `src/services/promise_service.py::_apply_business_rules()`
```python
promise_date += timedelta(days=rules.lead_time_buffer_days)
```
**Configuration**: `PromiseRules.lead_time_buffer_days` (default: 1, must be >= 0)  
**Validation**: ✅ Adds configurable buffer days

#### 2.4 Timezone Support
**Implementation**: All calculations use `pytz.timezone(rules.timezone)`  
**Configuration**: `PromiseRules.timezone` (default: "UTC")  
**Validation**: ✅ Timezone-aware date/time calculations

**Complete Rule Application Order**:
1. Determine base fulfillment date (latest item date)
2. Add lead time buffer
3. Apply cutoff time rule
4. Skip weekends if configured

---

### 3. **Calculate Confidence Level (HIGH/MEDIUM/LOW)** ✅

**Implementation**: `src/services/promise_service.py::_calculate_confidence()`

**Algorithm**:
```
Calculates using:
- stock_qty / total_qty (coverage from stock)
- shortage_qty / total_qty (fulfillment gap)
- Distribution of near-term vs far-term POs

Confidence Levels:
  HIGH:   >= 99% from stock AND < 1% shortage
  MEDIUM: Mixed fulfillment sources within 7 days, OR 
          stock + near-term POs > far-term POs
  LOW:    > 10% shortage OR far-term POs dominate
```

**Test Case**:
- All from stock → HIGH ✅
- Mix of stock + near POs → MEDIUM ✅
- Significant shortage or late POs → LOW ✅

**Validation**: ✅ Reasonable confidence model based on fulfillment reliability

---

### 4. **Return Required Response Fields** ✅

**Response Model**: `src/models/response_models.py::PromiseResponse`
```python
{
  "promise_date": date,
  "confidence": str ("HIGH"|"MEDIUM"|"LOW"),
  "plan": [
    {
      "item_code": str,
      "qty_required": float,
      "fulfillment": [
        {
          "source": str ("stock"|"purchase_order"|"production"),
          "qty": float,
          "available_date": date,
          "warehouse": str,
          "po_id": str (if applicable),
          "expected_date": date (if applicable)
        }
      ],
      "shortage": float
    }
  ],
  "reasons": [str],  # Human-readable explanations
  "blockers": [str],  # Issues preventing fulfillment
  "options": [
    {
      "type": str ("alternate_warehouse"|"expedite_po"),
      "description": str,
      "impact": str,
      "po_id": str (if applicable)
    }
  ]
}
```

**Implementation Validates**:
- ✅ `promise_date`: Calculated as date object
- ✅ `confidence`: Set to HIGH/MEDIUM/LOW
- ✅ `plan`: Detailed per-item breakdown with fulfillment sources
- ✅ `reasons`: Generated via `_generate_reasons()`
- ✅ `blockers`: Identified via `_identify_blockers()`
- ✅ `options`: Suggested via `_suggest_options()`

---

### 5. **Apply Decision Back to ERPNext** ✅

**Implementation**: `src/services/apply_service.py::apply_promise_to_sales_order()`

#### 5.1 Add Comment to Sales Order
```python
action: "add_comment" (or "both")
↓
Creates comment with:
  "Order Promise Date: {promise_date} (Confidence: {confidence})"
```
**Implementation**: `ERPNextClient.add_comment_to_doc()`  
**Validation**: ✅ Writes comment to SO via API

#### 5.2 Update Custom Fields
```python
action: "set_custom_field" (or "both")
↓
Sets:
  - custom_otp_promise_date = {promise_date}
  - custom_otp_confidence = {confidence}
```
**Implementation**: `ERPNextClient.update_sales_order_custom_field()`  
**Note**: Custom fields must be created in ERPNext first  
**Validation**: ✅ Attempts to write custom fields; gracefully handles missing fields

#### 5.3 Create Procurement Suggestion
```python
Suggestion Type: "Material Request" or "Purchase Order"
↓
Creates document with:
  - Items needing procurement
  - Required by date
  - Priority
  - Warehouse
```
**Implementation**: `src/services/apply_service.py::create_procurement_suggestion()`  
**Model**: `src/models/request_models.py::ProcurementSuggestionRequest`  
**Response**: `ProcurementSuggestionResponse` with document ID & link  
**Validation**: ✅ Full procurement suggestion workflow

---

## API Endpoints

**Base URL**: `http://0.0.0.0:8001` (configurable)

### Endpoint 1: Calculate Promise
```
POST /otp/promise
Content-Type: application/json

Request:
{
  "customer": "CUST-001",
  "items": [
    {
      "item_code": "ITEM-001",
      "qty": 10.0,
      "warehouse": "Stores - WH"  # optional
    }
  ],
  "desired_date": "2026-02-15",  # optional
  "rules": {
    "no_weekends": true,
    "cutoff_time": "14:00",
    "timezone": "UTC",
    "lead_time_buffer_days": 1
  }
}

Response: PromiseResponse (see section 4 above)
```

### Endpoint 2: Apply Promise
```
POST /otp/apply
Content-Type: application/json

Request:
{
  "sales_order_id": "SO-00123",
  "promise_date": "2026-02-15",
  "confidence": "HIGH",
  "action": "both",  # "add_comment" | "set_custom_field" | "both"
  "comment_text": "Custom comment (optional)"
}

Response: ApplyPromiseResponse
{
  "status": "success|error",
  "sales_order_id": "SO-00123",
  "actions_taken": [str],
  "erpnext_response": {...},
  "error": null
}
```

### Endpoint 3: Create Procurement Suggestion
```
POST /otp/procurement-suggest
Content-Type: application/json

Request:
{
  "items": [
    {
      "item_code": "ITEM-001",
      "qty_needed": 5.0,
      "required_by": "2026-02-01",
      "reason": "Order promise fulfillment"  # optional
    }
  ],
  "suggestion_type": "Material Request",  # or "Purchase Order"
  "priority": "High"  # High | Medium | Low
}

Response: ProcurementSuggestionResponse
{
  "status": "success|error",
  "suggestion_id": "MR-00456",
  "type": "Material Request",
  "items_count": 1,
  "erpnext_url": "http://localhost:8080/app/material-request/MR-00456",
  "error": null
}
```

### Endpoint 4: Health Check
```
GET /otp/health
Response: HealthResponse
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": true|false,
  "message": null
}
```

---

## Architecture & Code Quality

### Service Layer Design
- ✅ **PromiseService**: Core algorithm (stock + PO + rules)
- ✅ **StockService**: Abstracts ERPNext stock queries
- ✅ **ApplyService**: Abstracts ERPNext write operations
- ✅ **ERPNextClient**: Centralized API communication

### Data Models
- ✅ **Request Models**: Strict validation via Pydantic
  - `PromiseRequest`, `ApplyPromiseRequest`, `PromiseRules`
- ✅ **Response Models**: Structured, type-safe responses
  - `PromiseResponse`, `ApplyPromiseResponse`, `ProcurementSuggestionResponse`

### Error Handling
- ✅ Custom `ERPNextClientError` exception
- ✅ Graceful degradation (e.g., missing custom fields)
- ✅ Structured logging at each layer
- ✅ HTTP error responses with meaningful messages

### Testing
- ✅ Unit tests for promise service (`tests/unit/test_promise_service.py`)
- ✅ Integration tests for ERPNext (`tests/integration/test_erpnext_integration.py`)
- ✅ API tests for endpoints (`tests/api/test_promise_endpoint.py`)
- ✅ E2E tests for UI workflows (`tests/e2e/test_order_promise_ui.py`)
- ✅ Mock fixtures for isolated testing

---

## Configuration

**File**: `.env` (created from `.env.example`)

### ERPNext Connection
```
ERPNEXT_BASE_URL=http://localhost:8080
ERPNEXT_API_KEY=your_api_key_here
ERPNEXT_API_SECRET=your_api_secret_here
ERPNEXT_SITE_NAME=erpnext.localhost
```

### OTP Service
```
OTP_SERVICE_HOST=0.0.0.0
OTP_SERVICE_PORT=8001
OTP_SERVICE_ENV=development  # development | production
```

### Business Rules Defaults
```
DEFAULT_WAREHOUSE=Stores - WH
NO_WEEKENDS=true
CUTOFF_TIME=14:00
TIMEZONE=UTC
LEAD_TIME_BUFFER_DAYS=1
```

### Testing
```
RUN_INTEGRATION=0  # Set to 1 to run integration tests
ERPNEXT_TEST_USERNAME=Administrator
ERPNEXT_TEST_PASSWORD=admin
```

---

## Deployment

### Docker Support
- ✅ `Dockerfile` provided for containerization
- ✅ `docker-compose.yml` for orchestration with ERPNext

### Running the Application

**Method 1: Direct Python**
```bash
python -m src.main
```

**Method 2: Docker Compose**
```bash
docker-compose up
```

**Method 3: Uvicorn CLI**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

### API Documentation
- ✅ OpenAPI/Swagger docs at: `http://localhost:8001/docs`
- ✅ ReDoc at: `http://localhost:8001/redoc`

---

## Known Limitations & Future Enhancements

### Current Limitations
1. **Single Warehouse Focus**: MVP defaults to single warehouse (`DEFAULT_WAREHOUSE`)
   - Future: Multi-warehouse optimization
2. **Production Orders**: Not yet implemented
   - Future: Support for MOs as supply sources
3. **Custom Pricing/Lead Times**: Uses generic buffers
   - Future: Item-specific lead times from vendor records
4. **Split Shipment Calculation**: Options suggested but not fully planned
   - Future: Automatic split shipment optimization

### Future Enhancements
- [ ] Machine learning confidence model
- [ ] Real-time supply chain optimization
- [ ] Supplier performance analytics
- [ ] Demand forecasting integration
- [ ] Multi-currency support
- [ ] Batch commitment management

---

## Validation Summary

| Requirement | Implementation | Status | Evidence |
|---|---|---|---|
| **Calculate promise date** | PromiseService | ✅ | `promise_service.py::calculate_promise()` |
| **Check current stock** | StockService | ✅ | `stock_service.py::get_available_stock()` |
| **Check incoming supply (POs)** | StockService | ✅ | `stock_service.py::get_incoming_supply()` |
| **Apply weekend rule** | PromiseService | ✅ | `promise_service.py::_skip_weekends()` |
| **Apply cutoff time rule** | PromiseService | ✅ | `promise_service.py::_apply_cutoff_rule()` |
| **Apply lead time buffer** | PromiseService | ✅ | `promise_service.py::_apply_business_rules()` |
| **Return promise_date** | PromiseResponse | ✅ | `response_models.py::PromiseResponse` |
| **Return confidence (HIGH/MEDIUM/LOW)** | PromiseService | ✅ | `promise_service.py::_calculate_confidence()` |
| **Return reasons** | PromiseService | ✅ | `promise_service.py::_generate_reasons()` |
| **Return blockers** | PromiseService | ✅ | `promise_service.py::_identify_blockers()` |
| **Return options** | PromiseService | ✅ | `promise_service.py::_suggest_options()` |
| **Add comment to SO** | ApplyService | ✅ | `apply_service.py::apply_promise_to_sales_order()` |
| **Set custom field on SO** | ApplyService | ✅ | `apply_service.py::apply_promise_to_sales_order()` |
| **Create procurement doc** | ApplyService | ✅ | `apply_service.py::create_procurement_suggestion()` |

---

## Conclusion

✅ **The application fully implements the Order Promise Engine (OTP) skill.**

The implementation demonstrates:
- **Correct Business Logic**: Multi-source fulfillment planning with configurable rules
- **Clean Architecture**: Layered services with clear separation of concerns
- **Comprehensive Testing**: Unit, integration, API, and E2E test suites
- **Production Readiness**: Docker support, error handling, logging, configuration management
- **Extensibility**: Well-structured for future enhancements

**The application is ready for:**
1. Local development testing
2. Integration testing with ERPNext instance
3. Pilot deployment
4. Enhancement development

---

**Next Steps**:
1. Start the application: `python -m src.main`
2. Access API docs: `http://localhost:8001/docs`
3. Run tests: `pytest` (requires ERPNext instance for integration tests)
4. Deploy: Use provided Docker/docker-compose configuration
