"""API routes for OTP endpoints."""
from fastapi import APIRouter, Depends, HTTPException
import logging
from src.models.request_models import (
    PromiseRequest,
    ApplyPromiseRequest,
    ProcurementSuggestionRequest,
)
from src.models.response_models import (
    PromiseResponse,
    ApplyPromiseResponse,
    ProcurementSuggestionResponse,
    HealthResponse,
)
from src.controllers.otp_controller import OTPController
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.services.mock_supply_service import MockSupplyService
from src.services.apply_service import ApplyService
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/otp", tags=["OTP"])


def get_erpnext_client() -> ERPNextClient:
    """Dependency to get ERPNext client."""
    return ERPNextClient()


def get_controller(client: ERPNextClient = Depends(get_erpnext_client)) -> OTPController:
    """Dependency to get OTP controller with all services."""
    if settings.use_mock_supply:
        stock_service = MockSupplyService(settings.mock_data_file)
    else:
        stock_service = StockService(client)
    promise_service = PromiseService(stock_service)
    apply_service = ApplyService(client)
    return OTPController(promise_service, apply_service)


@router.post("/promise", response_model=PromiseResponse, response_model_exclude_none=False)
async def calculate_promise(
    request: PromiseRequest,
    controller: OTPController = Depends(get_controller),
) -> PromiseResponse:
    """
    Calculate order promise date.
    
    Given a draft order with items, returns:
    - promise_date: Earliest feasible delivery date
    - confidence: HIGH/MEDIUM/LOW
    - plan: Detailed fulfillment plan per item
    - reasons: Explanation of calculation
    - blockers: Issues preventing optimal promise
    - options: Suggestions to improve promise
    """
    try:
        return controller.calculate_promise(request)
    except ERPNextClientError as e:
        logger.error(f"ERPNext error: {e}")
        raise HTTPException(status_code=503, detail=f"ERPNext service error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/apply", response_model=ApplyPromiseResponse)
async def apply_promise(
    request: ApplyPromiseRequest,
    controller: OTPController = Depends(get_controller),
) -> ApplyPromiseResponse:
    """
    Apply promise to a Sales Order in ERPNext.
    
    Writes promise date back to ERPNext:
    - Adds comment to Sales Order
    - Updates custom fields (if configured)
    """
    try:
        response = controller.apply_promise(request)
        
        # Return error status but not as HTTP exception
        # (client can handle based on response.status)
        return response
        
    except ERPNextClientError as e:
        logger.error(f"ERPNext error: {e}")
        raise HTTPException(status_code=503, detail=f"ERPNext service error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/procurement-suggest", response_model=ProcurementSuggestionResponse)
async def create_procurement_suggestion(
    request: ProcurementSuggestionRequest,
    controller: OTPController = Depends(get_controller),
) -> ProcurementSuggestionResponse:
    """
    Create procurement suggestion in ERPNext.
    
    Creates:
    - Material Request for purchasing
    - (Future) Draft Purchase Order
    - (Future) Task for manual follow-up
    """
    try:
        response = controller.create_procurement_suggestion(request)
        return response
        
    except ERPNextClientError as e:
        logger.error(f"ERPNext error: {e}")
        raise HTTPException(status_code=503, detail=f"ERPNext service error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns service status and ERPNext connectivity.
    """
    if settings.use_mock_supply:
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            erpnext_connected=False,
            message="OTP Service is operational (using mock supply data)",
        )

    try:
        client = ERPNextClient()
        # Try a simple query to verify ERPNext connection
        erpnext_connected = False
        try:
            # Attempt to call a simple API method
            client.get_stock_balance("*", None)
            erpnext_connected = True
        except:
            pass
        
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            erpnext_connected=erpnext_connected,
            message="OTP Service is operational"
        )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            erpnext_connected=False,
            message=f"Service running but ERPNext unavailable: {str(e)}"
        )
