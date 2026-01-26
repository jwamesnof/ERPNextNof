# Next Steps - Order Promise Engine Implementation

## ✅ Completed Steps

### 1. Environment Configuration
- ✅ `.env` file created with ERPNext connection settings
- ✅ Default business rules configured:
  - No weekends: `true`
  - Cutoff time: `14:00`
  - Timezone: `UTC`
  - Lead time buffer: `1 day`
  - Default warehouse: `Stores - WH`

### 2. Application Started
- ✅ OTP Service running on `http://0.0.0.0:8001`
- ✅ Development mode with auto-reload enabled
- ✅ API documentation available at `/docs`

### 3. Health Endpoint Added
- ✅ Added `/otp/health` endpoint
- ✅ Checks ERPNext connectivity
- ✅ Returns service version and status

### 4. API Testing
- ✅ Promise calculation endpoint tested
- ✅ Returns complete response with:
  - Promise date
  - Confidence level
  - Fulfillment plan
  - Reasons & blockers
  - Suggestions

**Example Response**:
```json
{
  "promise_date": "2026-01-27",
  "confidence": "LOW",
  "plan": [...],
  "reasons": [...],
  "blockers": ["Item ITEM-001: Shortage of 10.0 units"],
  "options": [...]
}
```

---

## 📋 Remaining Steps

### Step 1: Set Up ERPNext Instance
**Objective**: Connect the OTP service to a working ERPNext installation

**Actions**:
1. Ensure ERPNext is running on `http://localhost:8080`
2. Create an API user in ERPNext:
   - Go to Setup → User
   - Create new user with API access
   - Generate API Key and Secret
3. Update `.env` with credentials:
   ```
   ERPNEXT_API_KEY=your_api_key
   ERPNEXT_API_SECRET=your_api_secret
   ```
4. Test connection:
   ```bash
   curl http://localhost:8001/otp/health
   # Should show erpnext_connected: true
   ```

### Step 2: Create Custom Fields in ERPNext
**Objective**: Store OTP results back in Sales Order

**Custom Fields to Create**:
1. **custom_otp_promise_date**
   - DocType: Sales Order
   - Field Type: Date
   - Label: OTP Promise Date
   
2. **custom_otp_confidence**
   - DocType: Sales Order
   - Field Type: Link (or Select)
   - Options: HIGH, MEDIUM, LOW
   - Label: OTP Confidence

**Steps**:
1. In ERPNext, go to Customize Form → Sales Order
2. Add custom fields (or use Developer console)
3. Save

**Verification**:
```bash
curl -X POST http://localhost:8001/otp/apply \
  -H "Content-Type: application/json" \
  -d '{
    "sales_order_id": "SO-00001",
    "promise_date": "2026-02-15",
    "confidence": "HIGH",
    "action": "both"
  }'
```

### Step 3: Test Promise Calculation with Real Data
**Objective**: Verify calculation with actual ERPNext data

**Test Scenarios**:

#### Scenario A: All from Stock
```json
POST /otp/promise
{
  "customer": "CUST-001",
  "items": [
    {
      "item_code": "ITEM-WITH-STOCK",
      "qty": 5.0,
      "warehouse": "Stores - WH"
    }
  ]
}
```
**Expected**: HIGH confidence, promise_date = today + 1 day (buffer)

#### Scenario B: Partial Stock + PO
```json
POST /otp/promise
{
  "customer": "CUST-001",
  "items": [
    {
      "item_code": "ITEM-PARTIAL",
      "qty": 20.0
    }
  ]
}
```
**Expected**: MEDIUM confidence, promise_date based on PO delivery

#### Scenario C: Weekend Handling
```json
POST /otp/promise
{
  "customer": "CUST-001",
  "items": [
    {
      "item_code": "ITEM-001",
      "qty": 10.0
    }
  ],
  "rules": {
    "no_weekends": true
  }
}
```
**Expected**: If calculated date is Saturday/Sunday, moves to next Monday

### Step 4: Test Write-Back to ERPNext
**Objective**: Verify data is saved back to Sales Order

**Test**:
```bash
# 1. Calculate promise
PROMISE=$(curl -s -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [{"item_code": "ITEM-001", "qty": 10.0}]
  }')

# 2. Extract promise_date from response
PROMISE_DATE=$(echo $PROMISE | jq -r '.promise_date')

# 3. Apply to Sales Order
curl -X POST http://localhost:8001/otp/apply \
  -H "Content-Type: application/json" \
  -d "{
    \"sales_order_id\": \"SO-00001\",
    \"promise_date\": \"$PROMISE_DATE\",
    \"confidence\": \"HIGH\",
    \"action\": \"both\"
  }"
```

