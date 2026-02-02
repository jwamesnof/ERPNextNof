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
    SalesOrderItem,
    SalesOrderDetailsResponse,
    SalesOrderDetailItem,
    SalesOrderDefaults,
)
from src.controllers.otp_controller import OTPController
from src.services.promise_service import PromiseService
from src.services.stock_service import StockService
from src.services.apply_service import ApplyService
from src.clients.erpnext_client import ERPNextClient, ERPNextClientError
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/otp", tags=["OTP"])

_SALES_ORDER_CACHE_TTL_SECONDS = 300
_sales_orders_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def _map_erpnext_error_to_http(e: ERPNextClientError) -> HTTPException:
    message = str(e)
    if "HTTP 404" in message or "404" in message:
        return HTTPException(status_code=404, detail="Sales Order not found")
    return HTTPException(status_code=502, detail=f"ERPNext returned error: {message}")


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


@router.get("/sales-orders", response_model=List[SalesOrderItem])
async def list_sales_orders(
    client: ERPNextClient = Depends(get_erpnext_client),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    customer: Optional[str] = Query(None, description="Filter by customer name"),
    status: Optional[str] = Query(None, description="Filter by status (e.g., Draft, To Deliver)"),
    from_date: Optional[str] = Query(None, description="Filter transaction_date >= this date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter transaction_date <= this date (ISO format: YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search in Sales Order name or customer name"),
) -> List[SalesOrderItem]:
    """
    Get Sales Orders list from ERPNext for dropdown/list selection.
    
    Returns a lightweight list of Sales Orders ordered by newest first.
    Suitable for frontend dropdowns and list components.
    
    Query Parameters:
    - limit: Max results (1-100, default 20)
    - offset: Pagination offset (default 0)
    - customer: Filter by customer name (optional)
    - status: Filter by Sales Order status (optional)
    - from_date: Start date filter for transaction_date (optional, ISO format)
    - to_date: End date filter for transaction_date (optional, ISO format)
    - search: Search in SO name or customer name (optional)
    
    Returns:
    ```json
    [
      {
        "name": "SO-00001",
        "customer": "Customer A",
        "transaction_date": "2026-02-01",
        "delivery_date": "2026-02-05",
        "status": "To Deliver and Bill",
        "grand_total": 1234.56
      }
    ]
    ```
    
    Errors:
    - 502: ERPNext returned error (see detail field)
    - 500: Internal server error
    """
    cache_key = (limit, offset, customer, status, from_date, to_date, search)
    cached = _sales_orders_cache.get(cache_key)
    now = time.time()
    if cached and cached["expires_at"] > now:
        logger.info("[OTP API] Returning cached sales orders")
        return cached["data"]

    try:
        logger.info(
            f"[OTP API] Fetching sales orders: limit={limit}, offset={offset}, customer={customer}, "
            f"status={status}, from_date={from_date}, to_date={to_date}, search={search}"
        )
        
        orders = client.get_sales_order_list(
            limit=limit,
            offset=offset,
            status=status,
            customer=customer,
            from_date=from_date,
            to_date=to_date,
            search=search,
        )

        items: List[SalesOrderItem] = []
        for order in orders:
            items.append(
                SalesOrderItem(
                    name=order.get("name"),
                    customer=order.get("customer"),
                    transaction_date=order.get("transaction_date"),
                    delivery_date=order.get("delivery_date"),
                    status=order.get("status"),
                    grand_total=order.get("grand_total"),
                )
            )

        _sales_orders_cache[cache_key] = {
            "data": items,
            "expires_at": now + _SALES_ORDER_CACHE_TTL_SECONDS,
        }
        
        logger.info(f"[OTP API] Retrieved {len(items)} sales orders")
        return items

    except ERPNextClientError as e:
        logger.error(f"[OTP API] ERPNext error: {e}")
        # Return 502 Bad Gateway - ERPNext service returned an error
        raise HTTPException(
            status_code=502, 
            detail=f"ERPNext returned error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[OTP API] Unexpected error fetching sales orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/sales-orders/{sales_order_id}", response_model=SalesOrderDetailsResponse)
async def get_sales_order_details(
    sales_order_id: str,
    client: ERPNextClient = Depends(get_erpnext_client),
) -> SalesOrderDetailsResponse:
    """
    Get full Sales Order details from ERPNext for UI auto-fill.

    Returns customer name, items, order metadata, and OTP defaults.
    """
    try:
        order = client.get_sales_order(sales_order_id)

        items = []
        for item in order.get("items") or []:
            items.append(
                SalesOrderDetailItem(
                    item_code=item.get("item_code"),
                    item_name=item.get("item_name"),
                    qty=item.get("qty", 0),
                    uom=item.get("uom"),
                    warehouse=item.get("warehouse") or item.get("target_warehouse"),
                )
            )

        default_warehouse = (
            order.get("set_warehouse")
            or (items[0].warehouse if items else None)
            or settings.default_warehouse
        )

        return SalesOrderDetailsResponse(
            id=order.get("name") or sales_order_id,
            customer_name=order.get("customer_name") or order.get("customer") or "Unknown",
            transaction_date=order.get("transaction_date"),
            delivery_date=order.get("delivery_date"),
            status=order.get("status"),
            grand_total=order.get("grand_total"),
            items=items,
            defaults=SalesOrderDefaults(
                warehouse=default_warehouse,
                delivery_model=settings.delivery_model,
                cutoff_time=settings.cutoff_time,
                no_weekends=settings.no_weekends,
            ),
        )
    except ERPNextClientError as e:
        logger.error(f"[OTP API] ERPNext error: {e}")
        raise _map_erpnext_error_to_http(e)
    except Exception as e:
        logger.error(
            f"[OTP API] Unexpected error fetching sales order {sales_order_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
