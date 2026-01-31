"""Warehouse classification and utility functions for OTP.

Warehouses represent different inventory availability stages:
- SELLABLE: Ready to ship immediately
- NEEDS_PROCESSING: Requires additional processing before shipping
- IN_TRANSIT: Not available now; becomes supply based on receipt ETA
- NOT_AVAILABLE: Cannot satisfy demand (WIP, rejected, etc.)
- GROUP: Logical container; must expand to children
"""
from enum import Enum
from typing import List, Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)


class WarehouseType(str, Enum):
    """Warehouse availability classification."""
    SELLABLE = "SELLABLE"  # Stock counts as available now (e.g., "Stores - SD")
    NEEDS_PROCESSING = "NEEDS_PROCESSING"  # Requires processing lead time (e.g., "Finished Goods - SD")
    IN_TRANSIT = "IN_TRANSIT"  # Not available now; future supply only (e.g., "Goods In Transit - SD")
    NOT_AVAILABLE = "NOT_AVAILABLE"  # Cannot satisfy demand (e.g., "Work In Progress - SD")
    GROUP = "GROUP"  # Logical container only (e.g., "All Warehouses - SD")


# Default warehouse classification rules
DEFAULT_WAREHOUSE_CLASSIFICATIONS: Dict[str, WarehouseType] = {
    # SELLABLE - ready to ship immediately
    "stores - sd": WarehouseType.SELLABLE,
    "stores - wh": WarehouseType.SELLABLE,
    "main warehouse": WarehouseType.SELLABLE,
    "warehouse": WarehouseType.SELLABLE,
    
    # NEEDS_PROCESSING - requires additional processing
    "finished goods - sd": WarehouseType.NEEDS_PROCESSING,
    "finished goods - wh": WarehouseType.NEEDS_PROCESSING,
    "finished goods": WarehouseType.NEEDS_PROCESSING,
    
    # IN_TRANSIT - not available now, future supply only
    "goods in transit - sd": WarehouseType.IN_TRANSIT,
    "goods in transit - wh": WarehouseType.IN_TRANSIT,
    "goods in transit": WarehouseType.IN_TRANSIT,
    "in transit": WarehouseType.IN_TRANSIT,
    
    # NOT_AVAILABLE - cannot satisfy demand
    "work in progress - sd": WarehouseType.NOT_AVAILABLE,
    "work in progress - wh": WarehouseType.NOT_AVAILABLE,
    "work in progress": WarehouseType.NOT_AVAILABLE,
    "wip": WarehouseType.NOT_AVAILABLE,
    "rejected - sd": WarehouseType.NOT_AVAILABLE,
    "rejected - wh": WarehouseType.NOT_AVAILABLE,
    "scrap": WarehouseType.NOT_AVAILABLE,
    
    # GROUP - logical containers
    "all warehouses - sd": WarehouseType.GROUP,
    "all warehouses - wh": WarehouseType.GROUP,
    "all warehouses": WarehouseType.GROUP,
}

# Default warehouse hierarchy (for group expansion)
DEFAULT_WAREHOUSE_HIERARCHY: Dict[str, List[str]] = {
    "all warehouses - sd": [
        "Stores - SD",
        "Finished Goods - SD",
        "Goods In Transit - SD",
        "Work In Progress - SD"
    ],
    "all warehouses - wh": [
        "Stores - WH",
        "Finished Goods - WH",
        "Goods In Transit - WH",
        "Work In Progress - WH"
    ],
}


