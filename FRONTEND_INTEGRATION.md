# Frontend Integration Guide

**ERPNext Order Promise Engine (OTP) Backend**  
Version: 0.1.0  
Last Updated: January 28, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Setup](#quick-setup)
4. [Environment Variables](#environment-variables)
5. [Running the Backend](#running-the-backend)
6. [CORS Configuration](#cors-configuration)
7. [Frontend Connection](#frontend-connection)
8. [Mock Mode](#mock-mode)
9. [Troubleshooting](#troubleshooting)
10. [Cross-Reference](#cross-reference)

---

## Overview

The ERPNext OTP backend is a FastAPI-based microservice that provides order promise calculation capabilities. It can run in two modes:

- **ERPNext Mode**: Connects to a live ERPNext instance for real data
- **Mock Mode**: Uses CSV files for testing without ERPNext

The frontend at `c:\Users\NofJawamis\Desktop\ERPNextNofUI\erpnextnofui` connects to this backend to calculate delivery promises and manage order fulfillment.

---

## Architecture

```
┌─────────────────────────────────────┐
│   Frontend (Next.js)                │
│   Port: 3000                        │
│   Location: ERPNextNofUI/           │
└────────────┬────────────────────────┘
             │ HTTP Requests
             ↓
┌─────────────────────────────────────┐
│   OTP Backend (FastAPI)             │
│   Port: 8001                        │
│   Location: ERPNextNof/             │
└────────────┬────────────────────────┘
             │ REST API (optional)
             ↓
┌─────────────────────────────────────┐
│   ERPNext Instance                  │
│   Port: 8080 (default)              │
│   - Stock data                      │
│   - Purchase Orders                 │
│   - Sales Orders                    │
└─────────────────────────────────────┘
```

**Key Points:**
- Frontend communicates with backend via REST API
- Backend can operate in mock mode without ERPNext
- CORS is configured to allow cross-origin requests

---

## Quick Setup

### Prerequisites

- Python 3.11 or higher
- pip or conda for package management
- (Optional) ERPNext instance running

### 1. Clone and Navigate

```bash
cd c:\Users\NofJawamis\Desktop\ERPNextNof
```

### 2. Create Virtual Environment

```bash
# Using venv
python -m venv .venv

# Activate on Windows
.venv\Scripts\activate

# Activate on Unix/macOS
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (see below)
```

---

## Environment Variables

The backend requires a `.env` file in the root directory. Here's what you need:

### Required for Frontend Integration

```ini
# === OTP Service Configuration ===
OTP_SERVICE_HOST=0.0.0.0
OTP_SERVICE_PORT=8001
OTP_SERVICE_ENV=development

# === Mock Mode (NO ERPNext needed) ===
USE_MOCK_SUPPLY=true
MOCK_DATA_FILE=data/Sales Invoice.csv

# === Business Rules Defaults ===
DEFAULT_WAREHOUSE=Stores - SD
NO_WEEKENDS=true
CUTOFF_TIME=14:00
TIMEZONE=UTC
LEAD_TIME_BUFFER_DAYS=1
PROCESSING_LEAD_TIME_DAYS_DEFAULT=1
```

### Optional for ERPNext Connection

```ini
# === ERPNext Configuration ===
# Only needed if USE_MOCK_SUPPLY=false
ERPNEXT_BASE_URL=http://localhost:8080
ERPNEXT_API_KEY=your_api_key_here
ERPNEXT_API_SECRET=your_api_secret_here
ERPNEXT_SITE_NAME=erpnext.localhost

# === Test Configuration ===
RUN_INTEGRATION=0
ERPNEXT_TEST_USERNAME=Administrator
ERPNEXT_TEST_PASSWORD=admin
```

### Frontend Environment Variables

Your frontend (`.env.local` in ERPNextNofUI) needs:

```ini
NEXT_PUBLIC_API_URL=http://localhost:8001
```

---

## Running the Backend

### Option 1: Development Mode (Recommended)

```bash
cd c:\Users\NofJawamis\Desktop\ERPNextNof

# Activate virtual environment
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Unix/macOS

# Run with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8001
```

**Output:**
```
INFO:     Started reloader process [12345]
INFO:     Starting OTP Service...
INFO:     Environment: development
INFO:     ERPNext URL: http://localhost:8080
INFO:     API Documentation: http://0.0.0.0:8001/docs
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Option 2: Docker Compose

```bash
cd c:\Users\NofJawamis\Desktop\ERPNextNof

# Build and start
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Option 3: Using start.sh Script

```bash
cd c:\Users\NofJawamis\Desktop\ERPNextNof

# Make executable (Unix/macOS)
chmod +x start.sh

# Run
./start.sh
```

### Verify Backend is Running

Open your browser or use curl:

```bash
# Health check
curl http://localhost:8001/health

# API documentation
open http://localhost:8001/docs
```

Expected health response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": false,
  "message": "OTP Service is operational (using mock supply data)"
}
```

---

## CORS Configuration

### Current Setup

The backend has **permissive CORS** enabled for development:

**Location:** `src/main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### ✅ Correctly Configured For Development

This setup allows your frontend at `http://localhost:3000` to make requests to `http://localhost:8001` without CORS errors.

### Production Recommendations

For production, restrict origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-frontend-domain.com",
        "https://app.your-company.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
```

Or use environment variable:

```python
import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # ... rest of config
)
```

---

## Frontend Connection

### API Client Setup

Your frontend should use the API at `http://localhost:8001`. Here's how to configure:

**File:** `erpnextnofui/src/lib/api/client.ts`

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export async function calculatePromise(request: PromiseRequest): Promise<PromiseResponse> {
  const response = await fetch(`${API_BASE_URL}/otp/promise`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
```

### Example Frontend Request

```typescript
const request = {
  customer: "CUST-001",
  items: [
    {
      item_code: "SKU005",
      qty: 10,
      warehouse: "Stores - SD"
    }
  ],
  desired_date: "2026-02-05",
  rules: {
    no_weekends: true,
    cutoff_time: "14:00",
    timezone: "UTC",
    lead_time_buffer_days: 1,
    processing_lead_time_days: 1
  }
};

const response = await fetch('http://localhost:8001/otp/promise', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(request)
});

const data = await response.json();
console.log('Promise Date:', data.promise_date);
console.log('Confidence:', data.confidence);
```

### Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check service status |
| `/otp/promise` | POST | Calculate promise date |
| `/otp/apply` | POST | Apply promise to Sales Order |
| `/otp/procurement-suggest` | POST | Create procurement suggestion |
| `/demo/invoices/summary` | GET | Get demo data summary |
| `/demo/invoices/all` | GET | Get all demo invoices |

See [API_CONTRACT.md](API_CONTRACT.md) for detailed endpoint documentation.

---

## Mock Mode

### What is Mock Mode?

Mock mode allows the backend to run **without a live ERPNext instance** by using CSV data files. This is ideal for:

- Frontend development
- Testing
- Demos
- CI/CD pipelines

### Enabling Mock Mode

**Set in `.env`:**

```ini
USE_MOCK_SUPPLY=true
MOCK_DATA_FILE=data/Sales Invoice.csv
```

### Mock Data Files

Located in `data/` directory:

```
data/
├── Sales Invoice.csv          # Primary demo data
├── Sales Invoice_Enriched.csv # Enriched with PO data
├── stock.csv                  # Mock inventory levels
└── purchase_orders.csv        # Mock incoming supply
```

### Mock Data Structure

**stock.csv:**
```csv
item_code,warehouse,actual_qty,reserved_qty,projected_qty
SKU005,Stores - SD,100,20,80
SKU008,Stores - SD,50,10,40
```

**purchase_orders.csv:**
```csv
po_id,item_code,qty,expected_date,warehouse
PO-00123,SKU005,50,2026-02-03,Stores - SD
PO-00124,SKU008,30,2026-02-05,Stores - SD
```

### When to Use Mock Mode

✅ **Use Mock Mode:**
- During frontend development
- When ERPNext is unavailable
- For automated testing
- For demos and presentations

❌ **Use ERPNext Mode:**
- Production deployment
- Real order processing
- Integration testing with live data
- When you need to write back to ERPNext

### Mock Mode Limitations

- No write-back to ERPNext (apply promise, create procurement)
- Static data (no real-time updates)
- Limited to predefined items in CSV files
- Health check shows `erpnext_connected: false`

---

## Troubleshooting

### Problem: Frontend Can't Connect to Backend

**Symptoms:**
- Network errors in browser console
- `ERR_CONNECTION_REFUSED`
- CORS errors

**Solutions:**

1. **Verify backend is running:**
   ```bash
   curl http://localhost:8001/health
   ```

2. **Check port 8001 is not blocked:**
   ```bash
   # Windows
   netstat -ano | findstr :8001
   
   # Unix/macOS
   lsof -i :8001
   ```

3. **Verify frontend API URL:**
   ```bash
   # In erpnextnofui/.env.local
   cat .env.local | grep API_URL
   ```

4. **Check firewall settings:**
   - Ensure port 8001 is allowed through Windows Firewall
   - Try `http://127.0.0.1:8001` instead of `localhost`

### Problem: CORS Errors

**Symptoms:**
- Browser console: "Access to fetch at '...' has been blocked by CORS policy"

**Solutions:**

1. **Verify CORS is enabled in backend:**
   ```bash
   curl -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: POST" \
        -X OPTIONS \
        http://localhost:8001/otp/promise
   ```

2. **Check CORS headers in response:**
   ```bash
   curl -v http://localhost:8001/health
   # Look for: Access-Control-Allow-Origin: *
   ```

3. **Restart backend after changing CORS config**

### Problem: Mock Data Not Loading

**Symptoms:**
- Empty responses
- "No data available" errors
- `Loaded 0 stock rows and 0 purchase orders`

**Solutions:**

1. **Verify data files exist:**
   ```bash
   ls data/
   # Should show: stock.csv, purchase_orders.csv, Sales Invoice.csv
   ```

2. **Check USE_MOCK_SUPPLY in .env:**
   ```bash
   cat .env | grep USE_MOCK_SUPPLY
   # Should be: USE_MOCK_SUPPLY=true
   ```

3. **Check file paths:**
   ```bash
   cat .env | grep MOCK_DATA_FILE
   # Should be: MOCK_DATA_FILE=data/Sales Invoice.csv
   ```

4. **Verify CSV format:**
   ```bash
   head -n 5 data/stock.csv
   # Should have headers: item_code,warehouse,actual_qty...
   ```

### Problem: Slow API Responses

**Symptoms:**
- Frontend takes >5 seconds to load
- Timeout errors

**Solutions:**

1. **Use mock mode for development:**
   ```ini
   USE_MOCK_SUPPLY=true
   ```

2. **Check ERPNext connection (if not in mock mode):**
   ```bash
   curl http://localhost:8001/health
   # Check erpnext_connected status
   ```

3. **Enable debug logging:**
   ```python
   # In src/main.py
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Monitor backend logs:**
   ```bash
   # Look for slow queries or connection timeouts
   tail -f server.log
   ```

### Problem: "Module Not Found" Errors

**Symptoms:**
- Import errors when starting backend
- `ModuleNotFoundError: No module named 'fastapi'`

**Solutions:**

1. **Verify virtual environment is activated:**
   ```bash
   which python  # Should show .venv/bin/python
   ```

2. **Reinstall dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Check Python version:**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

### Problem: Port 8001 Already in Use

**Symptoms:**
- `Address already in use` error
- Backend won't start

**Solutions:**

1. **Find process using port 8001:**
   ```bash
   # Windows
   netstat -ano | findstr :8001
   taskkill /PID <pid> /F
   
   # Unix/macOS
   lsof -ti:8001 | xargs kill -9
   ```

2. **Use a different port:**
   ```bash
   uvicorn src.main:app --reload --port 8002
   
   # Update frontend .env.local:
   # NEXT_PUBLIC_API_URL=http://localhost:8002
   ```

### Problem: ERPNext Connection Failed

**Symptoms:**
- Health check shows `erpnext_connected: false`
- "ERPNext service error" responses

**Solutions:**

1. **Verify ERPNext is running:**
   ```bash
   curl http://localhost:8080
   ```

2. **Check API credentials:**
   ```bash
   cat .env | grep ERPNEXT_API
   # Verify API_KEY and API_SECRET are correct
   ```

3. **Test ERPNext API directly:**
   ```bash
   curl -X GET "http://localhost:8080/api/resource/Item" \
        -H "Authorization: token <api_key>:<api_secret>"
   ```

4. **Switch to mock mode temporarily:**
   ```ini
   USE_MOCK_SUPPLY=true
   ```

### Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   tail -f server.log
   ```

2. **Enable debug mode:**
   ```ini
   OTP_SERVICE_ENV=development
   ```

3. **Run tests:**
   ```bash
   pytest tests/api/ -v
   ```

4. **Review documentation:**
   - [API_CONTRACT.md](API_CONTRACT.md) - API details
   - [README.md](README.md) - General setup
   - Frontend [INTEGRATION_GUIDE.md](../ERPNextNofUI/erpnextnofui/INTEGRATION_GUIDE.md)

---

## Cross-Reference

### Related Documentation

- **[API_CONTRACT.md](API_CONTRACT.md)** - Complete API endpoint documentation with schemas
- **[README.md](README.md)** - Project overview and quick start
- **[DEMO_DATA.md](DEMO_DATA.md)** - Mock data structure and demo endpoints
- **Frontend Integration Guide** - `c:\Users\NofJawamis\Desktop\ERPNextNofUI\erpnextnofui\INTEGRATION_GUIDE.md`

### Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI app entry point, CORS setup |
| `src/config.py` | Environment variable configuration |
| `src/routes/otp.py` | API endpoint definitions |
| `.env` | Environment configuration (create from `.env.example`) |
| `requirements.txt` | Python dependencies |
| `data/*.csv` | Mock data files |

### Testing Files

| File | Purpose |
|------|---------|
| `test_api.py` | Example API usage with requests |
| `tests/api/` | FastAPI test suite |
| `tests/integration/` | ERPNext integration tests |

---

## Performance Characteristics

### Mock Mode Response Times

- `/health`: ~5-10ms
- `/otp/promise`: ~20-50ms (single item)
- `/otp/promise`: ~50-100ms (multi-item)

### ERPNext Mode Response Times

- `/health`: ~50-100ms
- `/otp/promise`: ~200-500ms (depends on ERPNext)
- `/otp/apply`: ~500-1000ms (writes to ERPNext)

### Recommendations

- **Use mock mode** during frontend development for fast iteration
- **Use ERPNext mode** for integration testing and production
- **Cache promise calculations** on frontend when appropriate
- **Implement loading states** for API calls >200ms

---

## Next Steps

1. ✅ Verify backend is running: `curl http://localhost:8001/health`
2. ✅ Check frontend can connect: Open DevTools Network tab
3. ✅ Test promise calculation from frontend UI
4. ✅ Review [API_CONTRACT.md](API_CONTRACT.md) for detailed endpoint docs
5. ✅ Configure production CORS before deployment

---

**Last Updated:** January 28, 2026  
**Maintainer:** ERPNext OTP Team  
**Questions?** See troubleshooting section or check GitHub Issues
