# Unit Tests - Test Plan & Traceability Matrix

## Overview

Unit tests validate individual components in isolation with mocked dependencies. These tests run in ~10 seconds and form the foundation of code quality.

**Scope:** Core business logic, utilities, and services  
**Total Tests:** 165  
**Coverage:** 92%  
**Dependencies Mocked:** ERPNext API, database queries  

---

## Test Categories & Traceability

### 1. Promise Service (Core Algorithm)

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestPromiseCalculation` | `test_promise_calculation_basic` | Calculate promise date from stock + PO | `promise_service.py` | ✅ |
| `TestPromiseCalculation` | `test_promise_calculation_with_shortage` | Handle shortage scenarios | `promise_service.py` | ✅ |
| `TestPromiseCalculation` | `test_confidence_high_from_stock` | HIGH confidence when 100% from stock | `promise_service.py` | ✅ |
| `TestPromiseCalculation` | `test_confidence_medium_stock_and_po` | MEDIUM confidence for stock + PO mix | `promise_service.py` | ✅ |
| `TestPromiseCalculation` | `test_confidence_low_late_po` | LOW confidence for late POs (>7 days) | `promise_service.py` | ✅ |
| `TestPromiseCalculationWithRules` | `test_no_weekends_skips_saturday` | Skip weekends (exclude Saturday/Sunday) | `promise_service.py` | ✅ |
| `TestPromiseCalculationWithRules` | `test_no_weekends_adjusts_to_monday` | Adjust to next Monday if needed | `promise_service.py` | ✅ |
| `TestPromiseCalculationWithRules` | `test_cutoff_time_adds_day` | Add 1 day if past cutoff time | `promise_service.py` | ✅ |
| `TestPromiseCalculationWithRules` | `test_lead_time_buffer` | Add lead time buffer days | `promise_service.py` | ✅ |
| `TestPromiseCalculationWithWarehouses` | `test_sellable_warehouse_available` | Fetch stock from sellable warehouse | `promise_service.py` | ✅ |
| `TestPromiseCalculationWithWarehouses` | `test_promise_date_never_weekend` | Promise date never lands on weekend | `promise_service.py` | ✅ |
| `TestPromiseExplanations` | `test_reasons_include_all_sources` | Reasons explain each fulfillment source | `promise_service.py` | ✅ |
| `TestPromiseExplanations` | `test_blockers_identify_shortages` | Blockers list shortages and late POs | `promise_service.py` | ✅ |
| `TestPromiseExplanations` | `test_options_suggest_alternatives` | Options suggest alternate warehouses | `promise_service.py` | ✅ |

### 2. Stock Service

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestStockService` | `test_fetch_stock_basic` | Query item stock from warehouse | `stock_service.py` | ✅ |
| `TestStockService` | `test_fetch_stock_multiple_items` | Batch query multiple items | `stock_service.py` | ✅ |
| `TestStockService` | `test_stock_reserved_calculation` | Calculate reserved qty (SO - delivered) | `stock_service.py` | ✅ |
| `TestStockService` | `test_stock_available_is_actual_minus_reserved` | Available = actual - reserved | `stock_service.py` | ✅ |
| `TestStockService` | `test_fetch_stock_error_handling` | Handle ERPNext errors gracefully | `stock_service.py` | ✅ |

### 3. Apply Service (Write-Back)

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestApplyService` | `test_apply_promise_as_comment` | Write promise date as comment to SO | `apply_service.py` | ✅ |
| `TestApplyService` | `test_apply_promise_to_custom_field` | Write promise to custom field if exists | `apply_service.py` | ✅ |
| `TestApplyService` | `test_apply_with_confidence_level` | Include confidence level in write-back | `apply_service.py` | ✅ |
| `TestApplyService` | `test_apply_error_recovery` | Continue on individual SO errors | `apply_service.py` | ✅ |

### 4. ERPNext Client

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestERPNextClient` | `test_get_doctype_basic` | Query ERPNext via GET method | `erpnext_client.py` | ✅ |
| `TestERPNextClient` | `test_get_doctype_with_filters` | Apply filters in query | `erpnext_client.py` | ✅ |
| `TestERPNextClient` | `test_get_doctype_pagination` | Support offset/limit pagination | `erpnext_client.py` | ✅ |
| `TestERPNextClient` | `test_auth_header_format` | Use correct Basic Auth header | `erpnext_client.py` | ✅ |
| `TestERPNextClient` | `test_404_error_handling` | Raise appropriate 404 error | `erpnext_client.py` | ✅ |
| `TestERPNextClient` | `test_5xx_error_handling` | Raise appropriate 5xx error | `erpnext_client.py` | ✅ |

