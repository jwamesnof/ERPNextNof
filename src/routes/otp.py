"""API routes for OTP endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
import logging
import time
from typing import List, Optional, Dict, Any, Tuple
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
    SalesOrderSummary,
)
from src.controllers.otp_controller import OTPController
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.services.apply_service import ApplyService
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/otp", tags=["OTP"])

_SALES_ORDER_CACHE_TTL_SECONDS = 300
_sales_orders_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def get_erpnext_client() -> ERPNextClient:
    """Dependency to get ERPNext client."""
    return ERPNextClient()


def get_controller(client: ERPNextClient = Depends(get_erpnext_client)) -> OTPController:
    """Dependency to get OTP controller with all services."""
    stock_service = StockService(client)
    promise_service = PromiseService(stock_service)
    apply_service = ApplyService(client)
    return OTPController(promise_service, apply_service)


@router.post("/promise", response_model=PromiseResponse)
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


@router.get("/sales-orders", response_model=List[SalesOrderSummary])
async def list_sales_orders(
    client: ERPNextClient = Depends(get_erpnext_client),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    days_back: int = Query(30, ge=1, le=365),
    status: Optional[str] = Query(None),
    customer: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> List[SalesOrderSummary]:
    """
    List recent Sales Orders from ERPNext.
    
    Returns Sales Orders (Draft/Submitted) from the last N days.
    Supports pagination and optional filtering.
    """
    cache_key = (limit, offset, days_back, status, customer, search)
    cached = _sales_orders_cache.get(cache_key)
    now = time.time()
    if cached and cached["expires_at"] > now:
        return cached["data"]

    try:
        logger.info("[OTP API] Fetching sales orders")
        orders = client.get_sales_orders(
            days_back=days_back,
            limit=limit,
            offset=offset,
            status=status,
            customer=customer,
            search=search,
        )

        results: List[SalesOrderSummary] = []
        for order in orders:
            so_name = order.get("name")
            item_count = 0
            if so_name:
                try:
                    so_detail = client.get_sales_order(so_name)
                    items = so_detail.get("items") if isinstance(so_detail, dict) else None
                    if isinstance(items, list):
                        item_count = len(items)
                except ERPNextClientError as e:
                    logger.warning(f"[OTP API] Failed to fetch items for {so_name}: {e}")

            results.append(
                SalesOrderSummary(
                    name=so_name,
                    customer=order.get("customer"),
                    delivery_date=order.get("delivery_date"),
                    item_count=item_count,
                    total_qty=float(order.get("total_qty") or 0),
                    status=order.get("status"),
                    so_date=order.get("transaction_date"),
                )
            )

        _sales_orders_cache[cache_key] = {
            "data": results,
            "expires_at": now + _SALES_ORDER_CACHE_TTL_SECONDS,
        }
        return results

    except ERPNextClientError as e:
        logger.error(f"[OTP API] ERPNext error: {e}")
        raise HTTPException(status_code=503, detail=f"ERPNext service error: {str(e)}")
    except Exception as e:
        logger.error(f"[OTP API] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
