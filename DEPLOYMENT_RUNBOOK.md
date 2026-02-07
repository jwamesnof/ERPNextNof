# 🚀 Production Deployment Runbook

## Overview

This runbook provides step-by-step instructions for deploying the **Order Promise Engine (OTP)** to production, from development to live operations.

---

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Methods](#deployment-methods)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Rollback Procedures](#rollback-procedures)
8. [Operations Guide](#operations-guide)
9. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### Code Readiness

```bash
# 1. Run all checks
./scripts/pre-deploy.sh

# 2. Tests pass
pytest tests/ -v --tb=short

# 3. Coverage meets target
pytest tests/ --cov=src --cov-report=term-missing
# Should show >= 80% coverage

# 4. Linting passes
black src/ --check
pylint src/ --fail-under=8.0
mypy src/ --strict

# 5. SAST scan (security)
bandit -r src/

# 6. Build & test Docker image
docker build -t otp:latest .
docker run -it otp:latest pytest tests/

✅ Code ready
```

### Infrastructure Readiness

```bash
# 1. ERPNext connectivity
curl -H "Authorization: Bearer {token}" \
  https://erpnext-instance.com/api/method/ping

# 2. Database connectivity (if using persistence)
mysql -h db-host -u user -p -e "SELECT 1"

# 3. Secrets available
aws ssm get-parameter --name /otp/erpnext_api_key

# 4. Load balancer configured
aws elbv2 describe-load-balancers

# 5. SSL certificates valid
openssl s_client -connect erpnext-instance.com:443

✅ Infrastructure ready
```

### Environmental Readiness

```bash
# 1. Create/verify .env file (production)
ERPNEXT_BASE_URL=https://erpnext.company.com
ERPNEXT_API_KEY=your-api-key
ERPNEXT_API_SECRET=your-api-secret
LOG_LEVEL=INFO
REQUEST_TIMEOUT=15

# 2. Create log directory
mkdir -p /var/log/otp/
chmod 755 /var/log/otp/

# 3. Create backup location
mkdir -p /backups/otp/
chmod 755 /backups/otp/

✅ Environment ready
```

---

## Deployment Methods

### Method 1: Docker Compose (Small Deployments)

**Use When**: Single server, < 100 RPS

```bash
# 1. Clone repository
git clone https://github.com/company/otp.git
cd otp

# 2. Prepare environment
cp .env.example .env.prod
# Edit .env.prod with production credentials

# 3. Build images
docker-compose -f docker-compose.yml build

# 4. Start services
docker-compose -f docker-compose.yml up -d

# 5. Verify
curl http://localhost:8001/health
# Should return: {"status": "healthy"}

# 6. Check logs
docker-compose logs -f otp

# Graceful shutdown
docker-compose down
```

### Method 2: Kubernetes (Large Deployments)

**Use When**: Multi-server, > 100 RPS, need auto-scaling

See [Kubernetes Deployment](#kubernetes-deployment) section below.

### Method 3: Manual Server Deployment

**Use When**: Legacy systems without containerization

```bash
# 1. SSH to production server
ssh otp-prod-01.company.com

# 2. Create application directory
sudo mkdir -p /opt/otp
sudo chown $USER:$USER /opt/otp

# 3. Deploy code
cd /opt/otp
git clone https://github.com/company/otp.git .
git checkout main

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Setup systemd service
sudo cp deployment/systemd/otp.service /etc/systemd/system/
sudo systemctl daemon-reload

# 7. Start service
sudo systemctl start otp
sudo systemctl enable otp  # Auto-start on reboot

# 8. Verify
curl http://localhost:8001/health
sudo systemctl status otp
```

---

## Docker Deployment

### Building the Image

```bash
# Build with version tag
docker build -t otp:v0.1.0 .

# Build with multiple tags
docker build -t otp:v0.1.0 -t otp:latest .

# Push to registry
docker tag otp:v0.1.0 registry.company.com/otp:v0.1.0
docker push registry.company.com/otp:v0.1.0
```

### Docker Compose Configuration

```yaml
# docker-compose.yml (production)
version: '3.8'

services:
  otp:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: otp-service
    ports:
      - "8001:8001"
    environment:
      ERPNEXT_BASE_URL: ${ERPNEXT_BASE_URL}
      ERPNEXT_API_KEY: ${ERPNEXT_API_KEY}
      ERPNEXT_API_SECRET: ${ERPNEXT_API_SECRET}
      LOG_LEVEL: INFO
    volumes:
      - ./logs:/app/logs
      - /var/log/otp:/var/log/otp
    restart: unless-stopped
    networks:
      - otp-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Optional: Reverse proxy
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx/nginx.conf:/etc/nginx/nginx.conf
      - /etc/ssl/certs:/etc/ssl/certs
    depends_on:
      - otp
    networks:
      - otp-network

networks:
  otp-network:
    driver: bridge
```

### Health Checks

```dockerfile
# In Dockerfile:
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1
```

---

## Kubernetes Deployment

### Prerequisites

```bash
# 1. Cluster access
kubectl cluster-info

# 2. Namespace created
kubectl create namespace otp
kubectl config set-context --current --namespace=otp

# 3. Secrets configured
kubectl create secret generic otp-secrets \
  --from-literal=ERPNEXT_API_KEY=xxx \
  --from-literal=ERPNEXT_API_SECRET=xxx \
  -n otp

✅ Ready for deployment
```

### Kubernetes Manifests

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otp
  namespace: otp
spec:
  replicas: 3  # Start with 3 instances
  selector:
    matchLabels:
      app: otp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: otp
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8001"
    spec:
      containers:
      - name: otp
        image: registry.company.com/otp:v0.1.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8001
          name: http
        env:
        - name: ERPNEXT_BASE_URL
          value: https://erpnext.company.com
        - name: ERPNEXT_API_KEY
          valueFrom:
            secretKeyRef:
              name: otp-secrets
              key: ERPNEXT_API_KEY
        - name: ERPNEXT_API_SECRET
          valueFrom:
            secretKeyRef:
              name: otp-secrets
              key: ERPNEXT_API_SECRET
        - name: LOG_LEVEL
          value: INFO
        
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 40
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 20
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      
      volumes:
      - name: logs
        emptyDir: {}
      
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - otp
              topologyKey: kubernetes.io/hostname

---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: otp
  namespace: otp
spec:
  type: ClusterIP
  selector:
    app: otp
  ports:
  - port: 8001
    targetPort: 8001
    name: http

---
# hpa.yaml (Auto-scaling)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: otp-hpa
  namespace: otp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: otp
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deployment Commands

```bash
# 1. Apply manifests
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml

# 2. Verify pods are running
kubectl get pods -n otp
# Expected: 3 pods in Running state

# 3. Check events
kubectl describe deployment otp -n otp

# 4. View logs
kubectl logs -f deployment/otp -n otp

# 5. Port forward for testing
kubectl port-forward svc/otp 8001:8001 -n otp

# 6. Verify health
curl http://localhost:8001/health
```

---

## Post-Deployment Verification

### Immediate Checks (5 mins)

```bash
# 1. Service is up
curl -I http://otp-service/health
# Expected: 200 OK

# 2. Docker logs show no errors
docker logs otp-service | tail -20
# Should show: "Uvicorn running on 0.0.0.0:8001"

# 3. ERPNext connectivity works
curl -X POST http://otp-service/otp/promise \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "TEST",
    "items": [{"item_code": "TEST-001", "qty": 1, "warehouse": "Stores"}]
  }'
# Should return valid response (even if item doesn't exist)

# 4. Metrics available
curl http://otp-service/metrics
# Should return Prometheus metrics
```

### Functional Tests (1 hour)

```bash
# 1. Run integration tests against production
RUN_INTEGRATION=1 pytest tests/integration/ -v

# 2. Test real sales orders
# Use sample orders from testing account

# 3. Verify response times
# Should be < 200ms under normal load

# 4. Check error handling
# Test with invalid item codes, missing warehouses
# Should return 404 without crashing
```

### Load Testing (2 hours)

```bash
# 1. Gradual load increase
k6 run deployment/k6-test.js \
  --vus 10 \
  --duration 5m

# 2. Monitor metrics
# CPU usage should be < 50%
# Memory should be stable
# Response times should be < 150ms P95

# 3. Stress test
k6 run deployment/k6-test.js \
  --vus 100 \
  --duration 10m

# 4. Monitor during stress
# Should handle 500+ RPS
# P99 should be < 500ms
# Error rate should be 0%
```

---

## Monitoring & Alerting

### Key Metrics Dashboard

```
Dashboard: OTP Service Health

Metrics to Display:
├─ Request Rate (RPS)
│  └─ Target: 100-200 RPS
├─ Response Time (P50, P95, P99)
│  └─ Target: P95 < 150ms
├─ Error Rate (%)
│  └─ Target: < 1%
├─ CPU Usage (%)
│  └─ Target: < 70%
├─ Memory Usage (MB)
│  └─ Target: < 600MB
├─ ERPNext Connection Status
│  └─ Target: Connected
└─ Pod Restarts
   └─ Target: 0
```

### Alert Rules

```yaml
# prometheus-rules.yaml
groups:
- name: otp-service
  interval: 30s
  rules:
  - alert: OTPHighResponseTime
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 0.15
    for: 5m
    annotations:
      summary: "OTP P95 response time > 150ms"
  
  - alert: OTPHighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[1m]) > 0.01
    for: 2m
    annotations:
      summary: "OTP error rate > 1%"
  
  - alert: OTPHighCPU
    expr: container_cpu_usage_seconds_total > 0.7
    for: 5m
    annotations:
      summary: "OTP CPU usage > 70%"
  
  - alert: OTPHighMemory
    expr: container_memory_usage_bytes / 1024 / 1024 / 1024 > 0.6
    for: 5m
    annotations:
      summary: "OTP memory usage > 600MB"
  
  - alert: ERPNextUnavailable
    expr: erpnext_connection_status == 0
    for: 1m
    annotations:
      summary: "ERPNext unavailable"
```

### Log Aggregation

```bash
# View structured logs
kubectl logs -f deployment/otp -n otp | jq .

# Example structured log:
{
  "timestamp": "2026-02-07T10:30:00Z",
  "level": "INFO",
  "message": "Promise calculated",
  "request_id": "abc-123",
  "customer": "CUST-001",
  "promise_date": "2026-02-10",
  "confidence": "HIGH",
  "duration_ms": 85
}
```

---

## Rollback Procedures

### Scenario 1: Rollback to Previous Version

```bash
# 1. Check current rollout
kubectl rollout history deployment/otp -n otp

# 2. Identify previous version
REVISION=1  # If current is 2

# 3. Rollback
kubectl rollout undo deployment/otp --to-revision=$REVISION -n otp

# 4. Verify
kubectl get pods -n otp
kubectl logs -f deployment/otp -n otp

# 5. Confirm health
curl http://otp-service/health
```

### Scenario 2: Immediate Rollback (Issues Detected)

```bash
# 1. Scale down current version
kubectl scale deployment otp --replicas=0 -n otp

# 2. Update image to last known-good version
kubectl set image deployment/otp \
  otp=registry.company.com/otp:v0.0.9 \
  -n otp

# 3. Scale back up
kubectl scale deployment otp --replicas=3 -n otp

# 4. Verify
kubectl rollout status deployment/otp -n otp
```

### Scenario 3: Database Rollback

If database migrations need rollback:

```bash
# 1. Identify current schema version
alembic current

# 2. Downgrade to previous version
alembic downgrade -1

# 3. Verify
alembic current

# 4. Restart services
kubectl rollout restart deployment/otp -n otp
```

---

## Operations Guide

### Daily Operations

```bash
# Morning check
kubectl get pods -n otp  # Verify all running
kubectl top pods -n otp  # Check resource usage
curl http://otp-service/health  # Verify connectivity

# Log monitoring
# Check for ERROR and CRITICAL logs in last 24h
kubectl logs --since=24h deployment/otp -n otp | grep -i error

# Metrics check
# Verify no alerts firing in Prometheus
```

### Weekly Maintenance

```bash
# 1. Update dependencies
pip install --upgrade -r requirements.txt
# Commit and tag new version
git tag v0.1.1
git push --tags

# 2. Performance review
# Check Grafana dashboards for trends
# Identify slow queries or high latency

# 3. Backup verification
# Test restore from latest backup
./scripts/backup-verify.sh

# 4. Certificate check (if using SSL)
# Verify certs don't expire soon
openssl x509 -in /etc/ssl/certs/otp.crt -noout -dates
```

### Monthly Operations

```bash
# 1. Cluster storage cleanup
# Remove old logs, temporary files
find /var/log/otp -mtime +30 -delete

# 2. Database optimization
# Rebuild indexes
OPTIMIZE TABLE Bin;
OPTIMIZE TABLE PurchaseOrder;

# 3. Capacity planning
# Review growth trends
# Plan for next quarter

# 4. Security updates
# Apply OS and library patches
./scripts/security-updates.sh
```

---

## Troubleshooting

### Issue: Service Won't Start

```bash
# 1. Check logs
docker logs otp-service
# OR
kubectl logs deployment/otp -n otp

# Common errors:
# - "ERPNext unreachable": Check ERPNEXT_BASE_URL
# - "Port already in use": Change port or kill existing process
# - "Out of memory": Increase memory limit

# 2. Verify environment
env | grep ERPNEXT

# 3. Test connectivity
curl -v https://erpnext-instance.com/api/method/ping

# 4. Restart
docker restart otp-service
# OR
kubectl rollout restart deployment/otp -n otp
```

### Issue: High Response Times

```bash
# 1. Check metrics
# Is ERPNext responding slowly?
curl -w "@deployment/curl-time.txt" \
  -o /dev/null \
  https://erpnext-instance.com/api/method/ping

# 2. Check resource usage
# CPU >80% or Memory >80%?
kubectl top pods -n otp

# 3. Scale if needed
kubectl scale deployment otp --replicas=5 -n otp

# 4. Check database indexes
EXPLAIN SELECT * FROM Bin WHERE item_code='ITEM-001';
```

### Issue: High Error Rate

```bash
# 1. Check recent logs
kubectl logs --tail=100 deployment/otp -n otp | grep ERROR

# 2. Check ERPNext health
curl -H "Authorization: Bearer {token}" \
  https://erpnext-instance.com/api/method/ping

# 3. Check network connectivity
# Firewall rules, DNS resolution, SSL certificates

# 4. Run diagnostics
./scripts/diagnostics.sh

# 5. If needed, rollback
kubectl rollout undo deployment/otp -n otp
```

### Issue: Memory Leak

```bash
# 1. Monitor memory growth
kubectl top pods -n otp --containers | watch

# 2. Check for cycles in code
# Review promise_service.py for unreleased resources

# 3. Restart pod to free memory
kubectl delete pod <pod-name> -n otp

# 4. If leak persists, rollback to previous version
kubectl rollout undo deployment/otp -n otp
```

---

## Disaster Recovery

### Backup Strategy

```bash
# Automated daily backups
0 2 * * * /opt/otp/scripts/backup.sh

# Backup includes:
├─ Current application code/config
├─ Database schema and data
└─ Logs for last 7 days

# Store in:
├─ Local: /backups/otp/
├─ Remote: S3 bucket (otp-backups)
└─ Retention: 30 days rolling
```

### Disaster Recovery Plan

```
RTO (Recovery Time Objective): 1 hour
RPO (Recovery Point Objective): 1 day

1. Detect failure (alert triggers)
   ↓
2. Activate recovery procedure
   └─ Spin up new instances from backup
   └─ Restore database from latest backup
   └─ Configure DNS to new servers
   ↓
3. Validate functionality
   └─ Health checks
   └─ Sample transactions
   ↓
4. Restore full traffic
   └─ Gradual traffic shift (5% → 100%)
   └─ Monitor error rate
   ↓
5. Post-incident review
   └─ Root cause analysis
   └─ Improve monitoring
```

---

## Deployment Checklist

Before Going Live:

```
Code:
  ☑ All tests passing (unit + integration)
  ☑ Coverage >= 80%
  ☑ Code review approved
  ☑ Security scan passed (bandit, OWASP)
  ☑ Performance benchmarks acceptable

Infrastructure:
  ☑ ERPNext connectivity verified
  ☑ Database indexes created
  ☑ Load balancer configured
  ☑ SSL certificates installed
  ☑ Monitoring/alerting configured

Operations:
  ☑ Runbooks documented
  ☑ On-call schedule established
  ☑ Backup/recovery tested
  ☑ Incident response plan ready
  ☑ Stakeholders notified

Post-Deployment:
  ☑ Health checks passing
  ☑ Smoke tests passed
  ☑ Load testing completed
  ☑ No critical error logs
  ☑ Metrics within expected range

🚀 Ready for Production!
```

---

## Support & Escalation

```
Issue → Severity → Response Time → Escalation Chain

Critical (Service Down)
  ↓ 15 minutes
  → OTP On-Call Engineer
  → Infrastructure Team
  → VP Engineering

High (High Error Rate)
  ↓ 30 minutes
  → OTP On-Call Engineer
  → Subject Matter Expert

Medium (Degraded Performance)
  ↓ 2 hours
  → OTP Team Lead
  → Architecture Review

Low (Minor Issues)
  ↓ 1 business day
  → OTP Team
  → Scheduled Review
```

---

## Summary

This runbook ensures:
- ✅ **Smooth Deployment**: Step-by-step instructions
- ✅ **Verification**: Comprehensive post-deployment checks
- ✅ **Monitoring**: Proactive issue detection
- ✅ **Recovery**: Quick rollback procedures
- ✅ **Reliability**: Production-grade operations

For questions, contact: **otp-team@company.com**