### 5. Request Models (Validation)

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestItemRequest` | `test_item_request_valid` | Valid item request passes | `request_models.py` | ✅ |
| `TestItemRequest` | `test_item_request_missing_code` | Reject missing item_code | `request_models.py` | ✅ |
| `TestItemRequest` | `test_item_request_zero_qty` | Reject zero/negative qty | `request_models.py` | ✅ |
| `TestPromiseRequest` | `test_promise_request_valid` | Valid promise request passes | `request_models.py` | ✅ |
| `TestPromiseRequest` | `test_promise_request_missing_customer` | Reject missing customer | `request_models.py` | ✅ |
| `TestPromiseRequest` | `test_promise_request_empty_items` | Reject empty items list | `request_models.py` | ✅ |
| `TestPromiseRequest` | `test_rules_optional_with_defaults` | Rules default if not provided | `request_models.py` | ✅ |

### 6. Calendar & Workweek

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestCalendarWorkweek` | `test_weekday_not_skipped` | Weekdays pass through | `calendar_workweek.py` | ✅ |
| `TestCalendarWorkweek` | `test_saturday_skipped` | Skip Saturday | `calendar_workweek.py` | ✅ |
| `TestCalendarWorkweek` | `test_sunday_skipped` | Skip Sunday | `calendar_workweek.py` | ✅ |
| `TestCalendarWorkweek` | `test_multiple_skips` | Skip across multiple days | `calendar_workweek.py` | ✅ |

### 7. Configuration & Environment

| Test Class | Test Method | Requirement | Component | Status |
|---|---|---|---|---|
| `TestConfig` | `test_config_loads_from_env` | Load settings from .env | `config.py` | ✅ |
| `TestConfig` | `test_config_defaults` | Use defaults if env vars missing | `config.py` | ✅ |
| `TestConfig` | `test_config_type_conversion` | Convert env string to correct types | `config.py` | ✅ |

---

## ✅ Success Criteria

**Test Execution:**
- ✅ All 165 unit tests pass
- ✅ 0 test failures, 0 skipped tests
- ✅ Execution time < 15 seconds
- ✅ No flaky/non-deterministic tests

**Code Coverage:**
- ✅ Minimum 90% line coverage
- ✅ Minimum 85% branch coverage
- ✅ All public functions tested
- ✅ All error paths tested

**Code Quality:**
- ✅ All tests have docstrings
- ✅ Proper setup/teardown in each test

**Acceptance Criteria:**
| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Pass Rate | 100% | 100% | ✅ |
| Line Coverage | 90% | 92% | ✅ |
| Execution Time | <15s | ~10s | ✅ |
| Flaky Tests | 0 | 0 | ✅ |

---

## Test Execution

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test class
pytest tests/unit/test_promise_service.py::TestPromiseCalculation -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=term-missing

# Run fast (no coverage)
pytest tests/unit/ -v --tb=short
```

---

## Test Quality Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Line Coverage | >90% | 92% |
| Branch Coverage | >85% | 88% |
| Test Execution Time | <15s | ~10s |
| Failed Tests | 0 | 0 ✅ |

---

## Maintenance & Review Schedule

- **Weekly:** Review test failures in CI/CD logs
- **Monthly:** Update tests after new features
- **Quarterly:** Coverage analysis and dead code removal