class WarehouseManager:
    """Manages warehouse classification and hierarchy for OTP calculations."""
    
    def __init__(
        self,
        custom_classifications: Optional[Dict[str, WarehouseType]] = None,
        custom_hierarchy: Optional[Dict[str, List[str]]] = None
    ):
        """
        Initialize warehouse manager.
        
        Args:
            custom_classifications: Override default warehouse classifications
            custom_hierarchy: Override default warehouse hierarchy
        """
        self.classifications = {**DEFAULT_WAREHOUSE_CLASSIFICATIONS}
        if custom_classifications:
            self.classifications.update(custom_classifications)
        
        self.hierarchy = {**DEFAULT_WAREHOUSE_HIERARCHY}
        if custom_hierarchy:
            self.hierarchy.update(custom_hierarchy)
    
    def classify_warehouse(self, warehouse_name: str) -> WarehouseType:
        """
        Classify a warehouse by its name.
        
        Args:
            warehouse_name: Warehouse name (case-insensitive)
            
        Returns:
            WarehouseType classification
            
        Default behavior:
        - If exact match found in classifications, return that
        - If contains "transit" or "in transit", classify as IN_TRANSIT
        - If contains "wip" or "work in progress", classify as NOT_AVAILABLE
        - If contains "finished goods", classify as NEEDS_PROCESSING
        - If contains "all" or "group", classify as GROUP
        - Otherwise, default to SELLABLE (conservative assumption)
        """
        if not warehouse_name:
            return WarehouseType.SELLABLE
        
        normalized = warehouse_name.lower().strip()
        
        # Exact match
        if normalized in self.classifications:
            return self.classifications[normalized]
        
        # Pattern matching for unmapped warehouses
        if "transit" in normalized or "in transit" in normalized:
            return WarehouseType.IN_TRANSIT
        elif "wip" in normalized or "work in progress" in normalized:
            return WarehouseType.NOT_AVAILABLE
        elif "finished goods" in normalized or "finished" in normalized:
            return WarehouseType.NEEDS_PROCESSING
        elif "all" in normalized or "group" in normalized:
            return WarehouseType.GROUP
        elif "scrap" in normalized or "reject" in normalized:
            return WarehouseType.NOT_AVAILABLE
        
        # Default to SELLABLE (stores-like warehouse)
        return WarehouseType.SELLABLE
    
    def is_group_warehouse(self, warehouse_name: str) -> bool:
        """Check if warehouse is a group warehouse."""
        return self.classify_warehouse(warehouse_name) == WarehouseType.GROUP
    
    def get_child_warehouses(self, group_warehouse: str) -> List[str]:
        """
        Get child warehouses of a group warehouse.
        
        Args:
            group_warehouse: Group warehouse name
            
        Returns:
            List of child warehouse names, or empty list if not a group
        """
        normalized = group_warehouse.lower().strip()
        return self.hierarchy.get(normalized, [])
    
    def expand_warehouse_list(
        self,
        warehouse_names: List[str],
        deduplicate: bool = True
    ) -> List[str]:
        """
        Expand warehouse list, replacing group warehouses with their children.
        
        Args:
            warehouse_names: List of warehouse names (may include groups)
            deduplicate: Remove duplicates from result
            
        Returns:
            Expanded list of non-group warehouses
            
        Example:
            expand_warehouse_list(["Stores - SD", "All Warehouses - SD"])
            -> ["Stores - SD", "Finished Goods - SD", "Goods In Transit - SD", 
                "Work In Progress - SD"]
        """
        expanded: List[str] = []
        
        for warehouse in warehouse_names:
            if self.is_group_warehouse(warehouse):
                children = self.get_child_warehouses(warehouse)
                if children:
                    logger.debug(f"Expanding group warehouse '{warehouse}' to children: {children}")
                    expanded.extend(children)
                else:
                    logger.warning(
                        f"Group warehouse '{warehouse}' has no children defined; skipping"
                    )
            else:
                expanded.append(warehouse)
        
        if deduplicate:
            # Preserve order while removing duplicates
            seen: Set[str] = set()
            result = []
            for wh in expanded:
                wh_normalized = wh.lower().strip()
                if wh_normalized not in seen:
                    seen.add(wh_normalized)
                    result.append(wh)
            return result
        
        return expanded
    
    def filter_available_warehouses(
        self,
        warehouse_names: List[str],
        include_types: Optional[List[WarehouseType]] = None
    ) -> List[str]:
        """
        Filter warehouses by type.
        
        Args:
            warehouse_names: List of warehouse names
            include_types: Types to include (default: [SELLABLE, NEEDS_PROCESSING])
            
        Returns:
            Filtered list of warehouses matching desired types
        """
        if include_types is None:
            include_types = [WarehouseType.SELLABLE, WarehouseType.NEEDS_PROCESSING]
        
        result = []
        for warehouse in warehouse_names:
            wh_type = self.classify_warehouse(warehouse)
            if wh_type in include_types:
                result.append(warehouse)
            else:
                logger.debug(
                    f"Excluding warehouse '{warehouse}' (type: {wh_type}, "
                    f"not in {include_types})"
                )
        
        return result
    
    def get_availability_reason(
        self,
        warehouse_name: str,
        qty: float
    ) -> str:
        """
        Generate human-readable reason for warehouse availability status.
        
        Args:
            warehouse_name: Warehouse name
            qty: Quantity in warehouse
            
        Returns:
            Human-readable explanation string
        """
        wh_type = self.classify_warehouse(warehouse_name)
        
        if wh_type == WarehouseType.SELLABLE:
            return f"{qty} units available in {warehouse_name} (ready to ship)"
        elif wh_type == WarehouseType.NEEDS_PROCESSING:
            return f"{qty} units in {warehouse_name} (requires processing before shipping)"
        elif wh_type == WarehouseType.IN_TRANSIT:
            return f"{qty} units in {warehouse_name} (not ship-ready; awaiting receipt)"
        elif wh_type == WarehouseType.NOT_AVAILABLE:
            return f"{qty} units in {warehouse_name} (not available for fulfillment)"
        elif wh_type == WarehouseType.GROUP:
            return f"{warehouse_name} is a group warehouse (must expand to children)"
        
        return f"{qty} units in {warehouse_name}"


# Global default instance
default_warehouse_manager = WarehouseManager()
