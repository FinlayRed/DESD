from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import atan2, cos, radians, sin, sqrt

from django.db import transaction
from django.utils import timezone

from .models import OrderItem, ProducerSettlement, SettlementEntry


BRISTOL_POSTCODE_COORDINATES = {
    "BS1": (51.4545, -2.5879),
    "BS2": (51.4576, -2.5800),
    "BS3": (51.4385, -2.6019),
    "BS4": (51.4311, -2.5610),
    "BS5": (51.4628, -2.5487),
    "BS6": (51.4703, -2.6088),
    "BS7": (51.4874, -2.5898),
    "BS8": (51.4587, -2.6216),
    "BS9": (51.4873, -2.6265),
    "BS10": (51.5054, -2.6086),
    "BS11": (51.5012, -2.6742),
    "BS13": (51.4098, -2.6118),
    "BS14": (51.4145, -2.5641),
    "BS15": (51.4590, -2.5057),
    "BS16": (51.4860, -2.5118),
    "BS20": (51.4792, -2.7608),
    "BS21": (51.4382, -2.8586),
    "BS22": (51.3498, -2.9314),
    "BS23": (51.3380, -2.9767),
    "BS24": (51.3445, -2.9188),
    "BS25": (51.3152, -2.8288),
    "BS26": (51.2863, -2.8147),
    "BS27": (51.2803, -2.7704),
    "BS28": (51.2274, -2.8733),
    "BS29": (51.3305, -2.8565),
    "BS30": (51.4486, -2.4720),
    "BS31": (51.4158, -2.4968),
    "BS32": (51.5439, -2.5603),
    "BS34": (51.5238, -2.5614),
    "BS35": (51.6044, -2.5329),
    "BS36": (51.5261, -2.4859),
    "BS37": (51.5386, -2.4184),
    "BS39": (51.3274, -2.4938),
    "BS40": (51.3812, -2.6863),
    "BS41": (51.4314, -2.6831),
    "BS48": (51.4288, -2.7483),
    "BS49": (51.3747, -2.7947),
}

COMMISSION_RATE = Decimal("0.05")
TWOPLACES = Decimal("0.01")


def normalise_postcode(postcode):
    return " ".join((postcode or "").upper().split())


def outward_code(postcode):
    normalised = normalise_postcode(postcode)
    return normalised.split(" ", 1)[0] if normalised else ""


def calculate_commission(amount):
    return (Decimal(amount) * COMMISSION_RATE).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_food_miles(postcode_a, postcode_b):
    code_a = outward_code(postcode_a)
    code_b = outward_code(postcode_b)
    if not code_a or not code_b:
        return None

    if code_a == code_b:
        return Decimal("0.0")

    point_a = BRISTOL_POSTCODE_COORDINATES.get(code_a)
    point_b = BRISTOL_POSTCODE_COORDINATES.get(code_b)
    if point_a is None or point_b is None:
        return None

    earth_radius_km = 6371.0
    lat1, lon1 = map(radians, point_a)
    lat2, lon2 = map(radians, point_b)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    arc = 2 * atan2(sqrt(haversine), sqrt(1 - haversine))
    miles = earth_radius_km * arc * 0.621371
    return Decimal(str(miles)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def order_item_requires_attention(order_item):
    return not minimum_lead_time_met(order_item)


def minimum_lead_time_met(order_item):
    fulfilment_date = order_item.order.fulfilment_date
    if fulfilment_date is None:
        return True

    created_date = timezone.localtime(order_item.order.created_at).date() if order_item.order.created_at else timezone.localdate()
    required_days = max(1, order_item.product.lead_time_hours // 24)
    return (fulfilment_date - created_date).days >= required_days


def item_food_miles(order_item):
    return calculate_food_miles(order_item.product.producer.postcode, order_item.order.delivery_postcode)


def settlement_window(for_date):
    week_start = for_date - timedelta(days=for_date.weekday())
    return week_start, week_start + timedelta(days=6)


@transaction.atomic
def sync_producer_settlements(producer):
    unsettled_items = (
        OrderItem.objects.select_related("order", "product", "settlement")
        .filter(product__producer=producer, order__paid=True, settlement__isnull=True)
        .exclude(status=OrderItem.STATUS_CANCELLED)
    )

    touched_ids = set()
    for item in unsettled_items:
        settlement_date = item.order.fulfilment_date or timezone.localtime(item.order.created_at).date()
        week_start, week_end = settlement_window(settlement_date)
        settlement, _ = ProducerSettlement.objects.get_or_create(
            producer=producer,
            week_start=week_start,
            week_end=week_end,
        )

        gross_amount = (item.price * item.quantity).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        commission_amount = calculate_commission(gross_amount)
        net_amount = (gross_amount - commission_amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        SettlementEntry.objects.create(
            settlement=settlement,
            order_item=item,
            gross_amount=gross_amount,
            commission_amount=commission_amount,
            net_amount=net_amount,
        )
        item.settlement = settlement
        item.save(update_fields=["settlement"])
        touched_ids.add(settlement.pk)

    settlements = ProducerSettlement.objects.filter(producer=producer)
    for settlement in settlements:
        settlement.recalculate_totals()
        settlement.save(update_fields=["gross_amount", "commission_amount", "net_amount"])
        touched_ids.add(settlement.pk)

    return ProducerSettlement.objects.filter(pk__in=touched_ids).order_by("-week_start")
