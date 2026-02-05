"""Quick demo script to test OTP functionality."""
import sys
from src.models.request_models import ItemRequest
from src.services.promise_service import PromiseService
from src.services.mock_supply_service import MockSupplyService
from src.config import settings


def print_section(title):
    """Print section divider."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def demo_promise_calculation():
    """Demonstrate OTP promise calculation with different scenarios."""

    print_section("OTP Demo - Order Promise Calculation")

    # Initialize service with mock data
    stock_service = MockSupplyService(settings.mock_data_file)
    promise_service = PromiseService(stock_service)

    # Scenario 1: Simple order with available stock
    print_section("Scenario 1: Order with Available Stock (Stores)")
    print("\nOrder Details:")
    print("  Customer: Demo Customer")
    print("  Item: SKU005 (Sneakers)")
    print("  Quantity: 50 units")
    print("  Warehouse: Stores - SD")
    print("  Desired Date: 2026-02-05")

    result1 = promise_service.calculate_promise(
        customer="Demo Customer",
        items=[ItemRequest(item_code="SKU005", qty=50, warehouse="Stores - SD")],
        desired_date=date(2026, 2, 5),
    )

    print("\n✅ RESULT:")
    print(f"  Status: {result1.status.value}")
    print(f"  Promise Date: {result1.promise_date}")
    print(f"  Can Fulfill: {result1.can_fulfill}")
    print(f"  Confidence: {result1.confidence}")
    print(f"  On Time: {result1.on_time}")

    if result1.plan:
        for item_plan in result1.plan:
            print(f"\n  Item: {item_plan.item_code}")
            print(f"    Required: {item_plan.qty_required}")
            print(f"    Shortage: {item_plan.shortage}")
            if item_plan.fulfillment:
                for source in item_plan.fulfillment:
                    print(
                        f"    ✓ {source.qty} units from {source.source} (ready: {source.ship_ready_date})"
                    )

    # Scenario 2: Order requiring incoming supply
    print_section("Scenario 2: Order with Incoming Supply (PO)")
    print("\nOrder Details:")
    print("  Customer: Demo Customer")
    print("  Item: SKU004 (Smartphone)")
    print("  Quantity: 30 units")
    print("  Warehouse: Stores - SD")
    print("  (Note: Will need incoming PO to fulfill)")

    result2 = promise_service.calculate_promise(
        customer="Demo Customer",
        items=[ItemRequest(item_code="SKU004", qty=30, warehouse="Stores - SD")],
        desired_date=None,
    )

    print("\n✅ RESULT:")
    print(f"  Status: {result2.status.value}")
    print(f"  Promise Date: {result2.promise_date}")
    print(f"  Can Fulfill: {result2.can_fulfill}")
    print(f"  Confidence: {result2.confidence}")

    if result2.plan:
        for item_plan in result2.plan:
            print(f"\n  Item: {item_plan.item_code}")
            print(f"    Required: {item_plan.qty_required}")
            print(f"    Shortage: {item_plan.shortage}")
            if item_plan.fulfillment:
                for source in item_plan.fulfillment:
                    if source.source == "purchase_order":
                        print(
                            f"    ✓ {source.qty} units from PO {source.po_id} (ETA: {source.expected_date})"
                        )
                    else:
                        print(f"    ✓ {source.qty} units from {source.source}")

    if result2.blockers:
        print("\n  ⚠️  Blockers:")
        for blocker in result2.blockers:
            print(f"    - {blocker}")

    # Scenario 3: Multi-item order
    print_section("Scenario 3: Multi-Item Order")
    print("\nOrder Details:")
    print("  Customer: Test Corp")
    print("  Items:")
    print("    - SKU005 (Sneakers): 20 units")
    print("    - SKU008 (Backpack): 10 units")
    print("  Warehouse: Stores - SD")
    print("  Desired Date: 2026-02-10")

    result3 = promise_service.calculate_promise(
        customer="Test Corp",
        items=[
            ItemRequest(item_code="SKU005", qty=20, warehouse="Stores - SD"),
            ItemRequest(item_code="SKU008", qty=10, warehouse="Stores - SD"),
        ],
        desired_date=date(2026, 2, 10),
    )

    print("\n✅ RESULT:")
    print(f"  Status: {result3.status.value}")
    print(f"  Promise Date: {result3.promise_date}")
    print(f"  Promise Date (raw): {result3.promise_date_raw}")
    print(f"  Can Fulfill: {result3.can_fulfill}")
    print(f"  Confidence: {result3.confidence}")
    print(f"  On Time: {result3.on_time}")

    print("\n  📦 Fulfillment Plan:")
    for item_plan in result3.plan:
        status = "✅ OK" if item_plan.shortage == 0 else f"⚠️ SHORT {item_plan.shortage}"
        print(f"    {item_plan.item_code}: {status}")
        for source in item_plan.fulfillment:
            print(f"      - {source.qty} units ready {source.ship_ready_date}")

    # Scenario 4: Order with insufficient stock
    print_section("Scenario 4: Order with Insufficient Stock")
    print("\nOrder Details:")
    print("  Customer: Big Order Corp")
    print("  Item: SKU005 (Sneakers)")
    print("  Quantity: 500 units (exceeds available)")
    print("  Warehouse: Stores - SD")

    result4 = promise_service.calculate_promise(
        customer="Big Order Corp",
        items=[ItemRequest(item_code="SKU005", qty=500, warehouse="Stores - SD")],
        desired_date=None,
    )

    print("\n✅ RESULT:")
    print(f"  Status: {result4.status.value}")
    print(f"  Promise Date: {result4.promise_date}")
    print(f"  Can Fulfill: {result4.can_fulfill}")
    print(f"  Confidence: {result4.confidence}")

    if result4.plan:
        for item_plan in result4.plan:
            print(f"\n  Item: {item_plan.item_code}")
            print(f"    Required: {item_plan.qty_required}")
            print(f"    Shortage: {item_plan.shortage} ⚠️")
            if item_plan.fulfillment:
                print(f"    Allocated: {sum(f.qty for f in item_plan.fulfillment)}")

    if result4.blockers:
        print("\n  🚫 Blockers:")
        for blocker in result4.blockers:
            print(f"    - {blocker}")

    if result4.options:
        print("\n  💡 Suggested Options:")
        for option in result4.options:
            print(f"    - {option.description}")
            print(f"      Impact: {option.impact}")

    print_section("Demo Complete")
    print("\n✅ All scenarios demonstrated successfully!")
    print("\nKey Features Shown:")
    print("  ✓ Available stock fulfillment (Stores - SD)")
    print("  ✓ Incoming supply from Purchase Orders")
    print("  ✓ Multi-item order coordination")
    print("  ✓ Calendar-aware promises (no Fri/Sat)")
    print("  ✓ Desired date handling and on-time detection")
    print("  ✓ Shortage detection and clear status messages")
    print("  ✓ Confidence levels (HIGH/MEDIUM/LOW)")
    print("  ✓ Explainable reasoning and blockers")
    print("\n")


if __name__ == "__main__":
    try:
        demo_promise_calculation()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
