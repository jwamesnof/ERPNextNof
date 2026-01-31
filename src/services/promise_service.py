"""Core promise calculation service."""
from typing import List, Dict, Any, Optional
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
from src.utils.warehouse_utils import WarehouseManager, WarehouseType, default_warehouse_manager
from src.config import settings

logger = logging.getLogger(__name__)


class PromiseService:
    """
    Core service for calculating order promise dates.
    
    Implements the deterministic, explainable promise algorithm.
    OTP calculations are calendar-aware and follow a Sunday–Thursday workweek.
    Weekend days (Friday, Saturday) are excluded from all processing, shipping, and delivery.
    """

    def __init__(
        self,
        stock_service: StockService,
        warehouse_lead_times: Dict[str, int] = None,
        item_lead_times: Dict[str, int] = None,
        warehouse_manager: WarehouseManager = None
    ):
        """Initialize with stock service and optional lead time overrides.
        
        Args:
            stock_service: Service for fetching stock and incoming supply
            warehouse_lead_times: Dict mapping warehouse names to processing_lead_time_days
            item_lead_times: Dict mapping item_codes to processing_lead_time_days
            warehouse_manager: Warehouse classification manager (uses default if not provided)
            
        Processing lead time = warehouse handling time (picking, packing, QA, staging).
        """
        self.stock_service = stock_service
        self.warehouse_lead_times = warehouse_lead_times or {}
        self.item_lead_times = item_lead_times or {}
        self.warehouse_manager = warehouse_manager or default_warehouse_manager

    def _get_processing_lead_time(self, item_code: str, warehouse: str, rules: PromiseRules) -> int:
        """Resolve processing lead time with override hierarchy.
        
        Hierarchy (highest to lowest priority):
        1. Item-specific override (item_lead_times)
        2. Warehouse-specific override (warehouse_lead_times)
        3. Rule-level override (rules.processing_lead_time_days)
        4. System default (settings.processing_lead_time_days_default)
        
        Args:
            item_code: Item code to look up
            warehouse: Warehouse name to look up
            rules: Promise rules with default
            
        Returns:
            Processing lead time in days (deterministic)
        """
        # Priority 1: Item-specific override
        if item_code in self.item_lead_times:
            return self.item_lead_times[item_code]
        
        # Priority 2: Warehouse-specific override
        if warehouse in self.warehouse_lead_times:
            return self.warehouse_lead_times[warehouse]
        
        # Priority 3: Rule-level override
        if rules.processing_lead_time_days is not None:
            return rules.processing_lead_time_days
        
        # Priority 4: System default
        return settings.processing_lead_time_days_default

    # ============================================================================
    # CALENDAR UTILITIES (Sunday-Thursday workweek)
    # ============================================================================
    
    @staticmethod
    def is_working_day(date_obj: date) -> bool:
        """
        Check if a date is a working day.
        
        Working days: Sunday(6), Monday(0), Tuesday(1), Wednesday(2), Thursday(3)
        Weekend days: Friday(4), Saturday(5)
        
        Args:
            date_obj: Date to check
            
        Returns:
            True if working day, False if weekend
        """
        # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
        weekday = date_obj.weekday()
        # Working days: Sun(6), Mon(0), Tue(1), Wed(2), Thu(3)
        # Weekend days: Fri(4), Sat(5)
        return weekday not in (4, 5)  # Not Friday or Saturday
    
    @staticmethod
    def next_working_day(date_obj: date) -> date:
        """
        Get the next working day (inclusive).
        
        If date_obj is already a working day, return it.
        Otherwise, advance to the next working day (Sunday).
        
        Args:
            date_obj: Starting date
            
        Returns:
            The same date if working day, otherwise next Sunday
        """
        while not PromiseService.is_working_day(date_obj):
            date_obj += timedelta(days=1)
        return date_obj
    
    @staticmethod
    def add_working_days(start_date: date, working_days: int) -> date:
        """
        Add working days to a date, skipping weekends.
        
        This method counts ONLY working days (Sunday-Thursday).
        Friday and Saturday are not counted.
        
        Args:
            start_date: Starting date
            working_days: Number of working days to add
            
        Returns:
            Date after adding working days
            
        Example:
            - Thursday + 1 working day = Sunday (skip Fri, Sat)
            - Wednesday + 2 working days = Sunday
            - Sunday + 5 working days = Thursday
        """
        if working_days == 0:
            return start_date
        
        current = start_date
        days_added = 0
        
        while days_added < working_days:
            current += timedelta(days=1)
            if PromiseService.is_working_day(current):
                days_added += 1
        
        return current

    # ============================================================================
    # MAIN PROMISE CALCULATION
    # ============================================================================

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
        
        # Ensure base date is a working day (Sunday-Thursday)
        # If today is Friday or Saturday, move to next Sunday
        base_today = self.next_working_day(today) if rules.no_weekends else today
        
        plan = []
        latest_fulfillment_date = base_today
        has_po_access_error = False
        all_item_reasons = []

        # Step 1: Build fulfillment plan for each item
        for item in items:
            warehouse = item.warehouse or settings.default_warehouse
            item_plan, po_access_error, item_reasons = self._build_item_plan(item, warehouse, base_today, rules)
            plan.append(item_plan)
            all_item_reasons.extend(item_reasons)
            
            # Track if any item had PO access issues
            if po_access_error:
                has_po_access_error = True

            # Track the latest date needed across all items
            # Use ship_ready_date (after processing lead time) instead of available_date
            if item_plan.fulfillment:
                item_latest = max(f.ship_ready_date for f in item_plan.fulfillment)
                latest_fulfillment_date = max(latest_fulfillment_date, item_latest)

        # Step 2: Apply business rules to determine promise date
        promise_date_raw = self._apply_business_rules(latest_fulfillment_date, rules, today)

        # Step 3: Apply desired_date constraints (if provided)
        promise_result = self._apply_desired_date_constraints(
            promise_date_raw, desired_date, rules, plan, today
        )

        # Step 4: Calculate confidence
        confidence = self._calculate_confidence(plan, promise_result["promise_date"], today)
        
        # Degrade confidence if PO access denied
        if has_po_access_error:
            confidence = "LOW"

        # Step 5: Generate explanations
        reasons = all_item_reasons.copy()
        reasons.extend(self._generate_reasons(plan, promise_result["promise_date"], latest_fulfillment_date, rules))
        
        # Add desired_date-specific reasons
        if promise_result.get("adjusted_reason"):
            reasons.append(promise_result["adjusted_reason"])
            
        blockers = self._identify_blockers(plan)
        
        # Add PO access error to blockers if present
        if has_po_access_error:
            blockers.append("PO data unavailable due to permissions - supply timeline uncertain")
        
        # Generate options (enhanced if promise misses desired_date)
        options = self._suggest_options(plan, blockers, desired_date, promise_result)

        # Determine if order can be fulfilled
        can_fulfill = all(p.shortage == 0 for p in plan)
        
        # Determine status
        from src.models.response_models import PromiseStatus
        if has_po_access_error and not can_fulfill:
            status = PromiseStatus.CANNOT_PROMISE_RELIABLY
        elif not can_fulfill:
            status = PromiseStatus.CANNOT_FULFILL
        else:
            status = PromiseStatus.OK
        
        # CRITICAL: promise_date must be None if order cannot be fulfilled
        final_promise_date = promise_result["promise_date"] if can_fulfill else None

        return PromiseResponse(
            status=status,
            promise_date=final_promise_date,
            promise_date_raw=promise_date_raw,
            desired_date=desired_date,
            desired_date_mode=rules.desired_date_mode.value if desired_date else None,
            on_time=promise_result.get("on_time") if final_promise_date else None,
            adjusted_due_to_no_early_delivery=promise_result.get("adjusted_due_to_no_early_delivery", False),
            can_fulfill=can_fulfill,
            confidence=confidence,
            plan=plan,
            reasons=reasons,
            blockers=blockers,
            options=options,
        )

    def _build_item_plan(
        self, item: ItemRequest, warehouse: str, today: date, rules: PromiseRules = None
    ) -> ItemPlan:
        """
        Build fulfillment plan for a single item.
        
        Strategy:
        1. Classify warehouse and handle accordingly
        2. Use available stock from SELLABLE/NEEDS_PROCESSING warehouses
        3. Ignore IN_TRANSIT and NOT_AVAILABLE warehouse stock
        4. Use incoming POs for future supply
        5. Add processing lead time to each fulfillment source
        6. Track any shortage
        """
        if rules is None:
            rules = PromiseRules()
            
        qty_needed = item.qty
        fulfillment = []
        reasons = []  # Collect warehouse-specific reasons
        
        # Classify the warehouse
        warehouse_type = self.warehouse_manager.classify_warehouse(warehouse)
        logger.debug(f"Warehouse '{warehouse}' classified as {warehouse_type}")
        
        # Get processing lead time for this item/warehouse
        lead_time_days = self._get_processing_lead_time(item.item_code, warehouse, rules)

        # Get available stock - behavior depends on warehouse type
        logger.debug(f"Looking up stock for {item.item_code} in warehouse '{warehouse}'")
        stock = self.stock_service.get_available_stock(item.item_code, warehouse)
        logger.debug(f"Stock result: {stock}")
        available_stock = stock["available_qty"]

        # Handle stock based on warehouse type
        if available_stock > 0:
            if warehouse_type == WarehouseType.SELLABLE:
                # SELLABLE: Stock is available immediately
                qty_from_stock = min(available_stock, qty_needed)
                available_date = today
                # Add working days only (skip weekends)
                if rules.no_weekends:
                    ship_ready_date = self.add_working_days(available_date, lead_time_days)
                else:
                    ship_ready_date = available_date + timedelta(days=lead_time_days)
                fulfillment.append(
                    FulfillmentSource(
                        source="stock",
                        qty=qty_from_stock,
                        available_date=available_date,
                        ship_ready_date=ship_ready_date,
                        warehouse=warehouse,
                    )
                )
                qty_needed -= qty_from_stock
                reasons.append(f"{qty_from_stock} units from {warehouse} (ready to ship)")
                
            elif warehouse_type == WarehouseType.NEEDS_PROCESSING:
                # NEEDS_PROCESSING: Stock needs additional processing
                qty_from_stock = min(available_stock, qty_needed)
                available_date = today
                # Add extra processing time for this warehouse type
                processing_days = lead_time_days + 1  # Additional day for processing
                if rules.no_weekends:
                    ship_ready_date = self.add_working_days(available_date, processing_days)
                else:
                    ship_ready_date = available_date + timedelta(days=processing_days)
                fulfillment.append(
                    FulfillmentSource(
                        source="stock",
                        qty=qty_from_stock,
                        available_date=available_date,
                        ship_ready_date=ship_ready_date,
                        warehouse=warehouse,
                    )
                )
                qty_needed -= qty_from_stock
                reasons.append(
                    f"{qty_from_stock} units from {warehouse} "
                    f"(requires +{processing_days - lead_time_days} day processing)"
                )
                
            elif warehouse_type == WarehouseType.IN_TRANSIT:
                # IN_TRANSIT: Do not count as available now
                logger.debug(
                    f"Ignoring {available_stock} units in {warehouse} (IN_TRANSIT - not ship-ready)"
                )
                reasons.append(
                    f"{available_stock} units in {warehouse} not ship-ready (awaiting receipt)"
                )
                
            elif warehouse_type == WarehouseType.NOT_AVAILABLE:
                # NOT_AVAILABLE: Cannot satisfy demand
                logger.debug(
                    f"Ignoring {available_stock} units in {warehouse} (NOT_AVAILABLE)"
                )
                reasons.append(
                    f"{available_stock} units in {warehouse} not available for fulfillment"
                )
                
            elif warehouse_type == WarehouseType.GROUP:
                # GROUP: Should have been expanded before calling this method
                logger.warning(
                    f"Group warehouse '{warehouse}' passed to _build_item_plan; should expand first"
                )
                reasons.append(f"Group warehouse {warehouse} must be expanded to children")

        # If still need more, check incoming POs
        po_access_error = None
        if qty_needed > 0:
            incoming_result = self.stock_service.get_incoming_supply(item.item_code, after_date=today)
            
            # Check for access errors (permission denied)
            if incoming_result.get("access_error"):
                po_access_error = incoming_result["access_error"]
                if po_access_error == "permission_denied":
                    logger.warning(f"PO data access denied for {item.item_code}")
                    reasons.append(
                        f"PO data unavailable due to permissions - cannot determine incoming supply"
                    )
                else:
                    logger.error(f"PO data access error for {item.item_code}: {po_access_error}")
                    reasons.append(f"Error accessing PO data - supply timeline uncertain")
            else:
                # Process available POs
                incoming_supply = incoming_result.get("supply", [])
                for po in incoming_supply:
                    if qty_needed <= 0:
                        break

                    qty_from_po = min(po["qty"], qty_needed)
                    available_date = po["expected_date"]
                    
                    # Adjust available_date if it falls on weekend
                    if rules.no_weekends and not self.is_working_day(available_date):
                        available_date = self.next_working_day(available_date)
                        logger.debug(f"PO {po['po_id']} date adjusted to next working day: {available_date}")
                    
                    # Add working days for processing lead time
                    if rules.no_weekends:
                        ship_ready_date = self.add_working_days(available_date, lead_time_days)
                    else:
                        ship_ready_date = available_date + timedelta(days=lead_time_days)
                    
                    fulfillment.append(
                        FulfillmentSource(
                            source="purchase_order",
                            qty=qty_from_po,
                            available_date=available_date,
                            ship_ready_date=ship_ready_date,
                            po_id=po["po_id"],
                            expected_date=po["expected_date"],
                            warehouse=po.get("warehouse"),
                        )
                    )
                    qty_needed -= qty_from_po

        # Calculate shortage
        shortage = max(0, qty_needed)
        
        # Log warehouse-specific reasons
        for reason in reasons:
            logger.info(f"Item {item.item_code}: {reason}")

        item_plan = ItemPlan(
            item_code=item.item_code,
            qty_required=item.qty,
            fulfillment=fulfillment,
            shortage=shortage,
        )
        
        return item_plan, po_access_error, reasons

    def _apply_business_rules(
        self, base_date: date, rules: PromiseRules, today: date
    ) -> date:
        """
        Apply business rules to determine final promise date.
        
        Rules:
        1. Add lead time buffer (working days only)
        2. Apply cutoff time (if order placed after cutoff, add 1 working day)
        3. Ensure final date is a working day
        """
        promise_date = base_date

        # Rule 1: Add lead time buffer (working days only)
        if rules.no_weekends:
            promise_date = self.add_working_days(promise_date, rules.lead_time_buffer_days)
        else:
            promise_date += timedelta(days=rules.lead_time_buffer_days)

        # Rule 2: Apply cutoff time
        promise_date = self._apply_cutoff_rule(promise_date, rules, today)

        # Rule 3: Skip weekends
        if rules.no_weekends:
            promise_date = self._skip_weekends(promise_date)

        return promise_date

    def _apply_desired_date_constraints(
        self, 
        promise_date_raw: date, 
        desired_date: Optional[date], 
        rules: PromiseRules,
        plan: List[ItemPlan],
        today: date
    ) -> Dict[str, Any]:
        """
        Apply desired_date constraints based on configured mode.
        
        Returns dict with:
        - promise_date: final promise date
        - on_time: bool (if desired_date provided)
        - adjusted_due_to_no_early_delivery: bool
        - adjusted_reason: str (optional explanation)
        """
        from src.models.request_models import DesiredDateMode
        
        # If no desired_date, return raw promise as-is
        if desired_date is None:
            return {
                "promise_date": promise_date_raw,
                "on_time": None,
                "adjusted_due_to_no_early_delivery": False
            }
        
        mode = rules.desired_date_mode
        on_time = promise_date_raw <= desired_date
        
        # Mode A: LATEST_ACCEPTABLE (default)
        if mode == DesiredDateMode.LATEST_ACCEPTABLE:
            return {
                "promise_date": promise_date_raw,
                "on_time": on_time,
                "adjusted_due_to_no_early_delivery": False,
                "adjusted_reason": f"Desired delivery: {desired_date}. {'On time.' if on_time else 'Late by ' + str((promise_date_raw - desired_date).days) + ' days.'}"
            }
        
        # Mode B: STRICT_FAIL
        elif mode == DesiredDateMode.STRICT_FAIL:
            if not on_time:
                # Raise domain error with reasons
                days_late = (promise_date_raw - desired_date).days
                raise ValueError(
                    f"Cannot meet desired delivery date {desired_date}. "
                    f"Earliest possible promise: {promise_date_raw} ({days_late} days late). "
                    f"Check response 'options' for alternative scenarios."
                )
            return {
                "promise_date": promise_date_raw,
                "on_time": True,
                "adjusted_due_to_no_early_delivery": False,
                "adjusted_reason": f"Desired delivery: {desired_date}. Promise meets constraint."
            }
        
        # Mode C: NO_EARLY_DELIVERY
        elif mode == DesiredDateMode.NO_EARLY_DELIVERY:
            if promise_date_raw < desired_date:
                # Adjust promise to desired_date (no early delivery)
                return {
                    "promise_date": desired_date,
                    "on_time": True,  # Technically on time since we can deliver by desired_date
                    "adjusted_due_to_no_early_delivery": True,
                    "adjusted_reason": f"Can deliver earlier on {promise_date_raw}, but adjusted to desired date {desired_date} (no early delivery requested)."
                }
            else:
                # Promise is later than desired
                return {
                    "promise_date": promise_date_raw,
                    "on_time": False,
                    "adjusted_due_to_no_early_delivery": False,
                    "adjusted_reason": f"Desired delivery: {desired_date}. Promise is {(promise_date_raw - desired_date).days} days late."
                }
        
        # Fallback
        return {
            "promise_date": promise_date_raw,
            "on_time": on_time,
            "adjusted_due_to_no_early_delivery": False
        }

    def _apply_cutoff_rule(self, promise_date: date, rules: PromiseRules, today: date) -> date:
        """
        If order is placed after cutoff time, add 1 working day.
        """
        now = datetime.now(pytz.timezone(rules.timezone))
        cutoff_time = datetime.strptime(rules.cutoff_time, "%H:%M").time()
        current_time = now.time()

        # If today and past cutoff, push promise date by 1 working day
        if promise_date == today and current_time > cutoff_time:
            if rules.no_weekends:
                promise_date = self.add_working_days(promise_date, 1)
                logger.debug(f"Applied cutoff rule: {current_time} > {cutoff_time}, added 1 working day")
            else:
                promise_date += timedelta(days=1)
                logger.debug(f"Applied cutoff rule: {current_time} > {cutoff_time}, added 1 day")

        return promise_date

    def _skip_weekends(self, target_date: date) -> date:
        """
        Ensure date falls on a working day (Sunday-Thursday workweek).
        
        If date falls on weekend (Friday=4, Saturday=5), move to next Sunday.
        """
        return self.next_working_day(target_date)

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

        if rules.no_weekends and self.is_working_day(promise_date):
            reasons.append("Weekend delivery avoided (Friday-Saturday excluded)")

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
        self, 
        plan: List[ItemPlan], 
        blockers: List[str],
        desired_date: Optional[date] = None,
        promise_result: Dict[str, Any] = None
    ) -> List[PromiseOption]:
        """Suggest alternative options to improve promise."""
        options = []

        # Check if we missed desired_date
        missed_desired = False
        if desired_date and promise_result:
            missed_desired = not promise_result.get("on_time", True)

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
                    if days_away > 7 or missed_desired:
                        potential_savings = min(days_away - 3, days_away // 2)
                        options.append(
                            PromiseOption(
                                type="expedite_po",
                                po_id=f.po_id,
                                description=f"Expedite {f.po_id} for {item_plan.item_code}",
                                impact=f"Could reduce promise date by up to {potential_savings} days",
                            )
                        )

        # If we missed desired_date, add split shipment option
        if missed_desired and len(plan) > 0:
            # Check if any items can ship earlier
            in_stock_items = [p for p in plan if p.shortage == 0 and 
                             any(f.source == "stock" for f in p.fulfillment)]
            
            if in_stock_items and len(in_stock_items) < len(plan):
                earliest_stock_date = min(
                    f.ship_ready_date 
                    for p in in_stock_items 
                    for f in p.fulfillment 
                    if f.source == "stock"
                )
                options.append(
                    PromiseOption(
                        type="split_shipment",
                        description=f"Ship {len(in_stock_items)} items from stock immediately",
                        impact=f"Partial delivery by {earliest_stock_date}, remaining items later",
                    )
                )

        return options

    def _get_today(self, timezone_str: str) -> date:
        """Get today's date in specified timezone."""
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz).date()
