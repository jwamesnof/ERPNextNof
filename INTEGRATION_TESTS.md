# Integration Tests

This guide explains how to run the integration tests for this project.

## What these tests do
The integration tests call a real ERPNext instance to verify:
- Item and stock retrieval
- Warehouse behavior
- Promise date calculations
- Purchase order lookups

These tests are skipped unless `RUN_INTEGRATION=1` is set.

---

## Option A: Run locally (recommended for development)

### 1) Ensure ERPNext is reachable
- Use your real ERPNext (trial/demo or production)
- Example base URL:
  - `https://your-company.frappe.cloud`
  - or `http://localhost:8080`

### 2) Set environment variables
Set the following values in your shell:
- `RUN_INTEGRATION=1`
- `ERPNEXT_BASE_URL=<your ERPNext base URL>`
- `ERPNEXT_API_KEY=<your ERPNext API key>`
- `ERPNEXT_API_SECRET=<your ERPNext API secret>`

### 3) Run the tests
Run only integration tests:
- `pytest tests/integration/ -v --tb=short`

---

## Option B: Run in GitHub Actions (manual workflow)

### 1) Add repository secrets
In your GitHub repo:
- Settings → Secrets and variables → Actions → New repository secret

Add these secrets:
- `ERPNEXT_BASE_URL`
- `ERPNEXT_API_KEY`
- `ERPNEXT_API_SECRET`

### 2) Trigger the workflow
- Open GitHub → Actions
- Select **Manual Integration Tests**
- Click **Run workflow**

This uses `.github/workflows/integration.yml` and runs against your real ERPNext instance.

---

## Notes
- Integration tests require a real ERPNext server.
- The CI workflow (`.github/workflows/ci.yml`) runs unit + API tests only.
- If you change ERPNext credentials, update GitHub Secrets and local environment variables.
