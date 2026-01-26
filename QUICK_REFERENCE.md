# OTP Service - Quick Reference Card

## 🎯 What is OTP?
**Order Promise Engine** - Calculates realistic delivery dates for ERPNext Sales Orders based on stock, incoming POs, and business rules.

## 🚀 Quick Start

```bash
# Clone & setup
git clone <repo-url> ERPNextNof
cd ERPNextNof
cp .env.example .env
# Edit .env with your ERPNext credentials

# Option 1: Docker (recommended)
docker-compose up --build

# Option 2: Local
./start.sh

# API docs → http://localhost:8001/docs
```

## 📡 API Endpoints

### Calculate Promise
```bash
POST /otp/promise
{
  "customer": "CUST-001",
  "items": [{"item_code": "ITEM-001", "qty": 10}],
  "rules": {"no_weekends": true, "cutoff_time": "14:00"}
}
→ Returns: promise_date, confidence, plan, reasons, options
```

### Apply Promise
```bash
POST /otp/apply
{
  "sales_order_id": "SO-00456",
  "promise_date": "2026-02-05",
  "confidence": "MEDIUM",
  "action": "both"
}
→ Adds comment + updates custom field in ERPNext
```

### Create Procurement
```bash
POST /otp/procurement-suggest
{
  "items": [{
    "item_code": "ITEM-001",
    "qty_needed": 5,
    "required_by": "2026-02-03",
    "reason": "SO-00456"
  }],
  "suggestion_type": "material_request"
}
→ Creates Material Request in ERPNext
```

## 🧪 Testing

```bash
# Unit tests (fast)
pytest tests/unit/ -v

# API tests
pytest tests/api/ -v

# Integration (needs ERPNext)
RUN_INTEGRATION=1 pytest tests/integration/ -v

# E2E UI tests (needs Playwright)
playwright install chromium
pytest tests/e2e/ -v
```

## 🔧 Configuration (.env)

```bash
# ERPNext
ERPNEXT_BASE_URL=http://localhost:8080
ERPNEXT_API_KEY=your_key
ERPNEXT_API_SECRET=your_secret

# Business Rules
DEFAULT_WAREHOUSE=Stores - WH
NO_WEEKENDS=true
CUTOFF_TIME=14:00
LEAD_TIME_BUFFER_DAYS=1
```

## 📊 Confidence Levels

| Level | Criteria |
|-------|----------|
| **HIGH** | 100% from available stock |
| **MEDIUM** | Mix of stock + near POs (<7 days) |
| **LOW** | Late POs (>7 days) or shortages |

## 🏗️ Architecture

```
Client → FastAPI → Controllers → Services → ERPNext Client → ERPNext
                                    ↓
                            Promise Algorithm
                            Stock Service
                            Apply Service
```

## 📁 Project Structure

```
ERPNextNof/
├── src/
│   ├── main.py                 # FastAPI app
│   ├── clients/                # ERPNext HTTP client
│   ├── services/               # Business logic
│   ├── controllers/            # Request handlers
│   ├── routes/                 # API endpoints
│   └── models/                 # Pydantic schemas
├── tests/
│   ├── unit/                   # Algorithm tests
│   ├── api/                    # Endpoint tests
│   ├── integration/            # ERPNext integration
│   └── e2e/                    # Playwright UI tests
├── .github/workflows/          # CI/CD
├── docker-compose.yml
└── README.md
```

## 🎨 Algorithm Flow

1. **Gather Sources**: Check stock → Query POs → Build fulfillment plan
2. **Apply Rules**: Add buffer → Check cutoff → Skip weekends
3. **Calculate Confidence**: Based on fulfillment sources
4. **Generate Explanations**: Reasons, blockers, options

## 🔍 Monitoring

- **Health Check**: `GET /health`
- **Logs**: stdout (JSON in production)
- **Coverage**: 73% (61% unit, 93% core algorithm)

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Check ERPNEXT_BASE_URL in .env |
| Auth failed | Verify API_KEY and API_SECRET |
| Import errors | Run `pip install -r requirements.txt` |
| Tests fail | Ensure ERPNext running for integration tests |

## 📞 Support

- **Docs**: http://localhost:8001/docs (when running)
- **Tests**: `pytest --help`
- **Issues**: GitHub Issues

## 🗺️ Roadmap

- [x] MVP: Stock + PO promise calculation
- [x] Write-back to Sales Orders
- [x] Material Request creation
- [ ] Multi-warehouse optimization
- [ ] Production planning integration
- [ ] Shipping carrier APIs
- [ ] Real-time stock updates

---

**Version**: 0.1.0 (MVP)  
**Python**: 3.11+  
**Framework**: FastAPI 0.109+  
**License**: MIT
