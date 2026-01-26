"""FastAPI application entry point."""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.routes import otp
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
    """
    erpnext_connected = False
    message = None

    try:
        with ERPNextClient() as client:
            erpnext_connected = client.health_check()
            if erpnext_connected:
                message = "All systems operational"
            else:
                message = "ERPNext connection failed"
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


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info("Starting OTP Service...")
    logger.info(f"Environment: {settings.otp_service_env}")
    logger.info(f"ERPNext URL: {settings.erpnext_base_url}")
    logger.info(f"API Documentation: http://{settings.otp_service_host}:{settings.otp_service_port}/docs")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    logger.info("Shutting down OTP Service...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.otp_service_host,
        port=settings.otp_service_port,
        reload=settings.otp_service_env == "development",
    )
