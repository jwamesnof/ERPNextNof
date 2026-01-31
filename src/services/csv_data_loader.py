"""Service for loading and processing CSV data from ERPNext exports."""
import csv
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CSVDataLoader:
    """Load and process CSV data exported from ERPNext."""

    def __init__(self, csv_file_path: str):
        """Initialize with CSV file path."""
        self.csv_file_path = Path(csv_file_path)

    def load_sales_invoices(self) -> List[Dict[str, Any]]:
        """
        Load Sales Invoices from CSV.
        
        Returns:
            List of invoice dictionaries with key fields extracted.
        """
        invoices = []
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Skip empty rows
                    if not row.get('ID'):
                        continue
                    
                    invoice = self._parse_invoice_row(row)
                    if invoice:
                        invoices.append(invoice)
            
            logger.info(f"Loaded {len(invoices)} sales invoices from CSV")
            return invoices
            
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.csv_file_path}")
            return []
        except Exception as e:
            logger.error(f"Error loading sales invoices: {e}", exc_info=True)
            return []

    def _parse_invoice_row(self, row: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single invoice row from CSV.
        
        Extracts key fields needed for the OTP skill.
        """
        try:
            invoice_id = row.get('ID', '').strip()
            if not invoice_id:
                return None
            
            # Parse items from the nested items structure
            items = self._extract_items(row)
            
            return {
                'id': invoice_id,
                'date': row.get('Date', '').strip(),
                'customer': row.get('Customer Name', '').strip(),
                'customer_id': row.get('Customer', '').strip(),
                'company': row.get('Company', '').strip(),
                'status': row.get('Status', '').strip(),
                'total_qty': self._parse_float(row.get('Total Quantity', '0')),
                'grand_total': self._parse_float(row.get('Grand Total (Company Currency)', '0')),
                'currency': row.get('Currency', 'ILS').strip(),
                'posting_date': row.get('Posting Time', '').strip(),
                'items': items,
                'warehouse': row.get('Source Warehouse', '').strip(),
                'related_sales_order': row.get('Sales Order (Items)', '').strip(),
            }
        except Exception as e:
            logger.error(f"Error parsing invoice row: {e}", exc_info=True)
            return None

    def _extract_items(self, row: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Extract items from invoice row.
        
        Items are denoted with (Items) suffix in column headers.
        """
        items = []
        
        # Extract item details from the row
        item_code = row.get('Item (Items)', '').strip()
        item_name = row.get('Item Name (Items)', '').strip()
        qty = self._parse_float(row.get('Quantity (Items)', '0'))
        rate = self._parse_float(row.get('Rate (Items)', '0'))
        amount = self._parse_float(row.get('Amount (Items)', '0'))
        warehouse = row.get('Warehouse (Items)', '').strip()
        uom = row.get('UOM (Items)', 'Nos').strip()
        
        if item_code:
            items.append({
                'item_code': item_code,
                'item_name': item_name,
                'qty': qty,
                'rate': rate,
                'amount': amount,
                'warehouse': warehouse,
                'uom': uom,
            })
        
        return items

    def _parse_float(self, value: str) -> float:
        """Safely parse float value from string."""
        try:
            if not value or value.strip() == '':
                return 0.0
            return float(value.strip())
        except ValueError:
            return 0.0

    def get_invoice_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of invoices.
        
        Returns:
            Dictionary with summary stats.
        """
        invoices = self.load_sales_invoices()
        
        if not invoices:
            return {
                'total_invoices': 0,
                'total_amount': 0.0,
                'total_items': 0,
                'customers': [],
                'items': [],
            }
        
        customers = set()
        all_items = set()
        total_amount = 0.0
        total_items = 0
        
        for invoice in invoices:
            customers.add(invoice['customer'])
            total_amount += invoice['grand_total']
            total_items += invoice['total_qty']
            
            for item in invoice['items']:
                all_items.add(item['item_code'])
        
        return {
            'total_invoices': len(invoices),
            'total_amount': total_amount,
            'total_items': int(total_items),
            'unique_customers': len(customers),
            'unique_items': len(all_items),
            'customers': sorted(list(customers)),
            'items': sorted(list(all_items)),
        }

    def get_invoices_by_customer(self, customer_name: str) -> List[Dict[str, Any]]:
        """Get all invoices for a specific customer."""
        invoices = self.load_sales_invoices()
        return [inv for inv in invoices if inv['customer'].lower() == customer_name.lower()]

    def get_invoices_by_item(self, item_code: str) -> List[Dict[str, Any]]:
        """Get all invoices containing a specific item."""
        invoices = self.load_sales_invoices()
        matching_invoices = []
        
        for invoice in invoices:
            for item in invoice['items']:
                if item['item_code'].lower() == item_code.lower():
                    matching_invoices.append(invoice)
                    break
        
        return matching_invoices