**Verification** in ERPNext:
- Check SO comment: Should have "Order Promise Date: ..."
- Check custom field: Should show calculated date & confidence

### Step 5: Test Procurement Suggestion
**Objective**: Verify Material Request creation

**Test**:
```bash
curl -X POST http://localhost:8001/otp/procurement-suggest \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "item_code": "ITEM-001",
        "qty_needed": 5.0,
        "required_by": "2026-02-01",
        "reason": "Order promise fulfillment"
      }
    ],
    "suggestion_type": "Material Request",
    "priority": "High"
  }'
```

**Expected Response**:
```json
{
  "status": "success",
  "suggestion_id": "MR-00123",
  "type": "Material Request",
  "items_count": 1,
  "erpnext_url": "http://localhost:8080/app/material-request/MR-00123"
}
```

### Step 6: Run Full Test Suite
**Objective**: Validate all functionality

```bash
# Unit tests (no ERPNext needed)
pytest tests/unit/ -v

# All tests (requires ERPNext)
pytest -v

# Specific test
pytest tests/unit/test_promise_service.py -v
```

**Expected**: All tests pass

### Step 7: Configure for Production
**Objective**: Prepare for deployment

**Actions**:
1. Update `.env`:
   ```
   OTP_SERVICE_ENV=production  # Disable auto-reload
   ```

2. Update ERPNext connection:
   ```
   ERPNEXT_BASE_URL=https://your-erpnext.com  # Use HTTPS
   ```

3. Consider Docker deployment:
   ```bash
   docker build -t otp-service .
   docker run -p 8001:8001 --env-file .env otp-service
   ```

4. Add monitoring & logging:
   - Configure log rotation
   - Set up error alerts
   - Monitor API response times

---

## 🎯 Success Criteria

- [ ] ERPNext connectivity: `/otp/health` returns `erpnext_connected: true`
- [ ] Promise calculation: Returns valid response with all required fields
- [ ] Write-back: Comments appear on Sales Orders, custom fields populated
- [ ] Business rules: Weekend handling & cutoff times work correctly
- [ ] Error handling: Gracefully handles ERPNext errors without crashing
- [ ] Tests: All unit tests pass
- [ ] API docs: Swagger UI accessible at `/docs`

---

## 📚 API Reference

### Calculate Promise
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
  "rules": {  # optional
    "no_weekends": true,
    "cutoff_time": "14:00",
    "timezone": "UTC",
    "lead_time_buffer_days": 1
  }
}

Response: PromiseResponse
```

### Apply Promise
```
POST /otp/apply
Content-Type: application/json

Request:
{
  "sales_order_id": "SO-00123",
  "promise_date": "2026-02-15",
  "confidence": "HIGH",  # HIGH | MEDIUM | LOW
  "action": "both",  # "add_comment" | "set_custom_field" | "both"
  "comment_text": "Custom comment"  # optional
}

Response: ApplyPromiseResponse
```

### Create Procurement Suggestion
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
      "reason": "Order promise"  # optional
    }
  ],
  "suggestion_type": "Material Request",  # or "Purchase Order"
  "priority": "High"  # High | Medium | Low
}

Response: ProcurementSuggestionResponse
```

### Health Check
```
GET /otp/health

Response: HealthResponse
{
  "status": "healthy",
  "version": "0.1.0",
  "erpnext_connected": true,
  "message": null
}
```

---

## 🚀 Quick Start

### 1. Start the service
```bash
cd /c/Users/NofJawamis/Desktop/ERPNextNof
python -m src.main
```

### 2. Access documentation
```
http://localhost:8001/docs
```

### 3. Test an endpoint
```bash
curl -X POST http://localhost:8001/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "items": [{"item_code": "ITEM-001", "qty": 10.0}]
  }' | python -m json.tool
```

---

## 📞 Troubleshooting

### ERPNext Connection Fails
- Check `ERPNEXT_BASE_URL` in `.env`
- Verify ERPNext is running: `curl http://localhost:8080`
- Check API key/secret are valid

### Promises Show LOW Confidence
- Verify test data exists in ERPNext (items, stock, POs)
- Check warehouse name matches `DEFAULT_WAREHOUSE`
- Review blockers in response for specific issues

### Custom Fields Not Updated
- Verify fields exist in ERPNext: `custom_otp_promise_date`, `custom_otp_confidence`
- Check API user has permission to update Sales Orders
- Review logs for update errors

### Application Won't Start
- Check `.env` file permissions
- Verify Python 3.8+ installed
- Try: `pip install -r requirements.txt --upgrade`

---

**Status**: Ready to proceed with ERPNext integration  
**Next Action**: Set up ERPNext API credentials
