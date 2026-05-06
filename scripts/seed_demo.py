"""Demo seed script — populates BRFN with realistic data so every page has content.

Run inside the web container:
    docker compose exec web python manage.py shell < scripts/seed_demo.py
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Producer,
    ProducerContent,
    ProducerSettlement,
    Product,
    SettlementEntry,
    SurplusListing,
)

User = get_user_model()
today = timezone.localdate()

# ---- Categories ----
cat_veg, _ = Category.objects.get_or_create(name="Vegetables")
cat_fruit, _ = Category.objects.get_or_create(name="Fruit")
cat_dairy, _ = Category.objects.get_or_create(name="Dairy")
cat_bakery, _ = Category.objects.get_or_create(name="Bakery")
cat_pantry, _ = Category.objects.get_or_create(name="Pantry")

# ---- Producers (two for multi-vendor demo) ----
owner1, _ = User.objects.get_or_create(
    username="owner@cotswoldhill.test",
    defaults={"email": "owner@cotswoldhill.test"},
)
owner1.set_password("Harvest!Sundown42"); owner1.save()
prod1, _ = Producer.objects.update_or_create(
    user=owner1,
    defaults={"business_name": "Cotswold Hill Farm", "organic": True, "postcode": "BS1 4QA"},
)

owner2, _ = User.objects.get_or_create(
    username="hello@mendipbakery.test",
    defaults={"email": "hello@mendipbakery.test"},
)
owner2.set_password("Sourdough!2026"); owner2.save()
prod2, _ = Producer.objects.update_or_create(
    user=owner2,
    defaults={"business_name": "Mendip Valley Bakery", "organic": False, "postcode": "BA5 2EJ"},
)

# ---- Products ----
def upsert_product(producer, name, **kwargs):
    obj, _ = Product.objects.update_or_create(
        producer=producer, name=name, defaults=kwargs,
    )
    return obj

p_tomatoes = upsert_product(
    prod1, "Heritage Plum Tomatoes",
    category=cat_veg,
    description="Sun-ripened San Marzano-style plum tomatoes from the polytunnels at Cotswold Hill Farm. Sweet, low-acid, perfect for slow-roasting or fresh sauces.",
    price=Decimal("4.50"),
    stock_quantity=60,
    minimum_order_quantity=1,
    lead_time_hours=48,
    available_from=today - timedelta(days=2),
    available_to=today + timedelta(days=140),
    harvest_date=today - timedelta(days=2),
    best_before_date=today + timedelta(days=7),
    farm_origin="Cotswold Hill Farm, North Somerset",
    seasonal_highlight="Late-spring favourite",
    storage_guidance="Store at room temperature out of direct sunlight. Refrigerate only after slicing.",
    organic=True,
    allergen_info="None known. Packed in a facility that also handles celery and mustard.",
    is_active=True,
)

p_rhubarb = upsert_product(
    prod1, "Yorkshire Forced Rhubarb",
    category=cat_fruit,
    description="Tender, candy-pink stalks grown in the dark. Best stewed with orange zest or roasted with honey.",
    price=Decimal("3.80"),
    stock_quantity=4,  # low stock — exercises the badge
    minimum_order_quantity=1,
    lead_time_hours=48,
    available_from=today,
    available_to=today + timedelta(days=21),
    harvest_date=today,
    best_before_date=today + timedelta(days=10),
    farm_origin="Cotswold Hill Farm, North Somerset",
    seasonal_highlight="In season now",
    storage_guidance="Keep refrigerated. Use within 5 days of opening.",
    organic=True,
    allergen_info="No declared allergens.",
    is_active=True,
)

p_paused = upsert_product(
    prod1, "Cucumber (winter glasshouse)",
    category=cat_veg,
    description="Out of season — listing paused until June.",
    price=Decimal("1.95"),
    stock_quantity=0,
    organic=True,
    is_active=False,  # paused — exercises the inactive state
)

p_sourdough = upsert_product(
    prod2, "Wild-Yeast Sourdough Loaf",
    category=cat_bakery,
    description="24-hour fermented sourdough with a chewy crumb and burnished crust. Baked at the wood-fired oven each morning.",
    price=Decimal("5.20"),
    stock_quantity=18,
    minimum_order_quantity=1,
    lead_time_hours=48,
    available_from=today,
    farm_origin="Mendip Valley Bakery, Wells",
    seasonal_highlight="Daily bake",
    storage_guidance="Keep in paper, cut-side down. Best within 3 days. Slice and freeze for longer.",
    organic=False,
    allergen_info="Contains wheat and gluten. Made in a bakery that handles sesame and dairy.",
    is_active=True,
)

p_butter = upsert_product(
    prod2, "Cultured Salted Butter (250g)",
    category=cat_dairy,
    description="Hand-rolled cultured butter from a single Somerset herd. Slow-churned and lightly salted.",
    price=Decimal("4.20"),
    stock_quantity=24,
    minimum_order_quantity=1,
    lead_time_hours=48,
    farm_origin="Mendip Valley Dairy",
    seasonal_highlight="Year-round",
    storage_guidance="Refrigerate. Best within 14 days of opening.",
    organic=False,
    allergen_info="Contains milk.",
    is_active=True,
)

# ---- Customer ----
customer, _ = User.objects.get_or_create(
    username="shopper@brfn.test",
    defaults={"email": "shopper@brfn.test", "first_name": "Helena", "last_name": "Okafor"},
)
customer.set_password("BasketShop!9421"); customer.save()

# ---- A historical paid order (multi-vendor) for the order history page ----
order, created = Order.objects.update_or_create(
    customer=customer,
    reference="ORD-00001",
    defaults={
        "status": Order.STATUS_DELIVERED,
        "delivery_method": Order.DELIVERY_DELIVERY,
        "customer_name": "Helena Okafor",
        "customer_email": customer.email,
        "delivery_postcode": "BS6 7AA",
        "delivery_address": "12 Redland Park, Bristol",
        "fulfilment_date": today - timedelta(days=3),
        "notes": "Please leave with neighbour at no. 14 if out.",
        "paid": True,
        "confirmed_at": timezone.now() - timedelta(days=4),
    },
)
order.items.all().delete()
OrderItem.objects.create(order=order, product=p_tomatoes, quantity=2, price=p_tomatoes.price, status=OrderItem.STATUS_FULFILLED)
OrderItem.objects.create(order=order, product=p_sourdough, quantity=1, price=p_sourdough.price, status=OrderItem.STATUS_FULFILLED)

gross = sum(i.line_total for i in order.items.all())
commission = (gross * Decimal("0.05")).quantize(Decimal("0.01"))
producer_amount = gross - commission

Payment.objects.update_or_create(
    order=order,
    defaults={
        "total_amount": gross,
        "network_commission": commission,
        "producer_amount": producer_amount,
        "status": Payment.STATUS_COMPLETED,
        "completed_at": timezone.now() - timedelta(days=4),
        "stripe_payment_intent_id": "pi_demo_00001",
    },
)

# ---- A pending pre-payment order for an in-flight checkout/payment view ----
pending, _ = Order.objects.update_or_create(
    customer=customer,
    reference="ORD-00002",
    defaults={
        "status": Order.STATUS_PENDING,
        "delivery_method": Order.DELIVERY_COLLECTION,
        "customer_name": "Helena Okafor",
        "customer_email": customer.email,
        "delivery_postcode": "BS6 7AA",
        "fulfilment_date": today + timedelta(days=2),
        "paid": False,
    },
)
pending.items.all().delete()
OrderItem.objects.create(order=pending, product=p_rhubarb, quantity=2, price=p_rhubarb.price)
OrderItem.objects.create(order=pending, product=p_butter, quantity=1, price=p_butter.price)

# ---- Settlement for the producer settlements page ----
week_start = today - timedelta(days=today.weekday() + 7)  # last week's Monday
week_end = week_start + timedelta(days=6)
settlement, _ = ProducerSettlement.objects.update_or_create(
    producer=prod1, week_start=week_start, week_end=week_end,
    defaults={
        "status": ProducerSettlement.STATUS_PENDING,
        "gross_amount": Decimal("0.00"),
        "commission_amount": Decimal("0.00"),
        "net_amount": Decimal("0.00"),
        "payout_reference": "",
        "notes": "Auto-generated for demo seed.",
    },
)
settlement.entries.all().delete()
for item in order.items.filter(product__producer=prod1):
    g = item.line_total
    c = (g * Decimal("0.05")).quantize(Decimal("0.01"))
    n = g - c
    SettlementEntry.objects.create(
        settlement=settlement, order_item=item,
        gross_amount=g, commission_amount=c, net_amount=n,
    )
settlement.recalculate_totals()
settlement.save()

# ---- Surplus listing ----
SurplusListing.objects.update_or_create(
    producer=prod1, product=p_rhubarb,
    defaults={
        "quantity": 3,
        "original_price": p_rhubarb.price,
        "discount_percent": 25,
        "discounted_price": (p_rhubarb.price * Decimal("0.75")).quantize(Decimal("0.01")),
        "available_until": timezone.now() + timedelta(days=2),
        "note": "Last of this week's pull — short window before they oversoften.",
        "is_active": True,
    },
)

# ---- Producer content ----
ProducerContent.objects.update_or_create(
    producer=prod1, title="Slow-roasted plum tomato sauce",
    defaults={
        "product": p_tomatoes,
        "content_type": ProducerContent.TYPE_RECIPE,
        "season": "Late spring",
        "summary": "A thick, sweet sauce that freezes well — three ingredients, two hours.",
        "body": "Halve the tomatoes lengthways, toss with olive oil, salt, and a few crushed garlic cloves. Roast at 140C for two hours until collapsed and caramelised at the edges. Blitz briefly for sauce, leave chunky for bruschetta.",
        "is_published": True,
    },
)
ProducerContent.objects.update_or_create(
    producer=prod1, title="Storing rhubarb so it lasts the week",
    defaults={
        "product": p_rhubarb,
        "content_type": ProducerContent.TYPE_STORAGE,
        "season": "Spring",
        "summary": "Wrap in damp paper, refrigerate, and don't wash until use.",
        "body": "Rhubarb starts to go limp once it's washed. Keep stalks dry, wrapped loosely in paper, in the bottom of the fridge. Use within five days for best texture.",
        "is_published": True,
    },
)

print("--- Seed complete ---")
print(f"Producers: {Producer.objects.count()}")
print(f"Products:  {Product.objects.count()}")
print(f"Orders:    {Order.objects.count()}")
print(f"Settlements: {ProducerSettlement.objects.count()}")
print(f"Surplus listings: {SurplusListing.objects.count()}")
print(f"Producer content: {ProducerContent.objects.count()}")
print()
print("Login as producer:  owner@cotswoldhill.test / Harvest!Sundown42")
print("Login as bakery:    hello@mendipbakery.test / Sourdough!2026")
print("Login as customer:  shopper@brfn.test / BasketShop!9421")
