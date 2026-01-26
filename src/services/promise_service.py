"""Core promise calculation service."""
from typing import List, Dict, Any
from datetime import date, datetime, timedelta
import pytz
import logging
from src.models.request_models import ItemRequest, PromiseRules
from src.models.response_models import (
    PromiseResponse,
    ItemPlan,
    FulfillmentSource,
    PromiseOption,
)
from src.services.stock_service import StockService
from src.config import settings

logger = logging.getLogger(__name__)


class PromiseService:
    """
    Core service for calculating order promise dates.
    
    Implements the deterministic, explainable promise algorithm.
    """

    def __init__(self, stock_service: StockService):
        """Initialize with stock service."""
        self.stock_service = stock_service

    def calculate_promise(
        self,
        customer: str,
        items: List[ItemRequest],
        desired_date: date = None,
        rules: PromiseRules = None,
    ) -> PromiseResponse:
        """
        Calculate promise date for an order.
        
        Algorithm:
        1. For each item, build fulfillment plan from stock + incoming POs
        2. Determine earliest date all items can be fulfilled
        3. Apply business rules (cutoff, weekends, buffer)
        4. Calculate confidence based on fulfillment sources
        5. Generate reasons, blockers, and options
        """
        if rules is None:
            rules = PromiseRules()

        today = self._get_today(rules.timezone)
        plan = []
        latest_fulfillment_date = today

        # Step 1: Build fulfillment plan for each item
        for item in items:
            warehouse = item.warehouse or settings.default_warehouse
            item_plan = self._build_item_plan(item, warehouse, today)
            plan.append(item_plan)

            # Track the latest date needed across all items
            if item_plan.fulfillment:
                item_latest = max(f.available_date for f in item_plan.fulfillment)
                latest_fulfillment_date = max(latest_fulfillment_date, item_latest)

        # Step 2: Apply business rules to determine promise date
        promise_date = self._apply_business_rules(latest_fulfillment_date, rules, today)

        # Step 3: Calculate confidence
        confidence = self._calculate_confidence(plan, promise_date, today)

        # Step 4: Generate explanations
        reasons = self._generate_reasons(plan, promise_date, latest_fulfillment_date, rules)
        blockers = self._identify_blockers(plan)
        options = self._suggest_options(plan, blockers)

        return PromiseResponse(
            promise_date=promise_date,
            confidence=confidence,
            plan=plan,
            reasons=reasons,
            blockers=blockers,
            options=options,
        )

    def _build_item_plan(
        self, item: ItemRequest, warehouse: str, today: date
    ) -> ItemPlan:
        """
        Build fulfillment plan for a single item.
        
        Strategy:
        1. Use available stock first
        2. Then use incoming POs (FIFO by date)
        3. Track any shortage
        """
        qty_needed = item.qty
        fulfillment = []

        # Get available stock
        stock = self.stock_service.get_available_stock(item.item_code, warehouse)
        available_stock = stock["available_qty"]

        if available_stock > 0:
            qty_from_stock = min(available_stock, qty_needed)
            fulfillment.append(
                FulfillmentSource(
                    source="stock",
                    qty=qty_from_stock,
                    available_date=today,
                    warehouse=warehouse,
                )
            )
            qty_needed -= qty_from_stock

        # If still need more, check incoming POs
        if qty_needed > 0:
            incoming = self.stock_service.get_incoming_supply(item.item_code, after_date=today)

            for po in incoming:
                if qty_needed <= 0:
                    break

                qty_from_po = min(po["qty"], qty_needed)
                fulfillment.append(
                    FulfillmentSource(
                        source="purchase_order",
                        qty=qty_from_po,
                        available_date=po["expected_date"],
                        po_id=po["po_id"],
                        expected_date=po["expected_date"],
                        warehouse=po.get("warehouse"),
                    )
                )
                qty_needed -= qty_from_po

        # Calculate shortage
        shortage = max(0, qty_needed)

        return ItemPlan(
            item_code=item.item_code,
            qty_required=item.qty,
            fulfillment=fulfillment,
            shortage=shortage,
        )

    def _apply_business_rules(
        self, base_date: date, rules: PromiseRules, today: date
    ) -> date:
        """
        Apply business rules to determine final promise date.
        
        Rules:
        1. Add lead time buffer
        2. Apply cutoff time (if order placed after cutoff, add 1 day)
        3. Skip weekends if configured
        """
        promise_date = base_date

        # Rule 1: Add lead time buffer
        promise_date += timedelta(days=rules.lead_time_buffer_days)

        # Rule 2: Apply cutoff time
        promise_date = self._apply_cutoff_rule(promise_date, rules, today)

        # Rule 3: Skip weekends
        if rules.no_weekends:
            promise_date = self._skip_weekends(promise_date)

        return promise_date

    def _apply_cutoff_rule(self, promise_date: date, rules: PromiseRules, today: date) -> date:
        """
        If order is placed after cutoff time, add 1 day.
        """
        now = datetime.now(pytz.timezone(rules.timezone))
        cutoff_time = datetime.strptime(rules.cutoff_time, "%H:%M").time()
        current_time = now.time()

        # If today and past cutoff, push promise date by 1 day
        if promise_date == today and current_time > cutoff_time:
            promise_date += timedelta(days=1)
            logger.debug(f"Applied cutoff rule: {current_time} > {cutoff_time}, added 1 day")

        return promise_date

    def _skip_weekends(self, target_date: date) -> date:
        """
        If date falls on weekend (Saturday=5, Sunday=6), move to next Monday.
        """
        while target_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            target_date += timedelta(days=1)
        return target_date

    def _calculate_confidence(
        self, plan: List[ItemPlan], promise_date: date, today: date
    ) -> str:
        """
        Calculate overall confidence level.
        
        HIGH: All items 100% from stock
        MEDIUM: Mix of stock + near-term POs (<= 7 days) OR all from stock with minor shortages
        LOW: Depends on late POs (> 7 days) OR has significant shortages
        """
        total_qty = sum(p.qty_required for p in plan)
        stock_qty = 0
        near_po_qty = 0  # POs within 7 days
        far_po_qty = 0  # POs beyond 7 days
        shortage_qty = sum(p.shortage for p in plan)

        for item_plan in plan:
            for fulfillment in item_plan.fulfillment:
                if fulfillment.source == "stock":
                    stock_qty += fulfillment.qty
                elif fulfillment.source == "purchase_order":
                    days_away = (fulfillment.expected_date - today).days
                    if days_away <= 7:
                        near_po_qty += fulfillment.qty
                    else:
                        far_po_qty += fulfillment.qty

        # Calculate percentages
        stock_pct = stock_qty / total_qty if total_qty > 0 else 0
        shortage_pct = shortage_qty / total_qty if total_qty > 0 else 0

        # Determine confidence
        if stock_pct >= 0.99 and shortage_pct < 0.01:
            return "HIGH"
        elif shortage_pct > 0.1 or far_po_qty > near_po_qty + stock_qty:
            return "LOW"
        else:
            return "MEDIUM"

    def _generate_reasons(
        self,
        plan: List[ItemPlan],
        promise_date: date,
        base_date: date,
        rules: PromiseRules,
    ) -> List[str]:
        """Generate human-readable explanations."""
        reasons = []

        for item_plan in plan:
            if not item_plan.fulfillment:
                reasons.append(
                    f"Item {item_plan.item_code}: No stock or incoming supply available"
                )
                continue

            parts = []
            for f in item_plan.fulfillment:
                if f.source == "stock":
                    parts.append(f"{f.qty} units from stock")
                elif f.source == "purchase_order":
                    parts.append(
                        f"{f.qty} units from {f.po_id} (arriving {f.expected_date})"
                    )

            reason = f"Item {item_plan.item_code}: " + ", ".join(parts)
            reasons.append(reason)

        # Explain adjustments
        if rules.lead_time_buffer_days > 0:
            reasons.append(f"Added {rules.lead_time_buffer_days} day(s) lead time buffer")

        if promise_date != base_date:
            reasons.append(
                f"Adjusted from {base_date} to {promise_date} (business rules applied)"
            )

        if rules.no_weekends and promise_date.weekday() < 5:
            reasons.append("Weekend delivery avoided")

        return reasons

    def _identify_blockers(self, plan: List[ItemPlan]) -> List[str]:
        """Identify issues preventing optimal promise."""
        blockers = []

        for item_plan in plan:
            if item_plan.shortage > 0:
                blockers.append(
                    f"Item {item_plan.item_code}: Shortage of {item_plan.shortage} units"
                )

            # Check for late POs
            for f in item_plan.fulfillment:
                if f.source == "purchase_order" and f.expected_date:
                    days_away = (f.expected_date - date.today()).days
                    if days_away > 14:
                        blockers.append(
                            f"Item {item_plan.item_code}: PO {f.po_id} arrives in {days_away} days"
                        )

        return blockers

    def _suggest_options(
        self, plan: List[ItemPlan], blockers: List[str]
    ) -> List[PromiseOption]:
        """Suggest alternative options to improve promise."""
        options = []

        # For items with shortages or late POs, suggest options
        for item_plan in plan:
            if item_plan.shortage > 0:
                options.append(
                    PromiseOption(
                        type="alternate_warehouse",
                        description=f"Check alternate warehouses for {item_plan.item_code}",
                        impact="Could reduce promise date if stock available elsewhere",
                    )
                )

            # Suggest expediting late POs
            for f in item_plan.fulfillment:
                if f.source == "purchase_order" and f.expected_date:
                    days_away = (f.expected_date - date.today()).days
                    if days_away > 7:
                        options.append(
                            PromiseOption(
                                type="expedite_po",
                                po_id=f.po_id,
                                description=f"Expedite {f.po_id} for {item_plan.item_code}",
                                impact=f"Could reduce promise date by up to {days_away - 3} days",
                            )
                        )

        return options

    def _get_today(self, timezone_str: str) -> date:
        """Get today's date in specified timezone."""
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz).date()
