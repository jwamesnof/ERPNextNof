"""
Script to enrich Sales Invoices with Purchase Order data as new columns
"""
import pandas as pd
from pathlib import Path
import sys

def enrich_sales_invoices():
    # Load all data
    print("=" * 80)
    print("ENRICHING SALES INVOICES WITH PURCHASE ORDER DATA")
    print("=" * 80)
    sys.stdout.flush()
    
    try:
        # Try pandas 2.x syntax
        df_inv = pd.read_csv("data/Sales Invoice.csv", on_bad_lines='skip')
    except TypeError:
        # Fall back to pandas 1.x syntax
        df_inv = pd.read_csv("data/Sales Invoice.csv", error_bad_lines=False, warn_bad_lines=False)
    
    df_po = pd.read_csv("data/purchase_orders.csv")
    
    print("\nLoaded:")
    print(f"   - Sales Invoice rows: {len(df_inv)}")
    print(f"   - Purchase Orders: {len(df_po)}")
    print(f"   - Original invoice columns: {len(df_inv.columns)}")
    sys.stdout.flush()
    
    # Check for warehouse mismatches
    invoice_warehouses = df_inv[pd.notna(df_inv['Item (Items)'])]['Warehouse (Items)'].unique()
    po_warehouses = df_po['warehouse'].unique()
    print(f"\nInvoice warehouses: {list(invoice_warehouses)}")
    print(f"PO warehouses: {list(po_warehouses)}")
    
    # Since warehouses don't match, we'll map by item_code only
    # and use the invoice warehouse in enriched data
    po_by_item = {}
    for _, po_row in df_po.iterrows():
        item_code = po_row['item_code']
        po_by_item[item_code] = {
            'PO_ID': po_row['po_id'],
            'PO_Quantity': po_row['qty'],
            'PO_Expected_Date': po_row['expected_date'],
            'PO_Warehouse_Original': po_row['warehouse']  # Keep original for reference
        }
    
    print(f"\nCreated PO mapping for {len(po_by_item)} items")
    sys.stdout.flush()
    
    # Add new PO columns to invoice data
    df_inv['PO_ID'] = None
    df_inv['PO_Quantity'] = None
    df_inv['PO_Expected_Date'] = None
    df_inv['PO_Warehouse'] = None
    
    # Enrich each row - match by item_code only, use invoice warehouse
    matches = 0
    for idx, row in df_inv.iterrows():
        item_code = row.get('Item (Items)')
        warehouse = row.get('Warehouse (Items)')
        
        if pd.notna(item_code):
            if item_code in po_by_item:
                po_data = po_by_item[item_code]
                df_inv.at[idx, 'PO_ID'] = po_data['PO_ID']
                df_inv.at[idx, 'PO_Quantity'] = po_data['PO_Quantity']
                df_inv.at[idx, 'PO_Expected_Date'] = po_data['PO_Expected_Date']
                # Use the invoice warehouse, not the PO warehouse
                df_inv.at[idx, 'PO_Warehouse'] = warehouse if pd.notna(warehouse) else po_data['PO_Warehouse_Original']
                matches += 1
    
    print(f"\nMatched {matches} invoice items with PO data")
    sys.stdout.flush()
    
    # Display enriched data (items only)
    display_cols = ['ID', 'Date', 'Customer', 'Item (Items)', 'Quantity (Items)', 
                    'Warehouse (Items)', 'Sales Order (Items)', 
                    'PO_ID', 'PO_Quantity', 'PO_Expected_Date']
    
    df_display = df_inv[display_cols].dropna(subset=['Item (Items)'])
    
    print("\n" + "=" * 80)
    print("ENRICHED SALES INVOICES (With PO Columns)")
    print("=" * 80)
    print(df_display.to_string(index=False, max_colwidth=20))
    
    print("\nSummary:")
    print(f"   - Total invoice item rows: {len(df_display)}")
    print(f"   - Rows with PO match: {df_display['PO_ID'].notna().sum()}")
    print(f"   - Rows without PO match: {df_display['PO_ID'].isna().sum()}")
    print(f"   - New columns added: PO_ID, PO_Quantity, PO_Expected_Date, PO_Warehouse")
    sys.stdout.flush()
    
    # Save enriched file
    output_file = "data/Sales Invoice_Enriched.csv"
    df_inv.to_csv(output_file, index=False)
    print(f"\nEnriched file saved: {output_file}")
    print(f"   Total columns: {len(df_inv.columns)} (original {len(df_inv.columns)-4} + 4 new PO columns)")
    sys.stdout.flush()
    
    return df_inv

if __name__ == "__main__":
    enrich_sales_invoices()
