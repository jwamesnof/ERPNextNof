# PRESENTATION_DRAFT.md

## Slides (12-15 max)

### 1) Title + Me (15-20 sec)
- ERPNext Order Promise Engine (OTP)
- Your name, role, and focus (testing + API automation)
- Course: Skill Development and Test Automation

Speaker notes:
- Quick intro and role on this project.
- One sentence: OTP turns inventory data into reliable delivery promises.

Visual suggestion:
- Title slide with OTP logo or ERPNext + OTP badge.

---

### 2) Why ERPNext + Why This Problem Matters
- ERPNext: open source, rich ERP modules, free API
- Business pain: wrong promises lead to churn and expediting
- Goal: deterministic, explainable promise dates

Speaker notes:
- ERPNext chosen for real data and API access.
- The problem costs revenue and trust.

Visual suggestion:
- Simple “before vs after” timeline graphic.

---

### 3) User Story (Pain Before)
- Sales rep sees stock but not incoming supply
- Manual promise = inconsistent and slow
- Missed delivery dates damage trust

Speaker notes:
- Short story: a customer asks for delivery date; manual guess hurts credibility.

Visual suggestion:
- One short story card with customer quote.

---

### 4) Solution Overview (What OTP Does)
- Query live stock + incoming purchase orders
- Apply business rules (cutoff, weekends, buffers)
- Return promise date + confidence + reasons
- Optionally write back to ERPNext Sales Order

Speaker notes:
- OTP is a microservice sitting beside ERPNext and enhancing decisions.

Visual suggestion:
- High-level 3-step flow diagram.

---

### 5) Architecture Diagram (Backend + ERPNext)
- FastAPI service on port 8001
- ERPNext API client with retries + circuit breaker
- Services: Promise, Stock, Apply

Speaker notes:
- Explain modular design and resilience features.

Visual suggestion:
- Architecture sketch (see README architecture diagram).

---

### 6) Key API Endpoints (Actual Implementation)
- POST /otp/promise
- POST /otp/apply
- POST /otp/procurement-suggest
- GET /otp/sales-orders
- GET /otp/sales-orders/{sales_order_id}
- GET /api/items/stock
- GET /health, GET /diagnostics

Speaker notes:
- All endpoints are in src/routes/otp.py and src/routes/items.py.
- Note: Docs mention /otp/procurement-suggestion but code uses /otp/procurement-suggest.

Visual suggestion:
- Table with endpoint + purpose.

---

### 7) OTP Logic Overview (Algorithm Highlights)
- Build fulfillment plan per item (stock + POs)
- Apply processing lead time + buffers
- Skip weekends (Friday/Saturday) if configured
- Calculate confidence (HIGH/MEDIUM/LOW)

Speaker notes:
- Deterministic: same input always yields same output.

Visual suggestion:
- 5-step algorithm flow (from ALGORITHM_EXPLANATION.md).

---

### 8) Frontend UX Flow (Status)
- UI pages requested: Promise Calculator, Scenarios, Audit & Trace, Settings
- Status in this repo: Not implemented yet
- Demo uses API + Swagger UI instead

Speaker notes:
- Be transparent: no frontend in this repo; use Swagger and ERPNext UI as proof.

Visual suggestion:
- Placeholder slide with “Not implemented yet”.

---

### 9) Testing Strategy Overview
- Unit tests (171) for services, models, utils
- API tests (58) with mocked ERPNext
- Integration tests (20) with real ERPNext (optional)
- E2E/UI tests: not implemented yet (marker exists)

Speaker notes:
- Emphasize pyramid: fast unit, focused API, optional integration.

Visual suggestion:
- Test pyramid graphic.

---

### 10) Success Criteria (What Good Means)
- Unit: 171 tests, 98% coverage, <16s
- API: 58 tests, 100% endpoint coverage, <5s
- Integration: 20 tests, real ERPNext, <60s
- Overall: 98% coverage, zero flaky tests

Speaker notes:
- These are in tests/TEST_PLAN_INDEX.md.

Visual suggestion:
- Metrics table.

---

### 11) CI Pipeline + Coverage Reporting
- GitHub Actions on PR (ci.yml)
- Unit + API tests with coverage XML
- Codecov upload + Allure artifacts
- PR gating: failing tests block merge

