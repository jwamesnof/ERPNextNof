"""API routes for demo data endpoints."""
from fastapi import APIRouter, HTTPException
import logging
from src.services.csv_data_loader import CSVDataLoader
from pathlib import Path
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Demo Data"])

# Initialize data loader - use project root directory
PROJECT_ROOT = Path(os.path.dirname(__file__)).parent.parent
CSV_FILE = PROJECT_ROOT / "Sales Invoice.csv"
loader = CSVDataLoader(str(CSV_FILE))


@router.get("/invoices/summary")
async def get_invoices_summary():
    """
    Get summary of loaded invoices from CSV.
    
    Returns:
        - total_invoices: Total number of invoices loaded
        - total_amount: Total invoice amount
        - total_items: Total items sold
        - unique_customers: Count of unique customers
        - unique_items: Count of unique items
        - customers: List of customer names
        - items: List of item codes
    """
    try:
        summary = loader.get_invoice_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoices/all")
async def get_all_invoices():
    """
    Get all invoices from CSV.
    
    Returns:
        List of invoices with all details.
    """
    try:
        invoices = loader.load_sales_invoices()
        return {
            "count": len(invoices),
            "invoices": invoices
        }
    except Exception as e:
        logger.error(f"Error getting invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoices/customer/{customer_name}")
async def get_customer_invoices(customer_name: str):
    """
    Get invoices for a specific customer.
    
    Args:
        customer_name: Name of the customer
    
    Returns:
        List of invoices for that customer.
    """
    try:
        invoices = loader.get_invoices_by_customer(customer_name)
        if not invoices:
            return {
                "customer": customer_name,
                "count": 0,
                "invoices": []
            }
        
        return {
            "customer": customer_name,
            "count": len(invoices),
            "invoices": invoices
        }
    except Exception as e:
        logger.error(f"Error getting customer invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoices/item/{item_code}")
async def get_item_invoices(item_code: str):
    """
    Get invoices containing a specific item.
    
    Args:
        item_code: Code of the item
    
    Returns:
        List of invoices containing that item.
    """
    try:
        invoices = loader.get_invoices_by_item(item_code)
        if not invoices:
            return {
                "item_code": item_code,
                "count": 0,
                "invoices": []
            }
        
        return {
            "item_code": item_code,
            "count": len(invoices),
            "invoices": invoices
        }
    except Exception as e:
        logger.error(f"Error getting item invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))
