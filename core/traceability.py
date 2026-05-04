"""
Traceability record-keeping for the Bristol Regional Food Network.

When an order is paid, a TraceabilityRecord is created for every
OrderItem.  This is a **point-in-time snapshot** so that even if a
producer later edits their product details the audit trail is
preserved.

Test-case coverage
------------------
TC-013  – food miles (stored per record from postcode calculation)
TC-015  – allergen info snapshot
TC-025  – admin traceability / audit reporting
"""

from decimal import Decimal

from django.db import transaction

from .models import Order, OrderItem
from .services import calculate_food_miles


@transaction.atomic
def create_traceability_records(order: Order):
    """
    Create a TraceabilityRecord for every item on a paid order.

    Should be called immediately after ``process_order_payment()``
    succeeds.

    Imports the model here to avoid circular imports at module level.
    """
    from .models import TraceabilityRecord

    records = []
    items = (
        order.items
        .select_related("product__producer", "product__category")
        .all()
    )

    for item in items:
        product = item.product
        producer = product.producer

        # Calculate food miles between producer and customer
        food_miles = calculate_food_miles(
            producer.postcode,
            order.delivery_postcode,
        )

        record = TraceabilityRecord(
            order_item=item,
            order_reference=order.reference or f"ORD-{order.pk:05d}",
            producer=producer,
            customer=order.customer,
            product_name_snapshot=product.name,
            product_category_snapshot=(
                product.category.name if product.category else ""
            ),
            producer_name_snapshot=producer.business_name,
            producer_postcode_snapshot=producer.postcode,
            customer_postcode_snapshot=order.delivery_postcode,
            food_miles=food_miles or Decimal("0.0"),
            allergen_info_snapshot=product.allergen_info,
            organic_certified=product.organic,
            harvest_date=product.harvest_date,
            best_before_date=product.best_before_date,
            quantity=item.quantity,
            unit_price=item.price,
            line_total=(item.price * item.quantity),
        )
        records.append(record)

    TraceabilityRecord.objects.bulk_create(records)
    return records