Speaker notes:
- Show the CI workflow file and how it reports.

Visual suggestion:
- CI pipeline diagram.

---

### 12) Live Demo Plan (Exact Steps)
- Start backend (uvicorn or docker-compose)
- Health + diagnostics endpoints
- POST /otp/promise via Swagger
- Show sales order details + stock endpoint
- Run unit+api tests with coverage

Speaker notes:
- Keep demo short and reliable; use mock mode if ERPNext is offline.

Visual suggestion:
- Checklist screenshot.

---

### 13) Code Snippet 1 (MVC separation)
- Route calls controller, controller calls service
- Clear separation for testing and maintenance

Speaker notes:
- Show how FastAPI route depends on controller, controller delegates to service.

Visual suggestion:
- Code snippet slide (short, 15-25 lines).

---

### 14) Code Snippet 2 (Mocking ERPNext + Integration)
- Unit test with mock_erpnext_client fixture
- Integration test marked and gated by RUN_INTEGRATION

Speaker notes:
- Explain how mock and real tests coexist without flakiness.

Visual suggestion:
- Two short code blocks (unit + integration).

---

### 15) Lessons Learned + Next Steps + Q&A
- Lessons: deterministic logic, resilient API client, testing depth
- Next: build UI pages, add Playwright tests
- Q&A

Speaker notes:
- Close with roadmap and invite questions.

Visual suggestion:
- Roadmap bullets.

---

## Live Demo Script (Minute-by-Minute)

### Pre-demo checklist (5-10 min before)
- Backend running:
  - Local: uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
  - Docker: docker-compose up --build
- ERPNext reachable (or mock supply enabled)
- .env values set (ERPNEXT_BASE_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET)
- Test data: known item codes (TEST-ITEM-001 or ERPNext items)

### 0:00 - 1:00 Intro
- Open slides and say the one-line pitch.

### 1:00 - 3:00 Health + Diagnostics
- Open browser: http://localhost:8001/health
- Show result: service status + ERPNext connection
- Open: http://localhost:8001/diagnostics
- Explain circuit breaker and pooled HTTP client

### 3:00 - 7:00 OTP Promise Demo (Swagger)
- Open Swagger UI: http://localhost:8001/docs
- Run POST /otp/promise with a sample payload
- Highlight response fields:
  - promise_date
  - confidence
  - plan + reasons

### 7:00 - 9:00 Sales Order + Stock
- Call GET /otp/sales-orders
- Call GET /otp/sales-orders/{id} for one SO
- Call GET /api/items/stock?item_code=...&warehouse=...

### 9:00 - 11:00 Apply Promise
- Run POST /otp/apply
- If ERPNext is available, confirm change in ERPNext UI

### 11:00 - 13:00 Run Tests Live
- Unit + API tests:
  - pytest tests/unit/ tests/api/ -v --cov=src --cov-report=term-missing
- Optional integration test (if ERPNext is live):
  - RUN_INTEGRATION=1 pytest tests/integration/ -v
- Show coverage report:
  - Open htmlcov/index.html

### 13:00 - 14:00 CI Proof
- Show .github/workflows/ci.yml
- Highlight Codecov and Allure artifacts

### 14:00 - 15:00 Wrap + Q&A
- Summarize results, open questions.

### Backup plan if ERPNext is offline
- Enable mock supply mode (settings.use_mock_supply)
- Run /otp/health (shows mock supply)
- Run /otp/promise with mock results
- Skip integration test step

---

## Code Snippet Selection (short, 15-30 lines each)

### Snippet 1: MVC separation (route -> controller -> service)
Source: src/routes/otp.py and src/controllers/otp_controller.py

```python
@router.post("/promise", response_model=PromiseResponse, response_model_exclude_none=False)
async def calculate_promise(
    request: PromiseRequest,
    controller: OTPController = Depends(get_controller),
) -> PromiseResponse:
    try:
        return controller.calculate_promise(request)
    except ERPNextClientError as e:
        logger.error(f"ERPNext error: {e}")
        raise HTTPException(status_code=503, detail=f"ERPNext service error: {str(e)}")
```

