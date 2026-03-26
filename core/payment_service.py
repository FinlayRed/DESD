"""
Payment processing service for the Bristol Regional Food Network.

Provides a mock payment gateway (simulating Stripe test mode) and
the business logic that creates Payment records, calculates the 5 %
network commission, and distributes the producer share.

This module is designed to be called by the checkout view (John's
basket / order flow).  It does NOT own the checkout UI – it only
exposes ``process_order_payment()`` as the single entry-point the
checkout view should call once the customer confirms payment.

Test-case coverage
------------------
TC-007  – single-producer order payment + commission
TC-008  – multi-producer order payment + per-producer distribution
TC-012  – settlement linkage (delegates to services.sync_producer_settlements)
TC-025  – Payment / commission records for admin reporting
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import Order, OrderItem, Payment
from .services import COMMISSION_RATE, TWOPLACES


# ---------------------------------------------------------------------------
# Mock payment gateway (simulates Stripe test-mode charges)
# ---------------------------------------------------------------------------

class MockPaymentGateway:
    """
    Simulates a payment provider in test/sandbox mode.

    Every call to ``charge()`` succeeds and returns a fake
    transaction reference that looks like a Stripe charge ID.
    In a production build this class would be swapped for a real
    Stripe / PayPal SDK wrapper.
    """

    @staticmethod
    def charge(amount_pence: int, currency: str = "gbp",
               description: str = "", metadata: dict | None = None):
        """
        Simulate a card charge.

        Parameters
        ----------
        amount_pence : int
            Amount in the smallest currency unit (pence for GBP).
        currency : str
            ISO currency code (default ``"gbp"``).
        description : str
            Human-readable charge description.
        metadata : dict, optional
            Arbitrary key/value pairs attached to the charge.

        Returns
        -------
        dict
            A simplified charge-response object.
        """
        charge_id = f"ch_mock_{uuid.uuid4().hex[:24]}"
        return {
            "id": charge_id,
            "status": "succeeded",
            "amount": amount_pence,
            "currency": currency,
            "description": description,
            "metadata": metadata or {},
            "created": timezone.now().isoformat(),
        }

    @staticmethod
    def refund(charge_id: str, amount_pence: int | None = None):
        """Simulate a full or partial refund."""
        refund_id = f"re_mock_{uuid.uuid4().hex[:24]}"
        return {
            "id": refund_id,
            "charge": charge_id,
            "status": "succeeded",
            "amount": amount_pence,
            "created": timezone.now().isoformat(),
        }


# Singleton-style gateway instance – import this from other modules.
payment_gateway = MockPaymentGateway()


# ---------------------------------------------------------------------------
# Core payment processing
# ---------------------------------------------------------------------------

def _calculate_item_totals(order: Order):
    """
    Walk through every item on an order and return a dict
    keyed by producer with the value being their gross subtotal.

    Also returns the overall order total.
    """
    producer_totals: dict[int, Decimal] = {}
    order_total = Decimal("0.00")

    items = order.items.select_related("product__producer").all()
    for item in items:
        line_total = (item.price * item.quantity).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
        producer_id = item.product.producer_id
        producer_totals[producer_id] = producer_totals.get(
            producer_id, Decimal("0.00")
        ) + line_total
        order_total += line_total

    return order_total, producer_totals


@transaction.atomic
def process_order_payment(order: Order,
                          payment_method: str = "card_mock") -> Payment:
    """
    Process payment for an order.

    This is the **single entry-point** the checkout view should call.

    Steps
    -----
    1. Calculate the order total from its items.
    2. Charge the mock gateway.
    3. Calculate the 5 % network commission.
    4. Create a ``Payment`` record.
    5. Mark the order as paid.

    Parameters
    ----------
    order : Order
        The order to process.  Must already contain its ``OrderItem`` rows.
    payment_method : str
        A label for the payment method used (stored for audit).

    Returns
    -------
    Payment
        The newly created ``Payment`` instance.

    Raises
    ------
    ValueError
        If the order has no items or is already paid.
    """
    if order.paid:
        raise ValueError(f"Order {order.reference} is already paid.")

    order_total, producer_totals = _calculate_item_totals(order)

    if order_total <= 0:
        raise ValueError("Order total must be greater than zero.")

    # ---- 1. Charge the mock gateway ----
    amount_pence = int((order_total * 100).to_integral_value())
    charge_result = payment_gateway.charge(
        amount_pence=amount_pence,
        description=f"BRFN Order {order.reference}",
        metadata={
            "order_id": str(order.pk),
            "order_ref": order.reference or "",
        },
    )

    if charge_result["status"] != "succeeded":
        raise RuntimeError("Payment charge failed.")

    # ---- 2. Commission split ----
    commission = (order_total * COMMISSION_RATE).quantize(
        TWOPLACES, rounding=ROUND_HALF_UP
    )
    producer_amount = (order_total - commission).quantize(
        TWOPLACES, rounding=ROUND_HALF_UP
    )

    # ---- 3. Create the Payment record ----
    payment = Payment.objects.create(
        order=order,
        total_amount=order_total,
        network_commission=commission,
        producer_amount=producer_amount,
    )

    # ---- 4. Mark order as paid ----
    order.paid = True
    order.save(update_fields=["paid", "updated_at"])

    return payment


def get_producer_payment_breakdown(order: Order):
    """
    Return per-producer financial breakdown for a paid order.

    Used by the admin reports and potentially by the checkout
    confirmation page to show the customer how their money is
    distributed.

    Returns
    -------
    list[dict]
        Each dict contains ``producer``, ``gross``, ``commission``,
        and ``net`` keys.
    """
    _, producer_totals = _calculate_item_totals(order)
    breakdown = []
    for producer_id, gross in producer_totals.items():
        commission = (gross * COMMISSION_RATE).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
        net = (gross - commission).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        breakdown.append({
            "producer_id": producer_id,
            "gross": gross,
            "commission": commission,
            "net": net,
        })
    return breakdown
