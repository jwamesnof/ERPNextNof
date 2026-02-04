"""Mock supply data service backed by a unified CSV file."""
from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MockSupplyService:
    """
    Provide stock availability and incoming supply from a unified CSV file.

    Expected CSV structure:
    - Section 1 (Stock): Headers include "item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"
    - Section 2 (Purchase Orders): Headers include "po_id", "item_code", "qty", "expected_date", "warehouse"

    The file contains an empty row separator between the two sections.
    """

    def __init__(self, data_file: str):
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_path = self._resolve_path(data_file)

        self.stock_index = {}
        self.po_index = {}
        self._load_data()

    def _resolve_path(self, path_str: str) -> Path:
        path = Path(path_str)
        if not path.is_absolute():
            path = self.project_root / path
        return path

    def _safe_float(self, value: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _load_data(self):
        """Load stock and PO data from enriched Sales Invoice CSV plus fallbacks."""
        if not self.data_path.exists():
            logger.warning(f"Mock data file not found: {self.data_path}")
            return

        # 1) Load PO data from the enriched Sales Invoice CSV (row-level PO columns)
        with self.data_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                self._parse_po_row_from_row(row)

        # 2) Fallback: if no POs loaded, try the legacy purchase_orders.csv
        if sum(len(v) for v in self.po_index.values()) == 0:
            po_path = self.project_root / "data" / "purchase_orders.csv"
            if po_path.exists():
                with po_path.open(newline="", encoding="utf-8") as fh:
                    po_reader = csv.DictReader(fh)
                    for row in po_reader:
                        self._parse_po_row(row)

        # 3) Stock always comes from stock.csv (explicit mock inventory)
        stock_path = self.project_root / "data" / "stock.csv"
        if stock_path.exists():
            with stock_path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    self._parse_stock_row(row)

        logger.info(
            "Loaded %s stock rows and %s purchase orders from %s",
            sum(len(v) for v in self.stock_index.values()),
            sum(len(v) for v in self.po_index.values()),
            self.data_path,
        )

    def _parse_po_row_from_row(self, row: Dict[str, str]):
        """Parse PO data from enriched Sales Invoice rows."""
        po_id = (row.get("PO_ID") or row.get("po_id") or "").strip()
        item_code = (row.get("Item (Items)") or row.get("item_code") or "").strip()
        expected_raw = (row.get("PO_Expected_Date") or row.get("expected_date") or "").strip()
        qty_val = row.get("PO_Quantity") or row.get("qty")
        warehouse = (
            row.get("PO_Warehouse") or row.get("Warehouse (Items)") or row.get("warehouse") or ""
        ).strip()

        if not po_id or not item_code or not expected_raw:
            return

        qty = self._safe_float(qty_val)

        try:
            expected_date = datetime.strptime(expected_raw, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(
                "Skipping PO %s for %s due to bad date: %s", po_id, item_code, expected_raw
            )
            return

        record = {
            "po_id": po_id,
            "item_code": item_code,
            "qty": qty,
            "expected_date": expected_date,
            "warehouse": warehouse,
        }
        self.po_index.setdefault(item_code.lower(), []).append(record)
        self.po_index[item_code.lower()].sort(key=lambda r: r["expected_date"])

    def _parse_stock_row(self, row: Dict[str, str]):
        """Parse a stock row."""
        item_code = row.get("item_code", "").strip()
        warehouse = row.get("warehouse", "").strip()
        if not item_code or not warehouse:
            return

        record = {
            "item_code": item_code,
            "warehouse": warehouse,
            "actual_qty": self._safe_float(row.get("actual_qty")),
            "reserved_qty": self._safe_float(row.get("reserved_qty")),
            "projected_qty": self._safe_float(row.get("projected_qty")),
        }
        self.stock_index.setdefault(item_code.lower(), []).append(record)

    def _parse_po_row(self, row: Dict[str, str]):
        """Parse a purchase order row."""
        item_code = row.get("item_code", "").strip()
        po_id = row.get("po_id", "").strip()
        expected_raw = row.get("expected_date", "").strip()
        warehouse = row.get("warehouse", "").strip()
        qty = self._safe_float(row.get("qty"))

        if not item_code or not po_id or not expected_raw:
            return

        try:
            expected_date = datetime.strptime(expected_raw, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(
                "Skipping PO %s for %s due to bad date: %s", po_id, item_code, expected_raw
            )
            return

        record = {
            "po_id": po_id,
            "item_code": item_code,
            "qty": qty,
            "expected_date": expected_date,
            "warehouse": warehouse,
        }
        self.po_index.setdefault(item_code.lower(), []).append(record)

        # Sort by expected date
        self.po_index[item_code.lower()].sort(key=lambda r: r["expected_date"])

    def get_available_stock(
        self, item_code: str, warehouse: Optional[str] = None
    ) -> Dict[str, float]:
        all_matches = self.stock_index.get(item_code.lower(), [])
        matches = all_matches

        if warehouse:
            matches = [r for r in all_matches if r["warehouse"].lower() == warehouse.lower()]
            if not matches:
                # Fallback: use all warehouses for this item if requested warehouse has no mock row
                matches = all_matches

        if not matches:
            return {"actual_qty": 0.0, "reserved_qty": 0.0, "available_qty": 0.0}

        actual = sum(r["actual_qty"] for r in matches)
        reserved = sum(r["reserved_qty"] for r in matches)
        projected = sum(r["projected_qty"] for r in matches)
        return {
            "actual_qty": actual,
            "reserved_qty": reserved,
            "available_qty": projected,
        }

    def get_incoming_supply(self, item_code: str, after_date: Optional[date] = None) -> Dict:
        """
        Get incoming supply from mock PO data.

        Returns:
            Dict with structure: {"supply": [...], "access_error": None}
            Matches format returned by StockService for consistency.
        """
        recs = list(self.po_index.get(item_code.lower(), []))
        if after_date:
            recs = [r for r in recs if r["expected_date"] >= after_date]
        recs.sort(key=lambda r: r["expected_date"])
        return {"supply": recs, "access_error": None}
