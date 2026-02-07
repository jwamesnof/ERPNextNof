# 🚀 ERPNext Order Promise Engine (OTP)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Test Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)](./tests/)
[![Tests](https://img.shields.io/badge/tests-260-success.svg)](./tests/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Transform customer expectations into reliable commitments**  
> An intelligent microservice that calculates realistic delivery dates for ERPNext orders by analyzing real-time inventory, incoming supply chains, and business constraints.

---

## 🎯 The Challenge

In modern supply chains, promising delivery dates is complex:
- ❌ Static lead times don't account for actual stock availability
- ❌ Manual calculations are time-consuming and error-prone  
- ❌ Overselling creates broken promises and unhappy customers
- ❌ Conservative estimates leave money on the table

## ✨ The Solution

**OTP (Order Promise Engine)** provides intelligent, data-driven promise dates by:
- ✅ **Real-time inventory analysis** across warehouses
- ✅ **Supply chain visibility** through purchase orders and incoming stock
- ✅ **Confidence scoring** (HIGH/MEDIUM/LOW) based on fulfillment certainty
- ✅ **Explainable AI** with detailed reasoning for every promise
- ✅ **Automated procurement** suggestions when stock is insufficient
- ✅ **Seamless ERPNext integration** with write-back capabilities

---

## 🏆 Key Features

### 🧠 Smart Promise Calculation
Deterministic algorithm that considers:
- Current stock levels across multi-warehouse setups
- Incoming purchase orders with delivery dates
- Safety stock requirements and lead time buffers
- Business rules (weekends, cutoff times, holidays)
- Customer-specific requirements

### 📊 Confidence Scoring
Every promise includes transparency:
- **HIGH**: Fulfillable from existing stock
- **MEDIUM**: Requires incoming purchase orders
- **LOW**: Needs procurement or has constraints

### 🔍 Complete Transparency
Each calculation provides:
- Line-by-line fulfillment breakdown
- Warehouse allocation details
- Alternative delivery scenarios
- Blocking factors (if any)
- Procurement recommendations

### ⚡ Production-Ready Architecture
- **RESTful API** with OpenAPI documentation
- **Resilient design** with circuit breakers and retry logic
- **Comprehensive testing**: 260 tests, 98% coverage
- **Docker support** for easy deployment
- **Health monitoring** endpoints
- **Detailed logging** for debugging

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│         OTP Service (FastAPI - Port 8001)          │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │  📡 REST API Layer                          │    │
│  │  /otp/promise - Calculate delivery dates    │    │
│  │  /api/items/stock - Query stock levels      │    │
│  │  /health - Service health check             │    │
│  └──────────────┬──────────────────────────────┘    │
│                 │                                    │
│  ┌──────────────▼──────────────────────────────┐    │
│  │  🎯 Business Logic Layer                    │    │
│  │  - Promise Service (core algorithm)         │    │
│  │  - Stock Service (inventory lookup)         │    │
│  │  - Apply Service (ERPNext write-back)       │    │
│  │  - Mock Supply Service (PO simulation)      │    │
│  └──────────────┬──────────────────────────────┘    │
│                 │                                    │
│  ┌──────────────▼──────────────────────────────┐    │
│  │  🔌 ERPNext Client (HTTP + Retry Logic)     │    │
│  │  - Connection pooling                        │    │
│  │  - Circuit breaker pattern                   │    │
│  │  - Automatic retries with backoff            │    │
│  └──────────────┬──────────────────────────────┘    │
└─────────────────┼────────────────────────────────────┘
                  │ HTTPS/HTTP
                  ▼
         ┌────────────────────────┐
         │   ERPNext (Port 8080)  │
         │  ┌──────────────────┐  │
         │  │ 📦 Items         │  │
         │  │ 📊 Stock Ledger  │  │
         │  │ 🛒 Sales Orders  │  │
         │  │ 📋 Purchase Orders│ │
         │  │ 🏢 Warehouses    │  │
         │  └──────────────────┘  │
         └────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** installed
- **ERPNext instance** (cloud or self-hosted)
- **API credentials** for ERPNext (API Key + Secret)
- **Docker** (optional, for containerized deployment)

### Option 1: Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/ERPNextNof.git
cd ERPNextNof

# 2. Configure environment
cp .env.example .env
# Edit .env with your ERPNext credentials

# 3. Start with Docker Compose
docker-compose up --build

# 🎉 Service running at http://localhost:8001
# 📚 API docs at http://localhost:8001/docs
```

### Option 2: Local Development

```bash
# 1. Clone and navigate
git clone https://github.com/yourusername/ERPNextNof.git
cd ERPNextNof

# 2. Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate     
# Activate (Linux/Mac)
source .venv/bin/activate 

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Run the service
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

### Verify Installation

```bash
# Check health
curl http://localhost:8001/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "0.1.0",
#   "erpnext_connected": true,
#   "message": "All systems operational"
# }
```

---

## 📖 API Usage

### 1. Calculate Order Promise Date

**POST** `/otp/promise`

Calculates when an order can be delivered based on current inventory and supply chain.

**Request:**
```bash
curl -X POST "http://localhost:8001/otp/promise" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 10,
        "warehouse": "Stores - WH"
      },
      {
        "item_code": "ITEM-002",
        "qty": 25,
        "warehouse": "Finished Goods - WH"
      }
    ],
    "desired_date": "2026-02-01",
    "desired_date_mode": "prefer_early",
    "rules": {
      "no_weekends": true,
      "cutoff_time": "14:00",
      "timezone": "UTC",
      "lead_time_buffer_days": 1
    }
  }'
```

**Response:**
```json
{
  "promise_date": "2026-02-05",
  "confidence": "MEDIUM",
  "plan": [
    {
      "item_code": "ITEM-001",
      "qty_required": 10,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 5,
          "available_date": "2026-01-25",
          "warehouse": "Stores - WH"
        },
        {
          "source": "purchase_order",
          "qty": 5,
          "available_date": "2026-02-03",
          "po_id": "PO-00123"
        }
      ],
      "shortage": 0
    },
    {
      "item_code": "ITEM-002",
      "qty_required": 25,
      "fulfillment": [
        {
          "source": "stock",
          "qty": 25,
          "available_date": "2026-01-25",
          "warehouse": "Finished Goods - WH"
        }
      ],
      "shortage": 0
    }
  ],
  "reasons": [
    "Item ITEM-001: 5 units from stock, 5 units from PO-00123 (arriving 2026-02-03)",
    "Item ITEM-002: 25 units from stock (Finished Goods - WH)",
    "Added 1 day(s) lead time buffer",
    "Adjusted from 2026-02-04 to 2026-02-05 (business rules applied)"
  ],
  "blockers": [],
  "options": [
    {
      "scenario": "expedite_po_123",
      "promise_date": "2026-02-01",
      "description": "If PO-00123 can arrive by 2026-01-31"
    }
  ]
}
```

### 2. Query Stock Levels

**GET** `/api/items/stock/{item_code}`

Check real-time stock availability for an item across warehouses.

**Request:**
```bash
curl "http://localhost:8001/api/items/stock/ITEM-001?warehouse=Stores%20-%20WH"
```

**Response:**
```json
{
  "item_code": "ITEM-001",
  "warehouse": "Stores - WH",
  "actual_qty": 150.0,
  "available_qty": 135.0,
  "reserved_qty": 15.0,
  "uom": "Nos",
  "valuation_rate": 250.00
}
```

### 3. Apply Promise to Sales Order

**POST** `/otp/apply`

Write calculated promise date back to ERPNext Sales Order.

**Request:**
```bash
curl -X POST "http://localhost:8001/otp/apply" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_order_id": "SO-00456",
    "promise_date": "2026-02-05",
    "confidence": "MEDIUM",
    "action": "both",
    "reasons": [
      "Item ITEM-001: Stock + PO fulfillment",
      "Buffer applied for processing time"
    ]
  }'
```

**Response:**
```json
{
  "status": "success",
  "sales_order_id": "SO-00456",
  "updated_fields": ["delivery_date", "custom_promise_confidence"],
  "comment_added": true,
  "message": "Promise date applied successfully"
}
```

### 4. Generate Procurement Suggestions

**POST** `/otp/procurement-suggest`

Automatically create Material Requests for items with shortages.

**Request:**
```bash
curl -X POST "http://localhost:8001/otp/procurement-suggest" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "item_code": "ITEM-003",
        "qty_needed": 50,
        "required_by": "2026-02-10",
        "reason": "Sales Order SO-00789 shortage",
        "warehouse": "Stores - WH"
      }
    ],
    "suggestion_type": "material_request",
    "priority": "HIGH"
  }'
```

**Response:**
```json
{
  "status": "created",
  "material_request_id": "MR-00234",
  "items_count": 1,
  "total_value": 12500.00,
  "priority": "HIGH",
  "url": "http://localhost:8080/app/material-request/MR-00234"
}
```

---

## 🧪 Testing & Quality

### Test Suite Overview

This project maintains a **comprehensive test suite** with 260 tests ensuring reliability:

| Test Type | Count | Coverage | Purpose |
|-----------|-------|----------|---------|
| **Unit Tests** | 171 | Core logic | Algorithm correctness, edge cases |
| **API Tests** | 58 | REST endpoints | Request/response validation |
| **Integration Tests** | 20 | ERPNext connection | Real-world scenarios |
| **E2E Tests** | 11 | Full workflows | User journey validation |

**Overall Coverage**: 98% (see [tests/TEST_PLAN_INDEX.md](tests/TEST_PLAN_INDEX.md))

### Running Tests

**Quick Test (Unit + API):**
```bash
# Activate virtual environment
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Linux/Mac

# Run fast tests with coverage
pytest tests/unit/ tests/api/ -v --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest tests/unit/ tests/api/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

**Integration Tests (Requires ERPNext):**
```bash
# Set environment variables
export RUN_INTEGRATION=1
export ERPNEXT_BASE_URL=http://localhost:8080
export ERPNEXT_API_KEY=your_key
export ERPNEXT_API_SECRET=your_secret

# Run integration tests
pytest tests/integration/ -v --tb=short
```

*Full integration test setup: [INTEGRATION_TESTS.md](INTEGRATION_TESTS.md)*

**End-to-End Tests (Playwright):**
```bash
# Install Playwright browsers (one-time setup)
playwright install chromium

# Run E2E tests
pytest tests/e2e/ -v

# Watch browser interactions (debugging)
pytest tests/e2e/ -v --headed --slowmo 500
```

**Run ALL Tests:**
```bash
# Complete test suite
pytest -v --cov=src --cov-report=html --cov-report=term

# Skip slow tests
pytest -v -m "not slow"

# Run specific test file
pytest tests/unit/test_promise_service.py -v
```

### Test Reports

**Allure Reports** (Interactive HTML):
```bash
# Generate Allure results
pytest --alluredir=allure-results

# Serve report
allure serve allure-results
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# =====================================================
# ERPNext Connection Settings
# =====================================================
ERPNEXT_BASE_URL=http://localhost:8080
ERPNEXT_API_KEY=your_api_key_here
ERPNEXT_API_SECRET=your_api_secret_here
ERPNEXT_SITE_NAME=erpnext.localhost

# =====================================================
# OTP Service Settings
# =====================================================
OTP_SERVICE_HOST=0.0.0.0
OTP_SERVICE_PORT=8001
OTP_SERVICE_ENV=development  # development | staging | production

# =====================================================
# Business Rules (Defaults)
# =====================================================
DEFAULT_WAREHOUSE=Stores - WH
NO_WEEKENDS=true
CUTOFF_TIME=14:00
TIMEZONE=UTC
LEAD_TIME_BUFFER_DAYS=1

# =====================================================
# Advanced Settings
# =====================================================
# Connection pool size
ERPNEXT_MAX_CONNECTIONS=10
ERPNEXT_TIMEOUT_SECONDS=30

# Circuit breaker thresholds
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Retry policy
MAX_RETRIES=3
RETRY_BACKOFF_FACTOR=0.5

# =====================================================
# Testing (Development Only)
# =====================================================
RUN_INTEGRATION=0
ERPNEXT_TEST_USERNAME=Administrator
ERPNEXT_TEST_PASSWORD=admin
```

### ERPNext API Key Setup

1. **Login to ERPNext** as Administrator
2. Navigate to **User Profile** → **API Access**
3. Click **Generate API Secret**
4. Copy the **API Key** and **API Secret**
5. Add to `.env` file

**Alternative (Token-based):**
```bash
# Use session token instead
ERPNEXT_TOKEN=your_session_token
```

---

## 🏛️ Project Structure

```
ERPNextNof/
│
├── 📁 src/                         # Application source code
│   ├── main.py                     # FastAPI application entry
│   ├── config.py                   # Configuration management
│   │
│   ├── 📁 clients/                 # External service clients
│   │   └── erpnext_client.py       # ERPNext HTTP client with retry logic
│   │
│   ├── 📁 controllers/             # Request handlers
│   │   └── otp_controller.py       # Business logic orchestration
│   │
│   ├── 📁 models/                  # Data models (Pydantic)
│   │   ├── request_models.py       # API request schemas
│   │   └── response_models.py      # API response schemas
│   │
│   ├── 📁 routes/                  # API route definitions
│   │   ├── otp.py                  # OTP calculation endpoints
│   │   └── items.py                # Stock query endpoints
│   │
│   ├── 📁 services/                # Core business logic
│   │   ├── promise_service.py      # Promise calculation algorithm
│   │   ├── stock_service.py        # Stock level queries
│   │   ├── apply_service.py        # ERPNext write-back operations
│   │   └── mock_supply_service.py  # Purchase order simulations
│   │
│   └── 📁 utils/                   # Helper utilities
│       └── warehouse_utils.py      # Warehouse name handling
│
├── 📁 tests/                       # Test suite (200+ tests)
│   ├── conftest.py                 # Pytest configuration & fixtures
│   │
│   ├── 📁 unit/                    # Unit tests (171 tests)
│   │   ├── test_config.py
│   │   ├── test_models.py
│   │   ├── test_promise_service.py
│   │   ├── test_stock_service.py
│   │   ├── test_apply_service.py
│   │   ├── test_erpnext_client.py
│   │   └── ...
│   │
│   ├── 📁 api/                     # API integration tests (58+ tests)
│   │   ├── test_endpoints.py
│   │   ├── test_otp_routes.py
│   │   └── test_error_handling.py
│   │
│   ├── 📁 integration/             # Real ERPNext tests (20+ tests)
│   │   ├── test_erpnext_integration.py
│   │   └── test_stock_queries.py
│   │
│   └── 📁 e2e/                     # End-to-end tests (8+ tests)
│       ├── test_order_promise.py
│       └── 📁 pages/               # Page Object Models
│
├── 📁 data/                        # Demo data files
│   ├── Sales Invoice.csv
│   └── purchase_orders.csv
│
├── 📁 .github/                     # CI/CD workflows
│   └── workflows/
│       ├── ci.yml                  # PR tests + coverage
│       └── integration.yml         # Integration tests
│
├── 📁 allure-results/              # Test report artifacts
├── 📁 htmlcov/                     # Coverage HTML reports
│
├── 📄 docker-compose.yml           # Multi-container orchestration
├── 📄 Dockerfile                   # Container image definition
├── 📄 requirements.txt             # Python dependencies
├── 📄 pyproject.toml               # Poetry configuration
├── 📄 pytest.ini                   # Pytest settings
│
├── 📖 README.md                    # This file
├── 📖 QUICK_START.md               # Interactive quick start guide
├── 📖 INTEGRATION_TESTS.md         # Integration testing guide
└── 📖 TEST_SUMMARY.txt             # Detailed test coverage report
```

---

## 🧠 Core Algorithm Deep Dive

### Promise Calculation Flow

```
┌─────────────────────────────────────────────────────────┐
│  1. VALIDATE REQUEST                                    │
│     ✓ Check item codes exist                            │
│     ✓ Validate quantities > 0                           │
│     ✓ Verify warehouse access                           │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  2. GATHER FULFILLMENT SOURCES (per item)               │
│     ┌─────────────────────────────────────────┐        │
│     │ Source 1: Current Stock                 │        │
│     │ • Query actual_qty from Bin             │        │
│     │ • Exclude reserved quantities            │        │
│     │ • Available date = TODAY                 │        │
│     └─────────────────────────────────────────┘        │
│     ┌─────────────────────────────────────────┐        │
│     │ Source 2: Incoming Purchase Orders      │        │
│     │ • Filter by item_code + warehouse        │        │
│     │ • Status = "To Receive" or "Submitted"   │        │
│     │ • Sort by expected_delivery_date (ASC)   │        │
│     └─────────────────────────────────────────┘        │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  3. BUILD FULFILLMENT PLAN (FIFO)
│  3. BUILD FULFILLMENT PLAN (FIFO)                       │
│     for each item:                                      │
│       remaining_qty = qty_required                      │
│       fulfillment_plan = []                             │
│                                                          │
│       # Try to fulfill from stock first                 │
│       if stock_available >= remaining_qty:              │
│         fulfillment_plan.add(stock, remaining_qty)      │
│         remaining_qty = 0                               │
│       else:                                              │
│         fulfillment_plan.add(stock, stock_available)    │
│         remaining_qty -= stock_available                │
│                                                          │
│       # Fill remaining from POs (chronologically)       │
│       for po in sorted_purchase_orders:                 │
│         if remaining_qty == 0: break                    │
│         allocate_qty = min(po.qty, remaining_qty)       │
│         fulfillment_plan.add(po, allocate_qty)          │
│         remaining_qty -= allocate_qty                   │
│                                                          │
│       # Record shortage if any                          │
│       if remaining_qty > 0:                             │
│         shortage = remaining_qty                        │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  4. DETERMINE PROMISE DATE                              │
│     latest_date = max(fulfillment.available_date)      │
│     for all fulfillment sources across all items        │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  5. APPLY BUSINESS RULES                                │
│     ┌─────────────────────────────────────────┐        │
│     │ • Add Lead Time Buffer                   │        │
│     │   promise_date += buffer_days            │        │
│     ├─────────────────────────────────────────┤        │
│     │ • Check Cutoff Time                      │        │
│     │   if current_time > cutoff:              │        │
│     │     promise_date += 1 day                │        │
│     ├─────────────────────────────────────────┤        │
│     │ • Skip Weekends                          │        │
│     │   while is_weekend(promise_date):        │        │
│     │     promise_date += 1 day                │        │
│     └─────────────────────────────────────────┘        │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  6. CALCULATE CONFIDENCE SCORE                          │
│     if 100% from stock:                                 │
│       confidence = HIGH                                 │
│     elif has_po AND po_date < 7 days:                   │
│       confidence = MEDIUM                               │
│     else:                                                │
│       confidence = LOW                                  │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  7. GENERATE EXPLANATIONS                               │
│     ✓ Reasons: How each item is fulfilled               │
│     ✓ Blockers: Shortages, late POs, constraints        │
│     ✓ Options: Alternative scenarios                    │
└─────────────────────────────────────────────────────────┘
```

### Confidence Scoring Logic

```python
def calculate_confidence(fulfillment_plan, promise_date):
    """
    Determine promise confidence based on fulfillment sources.
    
    HIGH (🟢): 
      - 100% fulfillable from current stock
      - No external dependencies
      
    MEDIUM (🟡):
      - Mix of stock + incoming POs within 7 days
      - Reasonable certainty with minor supply chain dependency
      
    LOW (🔴):
      - Depends on POs > 7 days away
      - Has shortage requiring new procurement
      - Multiple complex dependencies
    """
    stock_percentage = calculate_stock_ratio(fulfillment_plan)
    days_until_promise = (promise_date - today()).days
    has_shortage = any(item.shortage > 0 for item in fulfillment_plan)
    
    if stock_percentage >= 1.0:
        return "HIGH"
    elif stock_percentage >= 0.5 and days_until_promise <= 7 and not has_shortage:
        return "MEDIUM"
    else:
        return "LOW"
```

---

## 💼 Real-World Use Cases

### 1. **E-Commerce Order Promising**
```
Scenario: Online customer places order for 3 items
Process:
  1. OTP calculates delivery date: Feb 15, 2026
  2. Confidence: HIGH (all from stock)
  3. Customer sees: "Guaranteed delivery by Feb 15"
  4. Order confirmed automatically
```

### 2. **B2B Sales with Custom Lead Times**
```
Scenario: Large enterprise customer orders 1000 units
Process:
  1. OTP checks: 500 in stock, 500 arriving Feb 20
  2. Confidence: MEDIUM
  3. Sales rep reviews alternative:
     - Option A: Feb 25 (wait for PO)
     - Option B: Feb 10 (expedite PO for $500)
  4. Customer chooses Option B
  5. OTP creates Material Request to expedite
```

### 3. **Multi-Warehouse Optimization**
```
Scenario: Item out of stock in primary warehouse
Process:
  1. OTP searches alternative warehouses
  2. Finds stock in Warehouse B
  3. Calculates transfer time: +2 days
  4. Promise date adjusted automatically
  5. Transfer request created
```

### 4. **Proactive Procurement**
```
Scenario: Customer wants Feb 1, but shortage exists
Process:
  1. OTP identifies 50-unit shortage
  2. Generates Material Request automatically
  3. Suggests expedited procurement
  4. Recalculates promise after procurement
  5. Updates customer via Sales Order comment
```

---

## 🚦 Monitoring & Health Checks

### Health Endpoint

**GET** `/health`

Comprehensive health check with circuit breaker status.

```bash
curl http://localhost:8001/health
```

**Response (Healthy):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": true,
  "circuit_breaker": {
    "state": "closed",
    "failure_count": 0,
    "last_failure": null
  },
  "uptime_seconds": 3600,
  "message": "All systems operational"
}
```

**Response (Degraded):**
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "erpnext_connected": false,
  "circuit_breaker": {
    "state": "open",
    "failure_count": 5,
    "last_failure": "2026-02-07T10:30:00Z"
  },
  "uptime_seconds": 3600,
  "message": "ERPNext connection unstable - circuit breaker active"
}
```

### Circuit Breaker Pattern

The OTP service implements **circuit breaker** to prevent cascading failures:

- **Closed** (Normal): All requests pass through
- **Open** (Failure): Requests fail fast, ERPNext not called
- **Half-Open** (Recovery): Test requests to check recovery

**Configuration:**
```bash
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5  # Open after 5 failures
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60  # Try recovery after 60s
```

### Logging

Structured JSON logs in production:

```json
{
  "timestamp": "2026-02-07T10:15:30.123Z",
  "level": "INFO",
  "service": "otp-service",
  "endpoint": "/otp/promise",
  "customer": "CUST-001",
  "items_count": 3,
  "promise_date": "2026-02-10",
  "confidence": "HIGH",
  "duration_ms": 245
}
```

---

## 🤖 CI/CD Pipeline

### GitHub Actions Workflows

#### 1. **PR Workflow** (`.github/workflows/ci.yml`)

Runs on every pull request:

```yaml
name: CI Tests

on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - ✅ Checkout code
      - ✅ Setup Python 3.11
      - ✅ Install dependencies
      - ✅ Run unit tests (171 tests)
      - ✅ Run API tests (58+ tests)
      - ✅ Generate coverage report
      - ✅ Upload to Codecov
      - ✅ Validate Docker build
```

**Duration**: ~2 minutes  
**Coverage Requirement**: >85%

#### 2. **Integration Workflow** (`.github/workflows/integration.yml`)

Manual trigger for real ERPNext testing:

```yaml
name: Integration Tests

on: workflow_dispatch

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - ✅ Connect to ERPNext (from secrets)
      - ✅ Run integration tests (20+ tests)
      - ✅ Test real API calls
      - ✅ Verify data consistency
```

**Setup**: See [INTEGRATION_TESTS.md](INTEGRATION_TESTS.md)

### Required GitHub Secrets

```
ERPNEXT_BASE_URL
ERPNEXT_API_KEY
ERPNEXT_API_SECRET
CODECOV_TOKEN (optional)
```

---

## 🛣️ Roadmap & Future Enhancements

### ✅ Released (v0.1.0)
- [x] Core promise calculation algorithm
- [x] Stock + Purchase Order fulfillment
- [x] Confidence scoring
- [x] Sales Order write-back
- [x] Material Request generation
- [x] REST API with FastAPI
- [x] Docker support
- [x] Comprehensive test suite (200+ tests)
- [x] Circuit breaker for resilience

### 🚧 In Progress (v0.2.0)
- [ ] Multi-warehouse optimization algorithm
- [ ] Alternative warehouse suggestions
- [ ] Production planning integration
- [ ] Batch processing for bulk orders

### 🔮 Planned (v0.3.0+)
- [ ] **Real-time Updates**: WebSocket for live stock changes
- [ ] **ML-based Lead Times**: Learn from historical data
- [ ] **Shipping Integration**: Real carrier APIs (FedEx, UPS, DHL)
- [ ] **GraphQL API**: Flexible query interface
- [ ] **Prometheus Metrics**: Advanced observability
- [ ] **Mobile App**: React Native client
- [ ] **Multi-tenancy**: Support multiple ERPNext instances
- [ ] **Caching Layer**: Redis for performance
- [ ] **What-if Analysis**: Scenario planning UI
- [ ] **Supplier Portal**: Direct PO visibility

### 💡 Ideas & Explorations
- AI-powered demand forecasting
- Blockchain for supply chain traceability
- IoT sensor integration for real-time inventory
- Natural language order placement
- Automated negotiation with suppliers

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/ERPNextNof.git
cd ERPNextNof

# 2. Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Linux/Mac

# 3. Install dev dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Create feature branch
git checkout -b feature/amazing-feature

# 5. Make changes and test
pytest -v

# 6. Commit (use conventional commits)
git commit -m "feat: add warehouse transfer optimization"

# 7. Push and create PR
git push origin feature/amazing-feature
```

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Maintenance tasks

**Examples:**
```bash
git commit -m "feat: add multi-warehouse optimization"
git commit -m "fix: handle timezone edge cases in cutoff logic"
git commit -m "docs: update API usage examples"
git commit -m "test: add integration tests for PO fulfillment"
```

### Pull Request Guidelines

1. **Write tests** for new features
2. **Ensure all tests pass**: `pytest -v`
3. **Maintain coverage**: Keep above 85%
4. **Update documentation**: README, docstrings, comments
5. **Follow code style**: Black, isort, type hints
6. **Link related issues**: Use "Fixes #123" in PR description

### Code Style

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type check (optional)
mypy src/

# Lint
flake8 src/ tests/
```

---

## 📚 Additional Resources

### Documentation
- **[QUICK_START.md](QUICK_START.md)** - Interactive quick start guide
- **[INTEGRATION_TESTS.md](INTEGRATION_TESTS.md)** - Integration testing setup
- **[TEST_SUMMARY.txt](TEST_SUMMARY.txt)** - Detailed test coverage report
- **[API Docs](http://localhost:8001/docs)** - Interactive Swagger UI (when running)
- **[ReDoc](http://localhost:8001/redoc)** - Alternative API documentation

### ERPNext Resources
- [ERPNext Documentation](https://docs.erpnext.com/)
- [ERPNext API Guide](https://frappeframework.com/docs/user/en/api)
- [ERPNext Forum](https://discuss.erpnext.com/)
- [Frappe Framework](https://frappeframework.com/)

### Technology Stack
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation with Python types
- [Pytest](https://docs.pytest.org/) - Testing framework
- [Playwright](https://playwright.dev/python/) - E2E testing
- [Docker](https://docs.docker.com/) - Containerization

---

## ❓ FAQ

**Q: Does this work with Frappe Cloud?**  
A: Yes! Just use your Frappe Cloud URL as `ERPNEXT_BASE_URL`.

**Q: Can I use this with ERPNext v13?**  
A: This is tested with ERPNext v14+. V13 may work but is not officially supported.

**Q: How do I handle multiple warehouses?**  
A: Specify `warehouse` in each item request. Future versions will auto-optimize across warehouses.

**Q: What if ERPNext is down?**  
A: The circuit breaker will "open" and fail fast, preventing cascading failures. Check `/health` for status.

**Q: Can I customize the promise algorithm?**  
A: Yes! Modify [src/services/promise_service.py](src/services/promise_service.py) and add your business rules.

**Q: Is this production-ready?**  
A: Yes for moderate loads. For high-traffic scenarios, consider adding caching (Redis) and load balancing.

**Q: How do I deploy to production?**  
A: Use Docker Compose or deploy the FastAPI app with Gunicorn/Uvicorn behind Nginx. See deployment guides in docs/.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026 ERPNext OTP Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 🙏 Acknowledgments

Special thanks to:

- **ERPNext Community** - For building an amazing open-source ERP
- **FastAPI Team** - For the excellent Python web framework
- **Playwright Contributors** - For reliable browser automation
- **All Contributors** - Who make this project better every day

### Built With ❤️ By

- Modern Python 3.11+ features
- Type hints and Pydantic for safety
- Test-driven development (TDD)
- Clean architecture principles
- DevOps best practices

---

## 📞 Support & Contact

### Get Help
- 📖 **Documentation**: Check [docs/](docs/) folder
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yourusername/ERPNextNof/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/ERPNextNof/discussions)
- 📧 **Email**: support@example.com

### Community
- 💼 **LinkedIn**: [Project Page](#)
- 🐦 **Twitter**: [@ERPNextOTP](#)
- 📺 **YouTube**: [Tutorial Videos](#)

### Enterprise Support
For enterprise support, custom development, or consulting:
- 🏢 **Website**: https://example.com
- 📧 **Sales**: sales@example.com
- 📞 **Phone**: +1-XXX-XXX-XXXX

---

<div align="center">

**⭐ Star this repo if you find it useful!**

Made with ❤️ for the ERPNext community

[![GitHub stars](https://img.shields.io/github/stars/yourusername/ERPNextNof?style=social)](https://github.com/yourusername/ERPNextNof)
[![GitHub forks](https://img.shields.io/github/forks/yourusername/ERPNextNof?style=social)](https://github.com/yourusername/ERPNextNof/fork)
[![GitHub watchers](https://img.shields.io/github/watchers/yourusername/ERPNextNof?style=social)](https://github.com/yourusername/ERPNextNof)

[⬆ Back to Top](#-erpnext-order-promise-engine-otp)

</div>
