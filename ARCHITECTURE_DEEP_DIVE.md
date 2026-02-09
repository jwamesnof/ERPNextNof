# 🏗️ Architecture Deep Dive - OTP Service

## Executive Summary

The **Order Promise Engine (OTP)** is built on a **layered, resilient microservice architecture** designed for enterprise-grade reliability, maintainability, and scalability. This document provides a comprehensive walkthrough of the system design, architectural decisions, and patterns used.

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Layered Architecture Pattern](#layered-architecture-pattern)
3. [Component Breakdown](#component-breakdown)
4. [Design Patterns](#design-patterns)
5. [Data Flow](#data-flow)
6. [Resilience & Error Handling](#resilience--error-handling)
7. [Dependency Injection](#dependency-injection)
8. [Configuration Management](#configuration-management)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT APPLICATIONS                       │
│  (Sales Orders, Customer Portal, ERP Dashboard, Mobile App)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS/REST
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              API GATEWAY / LOAD BALANCER                      │
│  (Optional: NGINX, AWS ALB, Kubernetes Ingress)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐        ┌─────────┐       ┌─────────┐
   │  OTP #1 │        │  OTP #2 │  ...  │  OTP #N │
   │(Port    │        │(Port    │       │(Port    │
   │ 8001)   │        │ 8001)   │       │ 8001)   │
   └────┬────┘        └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │   SHARED CACHE (Redis/Memcached) │ (Optional)
        │   - Warehouse config cache       │
        │   - Stock data cached            │
        │   - Session store                │
        └──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │   ERPNext Instance(s)            │
        │   (Real-time inventory data)     │
        │   - Stock levels                 │
        │   - Purchase orders              │
        │   - Warehouse config             │
        │   - Item master                  │
        └──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │   External Systems (Optional)    │
        │   - Monitoring/Observability      │
        │   - Logging aggregation          │
        │   - Metrics collection           │
        └──────────────────────────────────┘
```

### Container Deployment Architecture

```
┌──────────────────────────────────────────────────────┐
│         Docker Container / Kubernetes Pod            │
│                                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │  OTP Service Process (uvicorn)                │ │
│  │  - 4 worker threads (CPU cores)               │ │
│  │  - Event loop for async operations            │ │
│  │  - Connection pooling to ERPNext              │ │
│  └────────────────────────────────────────────────┘ │
│  Port: 8001                                          │
│  Memory: ~200MB base + request buffers              │
│  CPU: Scales with concurrent requests               │
│                                                       │
└──────────────────────────────────────────────────────┘
```

---

## Layered Architecture Pattern

The OTP service follows the **classic 4-layer architectural pattern**:

```
┌─────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                     │
│  (FastAPI Framework, OpenAPI Documentation)             │
│  - REST Endpoints                                        │
│  - Request/Response validation                           │
│  - Error formatting                                      │
├─────────────────────────────────────────────────────────┤
│                   CONTROLLER LAYER                       │
│  (Business Logic Orchestration)                          │
│  - OTPController: Coordinates services                   │
│  - Route handlers                                        │
│  - Input validation                                      │
│  - Output formatting                                     │
├─────────────────────────────────────────────────────────┤
│                   SERVICE LAYER                          │
│  (Core Business Logic)                                   │
│  - PromiseService: Promise calculation algorithm         │
│  - StockService: Inventory queries                       │
│  - ApplyService: ERPNext write-back                      │
│  - MockSupplyService: Purchase order simulation          │
├─────────────────────────────────────────────────────────┤
│                  DATA ACCESS LAYER                       │
│  (External System Integration)                           │
│  - ERPNextClient: HTTP communication with ERPNext        │
│  - Connection pooling                                    │
│  - Circuit breaker pattern                              │
│  - Retry logic with exponential backoff                 │
│  - Error handling and translation                        │
├─────────────────────────────────────────────────────────┤
│                 UTILITY LAYER                            │
│  (Cross-cutting Concerns)                                │
│  - WarehouseManager: Warehouse classification            │
│  - CalendarUtils: Workweek calculations                  │
│  - ConfigLoader: Environment & settings management       │
│  - Logging: Structured logging throughout                │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility | Technologies | Example |
|-------|---|---|---|
| **Presentation** | HTTP handling, request routing, response formatting | FastAPI, Pydantic | `GET /otp/promise` endpoint |
| **Controller** | Business flow orchestration, service coordination | Python classes | `OTPController.calculate_promise()` |
| **Service** | Core algorithms, business logic, calculations | PromiseService, StockService | Promise date calculation |
| **Data Access** | External system communication, resilience | ERPNextClient, httpx | Querying ERPNext inventory |
| **Utility** | Domain-specific helpers, cross-cutting concerns | WarehouseUtils, Config | Warehouse type classification |

---

## Component Breakdown

### 1. **FastAPI Application Layer** (`src/main.py`)

```python
# Core responsibilities:
- Initialize FastAPI application
- Configure CORS middleware
- Register routers (otp, items, demo_data)
- Exception handlers
- Startup/shutdown hooks
- Health check endpoint
```

**Key Features:**
- ✅ OpenAPI documentation auto-generated at `/docs`
- ✅ CORS enabled for cross-origin requests
- ✅ Global exception handlers for consistent error responses
- ✅ Middleware for logging and request tracking

---

### 2. **Router Layer** (`src/routes/`)

#### `otp.py` - Promise Calculation Endpoints
```
POST /otp/promise
├── Calculate delivery date for sales order
├── Input: ItemRequest[], PromiseRules
├── Output: PromiseResponse (date, confidence, reasons)
└── Uses: OTPController → PromiseService → StockService → ERPNextClient

POST /otp/apply
├── Write promise back to ERPNext
├── Input: ApplyPromiseRequest (promise_date, sales_order_name)
├── Output: ApplyPromiseResponse (success, message)
└── Uses: OTPController → ApplyService → ERPNextClient

POST /otp/procurement-suggestion
├── Recommend purchase orders when stock insufficient
├── Input: ItemRequest[], PromiseRules
├── Output: ProcurementSuggestionResponse
└── Uses: OTPController → ApplyService
```

#### `items.py` - Inventory Query Endpoints
```
GET /api/items/stock/{item_code}/{warehouse}
├── Query current stock levels
├── Returns: StockResponse (qty_available, reserved, projected)
└── Uses: StockService → ERPNextClient

GET /api/items/{item_code}/warehouses
├── Get all warehouses stocking this item
├── Returns: List[WarehouseStock]
└── Uses: StockService → ERPNextClient
```

---

### 3. **Controller Layer** (`src/controllers/`)

**OTPController** coordinates between routes and services:

```python
class OTPController:
    def __init__(
        self,
        promise_service: PromiseService,    # Dependency injection
        apply_service: ApplyService
    ):
        self.promise_service = promise_service
        self.apply_service = apply_service
    
    def calculate_promise(self, request: PromiseRequest) -> PromiseResponse:
        """
        Orchestrates:
        1. Validate input
        2. Call promise_service.calculate_promise()
        3. Format response
        4. Log operation
        5. Return PromiseResponse
        """
    
    def apply_promise(self, request: ApplyPromiseRequest) -> ApplyPromiseResponse:
        """
        Orchestrates:
        1. Validate ERPNext connectivity
        2. Call apply_service.apply_promise()
        3. Handle success/failure
        4. Return ApplyPromiseResponse
        """
```

**Why Controller Layer?**
- Decouples routes from business logic
- Enables easier unit testing (mock services)
- Centralizes orchestration logic
- Improves code reusability

---

### 4. **Service Layer** (`src/services/`)

#### **PromiseService** - Core Algorithm
The heart of the system. Implements the deterministic promise calculation:

```python
class PromiseService:
    """Promise calculation algorithm with explainability."""
    
    # Public API
    def calculate_promise(
        self,
        customer: str,
        items: List[ItemRequest],
        desired_date: Optional[date] = None,
        rules: Optional[PromiseRules] = None
    ) -> PromiseResponse:
        """
        5-Step Algorithm:
        1. Build fulfillment plan from stock + POs
        2. Determine latest fulfillment date
        3. Apply business rules (cutoff, weekends, buffer)
        4. Apply desired_date constraints if provided
        5. Calculate confidence and generate explanations
        
        Returns: PromiseResponse with:
        - promise_date: calculated delivery date
        - confidence: HIGH/MEDIUM/LOW
        - reasons: human-readable explanations
        - blockers: issues preventing optimal promise
        - options: alternative suggestions
        - plan: line-by-line fulfillment breakdown
        """
    
    # Private implementation methods
    def _build_item_plan(...) -> Tuple[ItemPlan, List[str]]: ...
    def _apply_business_rules(...) -> date: ...
    def _apply_desired_date_constraints(...) -> Dict: ...
    def _calculate_confidence(...) -> str: ...
    def _generate_reasons(...) -> List[str]: ...
    def _identify_blockers(...) -> List[str]: ...
    def _suggest_options(...) -> List[PromiseOption]: ...
```

**Key Algorithms:**
- **Warehouse Classification**: Categorize warehouses (SELLABLE, NEEDS_PROCESSING, IN_TRANSIT, etc.)
- **Calendar Handling**: Sunday-Thursday workweek, skip weekends
- **Stock Allocation**: Chronological fulfillment from available sources
- **Confidence Scoring**: Based on fulfillment certainty and lead times

#### **StockService** - Inventory Management
```python
class StockService:
    """Query and analyze inventory levels."""
    
    def get_available_stock(self, item_code: str, warehouse: str) -> Dict:
        """Get current stock levels with projections"""
    
    def get_incoming_purchase_orders(self, item_code: str, customer: str) -> List[Dict]:
        """Get POs with ETA dates"""
    
    def prepare_fulfillment_sources(self, ...) -> List[FulfillmentSource]:
        """Prepare sorted list of fulfillment options"""
```

#### **ApplyService** - ERPNext Integration
```python
class ApplyService:
    """Write calculated promises back to ERPNext."""
    
    def apply_promise(
        self,
        sales_order_name: str,
        promise_date: date,
        confidence: str
    ) -> ApplyPromiseResponse:
        """Update Sales Order with promise date"""
    
    def create_purchase_order_suggestion(
        self,
        items: List[ItemRequest]
    ) -> ProcurementSuggestionResponse:
        """Generate PO suggestions for shortages"""
```

#### **MockSupplyService** - Testing Utilities
```python
class MockSupplyService:
    """Simulate purchase orders for testing."""
    
    def get_mock_purchase_orders(self, item_code: str) -> List[Dict]:
        """Return simulated PO data"""
```

---

### 5. **Data Access Layer** (`src/clients/`)

**ERPNextClient** - The gateway to ERPNext:

```python
class ERPNextClient:
    """
    HTTP client for ERPNext with resilience patterns.
    
    Features:
    - Connection pooling (reuse TCP connections)
    - Circuit breaker (fail fast if ERPNext down)
    - Retry logic with exponential backoff
    - Request timeouts
    - Error translation
    """
    
    def __init__(self, base_url: str, api_key: str, api_secret: str):
        self.session = httpx.Client(
            base_url=base_url,
            auth=(api_key, api_secret),
            timeout=10.0,
            limits=httpx.Limits(max_connections=100)  # Connection pooling
        )
        self.circuit_breaker = CircuitBreaker(...)
    
    # Data retrieval methods
    def get_bin_details(self, item_code: str, warehouse: str) -> Dict:
        """Get stock in warehouse"""
    
    def get_incoming_purchase_orders(self, item_code: str) -> List[Dict]:
        """Get POs with delivery dates"""
    
    def get_item(self, item_code: str) -> Dict:
        """Get item master data"""
    
    def get_warehouse(self, warehouse_name: str) -> Dict:
        """Get warehouse configuration"""
    
    # Write operations
    def update_sales_order_promise(self, so_name: str, promise_date: str) -> bool:
        """Write promise date back to SO"""
```

**Resilience Patterns:**

```
Request Flow:
┌──────────────────────────────────────────────────────┐
│ 1. Check Circuit Breaker                             │
│    ├─ OPEN (ERPNext down): Fail fast               │
│    ├─ HALF_OPEN (recovering): Allow test request   │
│    └─ CLOSED (normal): Proceed                      │
├──────────────────────────────────────────────────────┤
│ 2. Execute with Retry Logic                         │
│    ├─ Attempt 1: Wait 100ms if fails               │
│    ├─ Attempt 2: Wait 200ms if fails               │
│    ├─ Attempt 3: Wait 400ms if fails               │
│    └─ Attempt 4: Fail with error                    │
├──────────────────────────────────────────────────────┤
│ 3. Apply Timeout (10 seconds)                        │
│    └─ Prevent hanging requests                      │
├──────────────────────────────────────────────────────┤
│ 4. Translate Errors                                  │
│    ├─ HTTP 500 → Retry or circuit open            │
│    ├─ HTTP 403 → Permission denied (don't retry)   │
│    ├─ HTTP 404 → Not found (don't retry)           │
│    └─ Network error → Log and fail gracefully       │
└──────────────────────────────────────────────────────┘
```

---

### 6. **Model Layer** (`src/models/`)

**Request Models** - Input validation with Pydantic:
```python
class ItemRequest(BaseModel):
    item_code: str = Field(..., min_length=1)
    qty: float = Field(..., gt=0)
    warehouse: str

class PromiseRequest(BaseModel):
    customer: str
    items: List[ItemRequest]
    desired_date: Optional[date] = None
    rules: Optional[PromiseRules] = None

class PromiseRules(BaseModel):
    no_weekends: bool = True
    cutoff_time: str = "14:00"
    lead_time_buffer_days: int = Field(1, ge=0)
    desired_date_mode: DesiredDateMode = DesiredDateMode.LATEST_ACCEPTABLE
```

**Response Models** - Type-safe responses:
```python
class FulfillmentSource(BaseModel):
    source_type: str  # "Stock" | "PurchaseOrder"
    warehouse: str
    qty: float
    available_date: date
    confidence: str

class ItemPlan(BaseModel):
    item_code: str
    requested_qty: float
    fulfilled_qty: float
    shortage: float
    fulfillment_sources: List[FulfillmentSource]

class PromiseResponse(BaseModel):
    status: PromiseStatus
    promise_date: Optional[date]
    confidence: str
    reasons: List[str]
    blockers: List[str]
    options: List[PromiseOption]
    plan: List[ItemPlan]
```

---

### 7. **Utility Layer** (`src/utils/`)

**WarehouseManager** - Domain intelligence:
```python
class WarehouseManager:
    """Classify warehouses by their role in the supply chain."""
    
    enum WarehouseType:
        SELLABLE              # Ship directly to customer
        NEEDS_PROCESSING      # Needs extra lead time (QC, assembly)
        IN_TRANSIT            # Stock is on the shelf but locked
        NOT_AVAILABLE         # Ignored for promise calculations
        GROUP                 # Virtual warehouse (sum of sub-warehouses)
    
    def classify_warehouse(self, warehouse: Dict) -> WarehouseType:
        """
        Classify based on warehouse attributes:
        - warehouse_type field
        - disabled status
        - name patterns
        
        Returns: WarehouseType enum
        """
```

**Config System** (`src/config.py`):
```python
class Settings(BaseSettings):
    """Application configuration from environment variables."""
    
    # Database
    db_url: str = "sqlite:///./otp.db"
    
    # ERPNext
    erpnext_base_url: str
    erpnext_api_key: str
    erpnext_api_secret: str
    
    # Service behavior
    request_timeout: int = 10
    max_retries: int = 3
    circuit_breaker_threshold: int = 5
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

---

## Design Patterns

### 1. **Dependency Injection (DI)**

```python
# Constructor injection in controller
class OTPController:
    def __init__(
        self,
        promise_service: PromiseService,    # Injected
        apply_service: ApplyService         # Injected
    ):
        self.promise_service = promise_service
        self.apply_service = apply_service

# In route handler
from fastapi import Depends

def get_otp_controller() -> OTPController:
    promise_service = PromiseService(
        stock_service=StockService(...),
        warehouse_manager=WarehouseManager(...)
    )
    apply_service = ApplyService(erpnext_client=...)
    return OTPController(promise_service, apply_service)

@router.post("/otp/promise")
async def calculate_promise(
    request: PromiseRequest,
    controller: OTPController = Depends(get_otp_controller)
):
    return controller.calculate_promise(request)
```

**Benefits:**
- ✅ Easy to test: Mock dependencies in unit tests
- ✅ Flexible: Swap implementations without changing code
- ✅ Loosely coupled: Services don't depend on concrete classes
- ✅ Single responsibility: Each component has one job

---

### 2. **Circuit Breaker Pattern**

Prevents cascading failures when ERPNext is unavailable:

```python
class CircuitBreaker:
    """Prevent repeated calls to failing external service."""
    
    STATE = Enum('State', 'CLOSED OPEN HALF_OPEN')
    
    def call(self, func, *args, **kwargs):
        if self.state == State.OPEN:
            if self.should_attempt_reset():
                self.state = State.HALF_OPEN
            else:
                raise CircuitBreakerOpen("Service unavailable")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.threshold:
            self.state = State.OPEN
    
    def on_success(self):
        self.failure_count = 0
        self.state = State.CLOSED
```

**State Transitions:**
```
    CLOSED (Normal operation)
       ↓ (failures >= threshold)
    OPEN (Fail fast, reject requests)
       ↓ (wait timeout)
    HALF_OPEN (Test if recovered)
       ↓ (success) → CLOSED
       ↓ (failure) → OPEN
```

---

### 3. **Retry Pattern with Exponential Backoff**

```python
@retry(
    wait=wait_exponential(multiplier=1, min=100ms, max=10s),
    stop=stop_after_attempt(4),
    reraise=True
)
def get_bin_details(self, item_code: str, warehouse: str):
    """Retry up to 4 times with exponential backoff."""
    return self.erpnext_api.get_bin(item_code, warehouse)

# Retry timeline:
# Attempt 1: Immediate
# Attempt 2: Wait 100ms
# Attempt 3: Wait 200ms
# Attempt 4: Wait 400ms
# Give up
```

---

### 4. **Strategy Pattern** - Desired Date Modes

```python
class DesiredDateMode(str, Enum):
    LATEST_ACCEPTABLE      # Latest date acceptable to customer
    NO_EARLY_DELIVERY      # Don't promise before desired date
    STRICT_FAIL            # Must meet or fail

# In PromiseService
def _apply_desired_date_constraints(self, promise_date, desired_date, mode):
    if mode == DesiredDateMode.LATEST_ACCEPTABLE:
        return min(promise_date, desired_date)
    elif mode == DesiredDateMode.NO_EARLY_DELIVERY:
        return max(promise_date, desired_date)
    elif mode == DesiredDateMode.STRICT_FAIL:
        if promise_date <= desired_date:
            return promise_date
        else:
            return None  # Cannot fulfill
```

---

### 5. **Factory Pattern** - Fulfillment Sources

```python
class FulfillmentSourceFactory:
    @staticmethod
    def create_from_stock(item, warehouse, qty, available_date):
        return FulfillmentSource(
            source_type="Stock",
            warehouse=warehouse,
            qty=qty,
            available_date=available_date
        )
    
    @staticmethod
    def create_from_po(po_data):
        return FulfillmentSource(
            source_type="PurchaseOrder",
            warehouse=po_data.warehouse,
            qty=po_data.pending_qty,
            available_date=po_data.schedule_date
        )
```

---

## Data Flow

### Typical Request: Calculate Promise

```
1. HTTP Request (FastAPI)
   POST /otp/promise
   Body: {
     "customer": "CUST-001",
     "items": [{"item_code": "ITEM-001", "qty": 10, "warehouse": "Stores - WH"}],
     "desired_date": "2026-02-15"
   }
   ↓

2. Route Handler Validation (Pydantic)
   - Validate request structure
   - Convert to Python types
   - ↓

3. OTPController.calculate_promise()
   - Input validation
   - Extract parameters
   - Call promise_service
   ↓

4. PromiseService.calculate_promise()
   Step 1: Build fulfillment plan
   ├─ For each item, call StockService.get_fulfillment_sources()
   │  ├─ Query current stock via ERPNextClient.get_bin_details()
   │  ├─ Query POs via ERPNextClient.get_incoming_purchase_orders()
   │  ├─ Classify warehouses
   │  └─ Return sorted list of fulfillment options
   │
   Step 2: Determine latest fulfillment date
   ├─ max(available_date) across all items
   │
   Step 3: Apply business rules
   ├─ Add lead time buffer days
   ├─ Apply cutoff time (if past 14:00, add 1 day)
   ├─ Skip weekends (if no_weekends=True)
   │
   Step 4: Apply desired date constraints
   ├─ LATEST_ACCEPTABLE: min(promise_date, desired_date)
   ├─ NO_EARLY_DELIVERY: max(promise_date, desired_date)
   ├─ STRICT_FAIL: promise_date if <= desired_date, else None
   │
   Step 5: Calculate confidence and explanations
   ├─ Confidence: HIGH/MEDIUM/LOW based on sources
   ├─ Reasons: Human-readable explanations
   ├─ Blockers: Issues (shortage, permission denied, late PO)
   ├─ Options: Alternative suggestions
   ↓

5. HTTP Response (FastAPI)
   {
     "status": "OK",
     "promise_date": "2026-02-17",
     "confidence": "HIGH",
     "reasons": ["100% from stock (Stores - WH)"],
     "blockers": [],
     "plan": [{...}]
   }
```

---

## Resilience & Error Handling

### Error Handling Hierarchy

```python
# Level 1: HTTP Client Errors
try:
    response = await self.session.get(url)
except httpx.NetworkError as e:
    # Network problem (DNS, connection refused, etc.)
    logger.error(f"Network error: {e}")
    raise ERPNextConnectionError(f"Cannot reach ERPNext: {e}")

except httpx.TimeoutException as e:
    # Request took too long
    logger.warning(f"Request timeout: {e}")
    raise ERPNextTimeoutError(f"ERPNext not responding within {timeout}s")

except httpx.HTTPStatusError as e:
    # HTTP error responses
    if response.status_code == 403:
        raise ERPNextPermissionError("API key/secret invalid or permissions denied")
    elif response.status_code == 404:
        raise ERPNextNotFoundError(f"Resource not found: {e.request.url}")
    elif response.status_code >= 500:
        raise ERPNextServerError(f"ERPNext server error: {e}")
```

### Graceful Degradation

```python
# If ERPNext available but PO access denied
if has_po_access_error:
    # Fall back to stock-only calculation
    confidence = "LOW"  # Lower confidence
    blockers.append("PO data unavailable (permission denied)")
    # Continue with calculation, just with limited info
    return response

# If payment method down for writes
if writes_to_erpnext_fail:
    # Return the calculated promise anyway
    return PromiseResponse(
        status="OK",
        promise_date=calculated_date,
        confidence="HIGH",
        reasons=[...],
        warnings=["Could not write promise back to ERPNext"]
    )
```

### Health Checks

```python
@router.get("/health")
async def health_check():
    """Check service and dependency health."""
    
    # Check ERPNext connectivity
    try:
        erpnext_ok = client.get_health_check()
    except Exception as e:
        erpnext_ok = False
    
    return {
        "status": "healthy" if erpnext_ok else "degraded",
        "service": "OTP",
        "erpnext_connected": erpnext_ok,
        "message": "All systems operational" if erpnext_ok else "ERPNext unreachable"
    }
```

---

## Dependency Injection

### Why DI?

```python
# ❌ BAD: Hard-coded dependencies, difficult to test
class PromiseService:
    def __init__(self):
        self.erpnext_client = ERPNextClient(...)  # Hard-coded
    
    def calculate_promise(self, ...):
        # Can't mock ERPNextClient in tests
        pass

# ✅ GOOD: Dependencies injected, easy to test
class PromiseService:
    def __init__(self, stock_service: StockService):
        self.stock_service = stock_service  # Injected
    
    def calculate_promise(self, ...):
        # Can pass mock in tests
        pass

# In tests:
mock_service = Mock(spec=StockService)
promise_service = PromiseService(stock_service=mock_service)
```

### Configuration Objects

```python
# Inject entire config object
class PromiseService:
    def __init__(self, config: PromiseConfig):
        self.config = config  # Contains all settings
    
    def calculate_promise(self, ...):
        buffer_days = self.config.lead_time_buffer_days
        cutoff_time = self.config.cutoff_time
```

---

## Configuration Management

### Environment Variables

```bash
# .env file
ERPNEXT_BASE_URL=https://company.frappe.cloud
ERPNEXT_API_KEY=your-key-here
ERPNEXT_API_SECRET=your-secret-here
LOG_LEVEL=INFO
REQUEST_TIMEOUT=10
```

### Runtime Configuration

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    erpnext_base_url: str
    erpnext_api_key: str
    erpnext_api_secret: str
    log_level: str = "INFO"
    request_timeout: int = 10
    
    class Config:
        env_file = ".env"

# Access anywhere
settings = Settings()
client = ERPNextClient(
    base_url=settings.erpnext_base_url,
    api_key=settings.erpnext_api_key
)
```

---

## Summary

The OTP architecture demonstrates several important principles:

1. **Separation of Concerns** - Each layer has a single responsibility
2. **Resilience** - Circuit breakers, retries, graceful degradation
3. **Testability** - Dependency injection enables easy mocking
4. **Scalability** - Stateless design allows horizontal scaling
5. **Maintainability** - Clear structure and design patterns
6. **Transparency** - Services provide reasoning and explanations

This architecture enables the OTP service to be **production-ready, reliable, and easy to extend**.
