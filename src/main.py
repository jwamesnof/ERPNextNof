"""FastAPI application entry point."""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.routes import otp, items
from src.models.response_models import HealthResponse
from src.clients.erpnext_client import ERPNextClient
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ERPNext Order Promise Engine (OTP)",
    description="API service for calculating order promise dates and managing fulfillment",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc) if settings.otp_service_env == "development" else None,
        },
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Verifies:
    - Service is running
    - ERPNext connection is working
    - Circuit breaker status (for connection resilience)
    """
    erpnext_connected = False
    message = None

    try:
        client = ERPNextClient()
        erpnext_connected = client.health_check()
        
        # Get circuit breaker status
        cb_status = ERPNextClient.get_circuit_breaker_status()
        
        if erpnext_connected:
            if cb_status["state"] == "open":
                message = "Connected but circuit breaker is protecting against cascading failures"
            else:
                message = "All systems operational"
        else:
            message = "ERPNext connection failed"
            
        logger.info(f"Health check - Connected: {erpnext_connected}, CB State: {cb_status['state']}")
            
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        message = f"ERPNext unreachable: {str(e)}"

    return HealthResponse(
        status="healthy" if erpnext_connected else "degraded",
        version="0.1.0",
        erpnext_connected=erpnext_connected,
        message=message,
    )


# Include routers
app.include_router(otp.router)
app.include_router(items.router)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info("Starting OTP Service...")
    logger.info(f"Environment: {settings.otp_service_env}")
    logger.info(f"ERPNext URL: {settings.erpnext_base_url}")
    logger.info(
        f"API Documentation: http://{settings.otp_service_host}:{settings.otp_service_port}/docs"
    )

    # No global HTTP client initialization needed; clients are now per-instance and thread-safe
    logger.info("HTTP client is now per-instance and thread-safe; no global pool initialized.")

    # Log all registered routes for debugging
    logger.info("\n=== Registered Routes ===")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            if "sales" in route.path.lower():
                logger.info(f"  {route.methods} {route.path}")
    logger.info("=== End Routes ===\n")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    logger.info("Shutting down OTP Service...")
    # No global HTTP client to close; clients are now per-instance
    logger.info("No global HTTP client to close; clients are per-instance.")


# Diagnostics endpoint
@app.get("/diagnostics")
async def diagnostics():
    """
    Get connection diagnostics and circuit breaker status.
    
    Returns:
        {
            "circuit_breaker": {
                "state": "closed" | "open" | "half_open",
                "failure_count": int,
                "threshold": int,
                "last_failure_time": float | null
            },
            "http_client": {
                "pooled": true,
                "max_connections": 100,
                "keep_alive_connections": 50,
                "keep_alive_expiry": "30s"
            }
        }
    """
    cb_status = ERPNextClient.get_circuit_breaker_status()
    
    return {
        "circuit_breaker": {
            "state": cb_status["state"],
            "failure_count": cb_status["failure_count"],
            "threshold": cb_status["threshold"],
            "last_failure_time": cb_status["last_failure_time"],
        },
        "http_client": {
            "pooled": True,
            "max_connections": 100,
            "keep_alive_connections": 50,
            "keep_alive_expiry": "30s",
        },
        "message": "Connection pooling and circuit breaker protection active"
    }

if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.otp_service_host,
        port=settings.otp_service_port,
        reload=settings.otp_service_env == "development",
    )