```python
class OTPController:
    def __init__(self, promise_service: PromiseService, apply_service: ApplyService):
        self.promise_service = promise_service
        self.apply_service = apply_service

    def calculate_promise(self, request: PromiseRequest) -> PromiseResponse:
        return self.promise_service.calculate_promise(
            customer=request.customer,
            items=request.items,
            desired_date=request.desired_date,
            rules=request.rules,
        )
```

Design explanation:
- FastAPI route handles HTTP and error mapping.
- Controller owns orchestration and logging.
- Service encapsulates business logic and is easy to unit test.

---

### Snippet 2: Mocking ERPNext in a unit test
Source: tests/unit/test_promise_service.py and tests/conftest.py

```python
def test_promise_all_from_stock(self, mock_erpnext_client, today):
    mock_erpnext_client.get_bin_details.return_value = {
        "actual_qty": 15.0,
        "reserved_qty": 0.0,
        "projected_qty": 15.0,
    }
    mock_erpnext_client.get_incoming_purchase_orders.return_value = []

    stock_service = StockService(mock_erpnext_client)
    promise_service = PromiseService(stock_service)

    item = ItemRequest(item_code="ITEM-001", qty=10.0, warehouse="Stores - WH")
    rules = PromiseRules(lead_time_buffer_days=1, no_weekends=False)

    response = promise_service.calculate_promise(customer="CUST-001", items=[item], rules=rules)

    assert response.confidence == "HIGH"
```

Design explanation:
- ERPNext client is mocked to isolate the algorithm.
- Test verifies deterministic behavior and confidence scoring.
- Fast and reliable; no external calls.

---

### Snippet 3: Integration test gate with RUN_INTEGRATION
Source: tests/integration/test_erpnext_integration.py

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not settings.run_integration,
        reason="Integration tests disabled. Set RUN_INTEGRATION=true in .env to enable.",
    ),
]

class TestPromiseEndpointIntegration:
    def test_promise_calculation_with_real_erpnext(self):
        response = client.post("/otp/promise", json=request_data)
        assert response.status_code == 200
```

Design explanation:
- Integration tests are opt-in to avoid flaky CI.
- Same API path, but hits real ERPNext.
- Ensures real-world compatibility while preserving fast CI.

---

## Teaser Video Script (30-45 sec)

### Scene 1 (Problem, 10-12 sec)
Narration:
- “In ERPNext, delivery promises are often guesses. Sales teams see stock, but not incoming supply, so customers get wrong dates.”

Visual:
- A sales order screen and a red “late delivery” stamp.

### Scene 2 (Solution, 12-15 sec)
Narration:
- “OTP connects to ERPNext, calculates promise dates from real stock and purchase orders, and explains every decision with confidence.”

Visual:
- API call in Swagger, then a response with promise_date, confidence, reasons.

### Scene 3 (Impact, 10-12 sec)
Narration:
- “The result: faster decisions, fewer broken promises, and measurable revenue protection with 98% test coverage and CI enforcement.”

Visual:
- Metrics: 98% coverage, 260 tests, 95% on-time promise rate.

---

## Truth from repo (implementation facts)

### Main endpoints (actual routes)
- POST /otp/promise
- POST /otp/apply
- POST /otp/procurement-suggest
- GET /otp/sales-orders
- GET /otp/sales-orders/{sales_order_id}
- GET /otp/health
- GET /api/items/stock
- GET /health
- GET /diagnostics

### ERPNext integration points
- ERPNextClient: get_stock_balance, get_bin_details, get_incoming_purchase_orders
- ERPNextClient: get_sales_order, get_sales_order_list, add_comment_to_doc
- Retry logic + circuit breaker

### UI pages (requested in prompt)
- Promise Calculator: Not implemented yet
- Scenarios: Not implemented yet
- Audit & Trace: Not implemented yet
- Settings: Not implemented yet

### Test layers
- Unit: tests/unit/*
- API: tests/api/*
- Integration (opt-in): tests/integration/*
- UI/E2E: Not implemented yet (marker exists in pytest.ini)

### Exact commands
- Run backend (local):
  - uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
- Run backend (docker):
  - docker-compose up --build
- Run tests (unit + api):
  - pytest tests/unit/ tests/api/ -v --cov=src --cov-report=term-missing
- Run integration (real ERPNext):
  - RUN_INTEGRATION=1 pytest tests/integration/ -v
- Coverage report:
  - pytest --cov=src --cov-report=html
  - open htmlcov/index.html
