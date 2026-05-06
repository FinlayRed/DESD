"""
Management command to seed the database with sample data for demo purposes.

Usage:
    docker compose exec web python manage.py seed_demo_data
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Producer,
    ProducerContent,
    Product,
    SurplusListing,
    TraceabilityRecord,
)
from core.payment_service import process_order_payment
from core.services import sync_producer_settlements
from core.traceability import create_traceability_records

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds the database with sample orders, payments and traceability records for demo."

    def handle(self, *args, **options):
        self.stdout.write("Creating demo data...\n")

        # ---- Categories ----
        veg, _ = Category.objects.get_or_create(name="Vegetables", defaults={"description": "Fresh local vegetables"})
        dairy, _ = Category.objects.get_or_create(name="Dairy & Eggs", defaults={"description": "Milk, cheese, eggs and more"})
        bakery, _ = Category.objects.get_or_create(name="Bakery", defaults={"description": "Fresh bread and baked goods"})
        pantry, _ = Category.objects.get_or_create(name="Pantry", defaults={"description": "Preserves, grains and store cupboard staples"})

        # ---- Producer 1: Bristol Valley Farm ----
        user1, created = User.objects.get_or_create(
            username="jane@bristolvalleyfarm.com",
            defaults={"email": "jane@bristolvalleyfarm.com", "first_name": "Jane", "last_name": "Smith"},
        )
        if created:
            user1.set_password("TestPass123!")
            user1.save()
        producer1, _ = Producer.objects.get_or_create(
            user=user1,
            defaults={"business_name": "Bristol Valley Farm", "postcode": "BS1 4DJ", "organic": True},
        )

        # ---- Producer 2: Hillside Dairy ----
        user2, created = User.objects.get_or_create(
            username="tom@hillsidedairy.com",
            defaults={"email": "tom@hillsidedairy.com", "first_name": "Tom", "last_name": "Davies"},
        )
        if created:
            user2.set_password("TestPass123!")
            user2.save()
        producer2, _ = Producer.objects.get_or_create(
            user=user2,
            defaults={"business_name": "Hillside Dairy", "postcode": "BS40 5SA", "organic": False},
        )

        # ---- Producer 3: Sunrise Bakery ----
        user3, created = User.objects.get_or_create(
            username="amy@sunrisebakery.com",
            defaults={"email": "amy@sunrisebakery.com", "first_name": "Amy", "last_name": "Chen"},
        )
        if created:
            user3.set_password("TestPass123!")
            user3.save()
        producer3, _ = Producer.objects.get_or_create(
            user=user3,
            defaults={"business_name": "Sunrise Bakery", "postcode": "BS6 7AA", "organic": False},
        )

        # ---- Products ----
        carrots, _ = Product.objects.get_or_create(
            producer=producer1, name="Organic Carrots",
            defaults={
                "category": veg, "description": "Sweet heritage carrots, hand-pulled",
                "price": Decimal("2.50"), "stock_quantity": 40, "organic": True,
                "allergen_info": "", "farm_origin": "Bristol Valley Farm",
                "harvest_date": timezone.now().date() - timedelta(days=2),
                "best_before_date": timezone.now().date() + timedelta(days=10),
                "is_active": True,
            },
        )
        tomatoes, _ = Product.objects.get_or_create(
            producer=producer1, name="Organic Tomatoes",
            defaults={
                "category": veg, "description": "Vine-ripened organic tomatoes",
                "price": Decimal("3.00"), "stock_quantity": 30, "organic": True,
                "allergen_info": "", "farm_origin": "Bristol Valley Farm",
                "harvest_date": timezone.now().date() - timedelta(days=1),
                "best_before_date": timezone.now().date() + timedelta(days=7),
                "is_active": True,
            },
        )
        milk, _ = Product.objects.get_or_create(
            producer=producer2, name="Fresh Whole Milk",
            defaults={
                "category": dairy, "description": "Full cream milk from grass-fed cows",
                "price": Decimal("1.80"), "stock_quantity": 60, "organic": False,
                "allergen_info": "Contains: Milk", "farm_origin": "Hillside Dairy",
                "harvest_date": timezone.now().date(),
                "best_before_date": timezone.now().date() + timedelta(days=5),
                "is_active": True,
            },
        )
        cheese, _ = Product.objects.get_or_create(
            producer=producer2, name="Cheddar Cheese",
            defaults={
                "category": dairy, "description": "Mature cheddar, aged 12 months",
                "price": Decimal("5.50"), "stock_quantity": 20, "organic": False,
                "allergen_info": "Contains: Milk", "farm_origin": "Hillside Dairy",
                "harvest_date": timezone.now().date() - timedelta(days=30),
                "best_before_date": timezone.now().date() + timedelta(days=90),
                "is_active": True,
            },
        )
        sourdough, _ = Product.objects.get_or_create(
            producer=producer3, name="Sourdough Loaf",
            defaults={
                "category": bakery, "description": "Traditional sourdough, 24-hour ferment",
                "price": Decimal("4.00"), "stock_quantity": 15, "organic": False,
                "allergen_info": "Contains: Wheat (Gluten)", "farm_origin": "Sunrise Bakery",
                "harvest_date": timezone.now().date(),
                "best_before_date": timezone.now().date() + timedelta(days=3),
                "is_active": True,
            },
        )
        walnut_bread, _ = Product.objects.get_or_create(
            producer=producer3, name="Walnut Bread",
            defaults={
                "category": bakery, "description": "Rustic walnut and honey loaf",
                "price": Decimal("4.50"), "stock_quantity": 10, "organic": False,
                "allergen_info": "Contains: Wheat (Gluten), Nuts (Walnuts)",
                "farm_origin": "Sunrise Bakery",
                "harvest_date": timezone.now().date(),
                "best_before_date": timezone.now().date() + timedelta(days=3),
                "is_active": True,
            },
        )
        eggs, _ = Product.objects.get_or_create(
            producer=producer2, name="Free Range Eggs (6 pack)",
            defaults={
                "category": dairy, "description": "Mixed-size eggs from pasture-raised hens",
                "price": Decimal("2.90"), "stock_quantity": 5, "organic": False,
                "allergen_info": "Contains: Eggs", "farm_origin": "Hillside Dairy",
                "harvest_date": timezone.now().date() - timedelta(days=1),
                "best_before_date": timezone.now().date() + timedelta(days=21),
                "seasonal_highlight": "Low stock",
                "storage_guidance": "Keep refrigerated after purchase.",
                "is_active": True,
            },
        )
        jam, _ = Product.objects.get_or_create(
            producer=producer1, name="Blackcurrant Jam",
            defaults={
                "category": pantry, "description": "Small-batch blackcurrant jam made with surplus summer fruit",
                "price": Decimal("3.75"), "stock_quantity": 25, "organic": True,
                "allergen_info": "No declared allergens", "farm_origin": "Bristol Valley Farm",
                "available_from": timezone.now().date() - timedelta(days=30),
                "available_to": timezone.now().date() + timedelta(days=180),
                "best_before_date": timezone.now().date() + timedelta(days=365),
                "seasonal_highlight": "Preserved summer crop",
                "storage_guidance": "Refrigerate after opening and use within four weeks.",
                "is_active": True,
            },
        )
        asparagus, _ = Product.objects.get_or_create(
            producer=producer1, name="Early Season Asparagus",
            defaults={
                "category": veg, "description": "Preview listing for the first asparagus cut of the season",
                "price": Decimal("4.25"), "stock_quantity": 12, "organic": True,
                "allergen_info": "No declared allergens", "farm_origin": "Bristol Valley Farm",
                "available_from": timezone.now().date() + timedelta(days=14),
                "available_to": timezone.now().date() + timedelta(days=45),
                "harvest_date": timezone.now().date() + timedelta(days=14),
                "best_before_date": timezone.now().date() + timedelta(days=21),
                "seasonal_highlight": "Upcoming season",
                "storage_guidance": "Stand spears in a little water and chill.",
                "is_active": True,
            },
        )
        paused_rolls, _ = Product.objects.get_or_create(
            producer=producer3, name="Seeded Breakfast Rolls",
            defaults={
                "category": bakery, "description": "Paused listing used to test inactive producer products",
                "price": Decimal("3.20"), "stock_quantity": 0, "organic": False,
                "allergen_info": "Contains: Wheat (Gluten), Sesame", "farm_origin": "Sunrise Bakery",
                "is_active": False,
            },
        )

        # ---- Customer accounts ----
        cust1, created = User.objects.get_or_create(
            username="robert.johnson@email.com",
            defaults={"email": "robert.johnson@email.com", "first_name": "Robert", "last_name": "Johnson"},
        )
        if created:
            cust1.set_password("TestPass123!")
            cust1.save()

        cust2, created = User.objects.get_or_create(
            username="sarah.williams@email.com",
            defaults={"email": "sarah.williams@email.com", "first_name": "Sarah", "last_name": "Williams"},
        )
        if created:
            cust2.set_password("TestPass123!")
            cust2.save()

        # =============================================
        # ORDER 1: Single producer (TC-007)
        # Robert buys from Bristol Valley Farm only
        # =============================================
        order1, o1_created = Order.objects.get_or_create(
            customer=cust1,
            reference="ORD-00001",
            defaults={
                "status": Order.STATUS_CONFIRMED,
                "delivery_method": Order.DELIVERY_DELIVERY,
                "customer_name": "Robert Johnson",
                "customer_email": "robert.johnson@email.com",
                "delivery_postcode": "BS1 5JG",
                "fulfilment_date": timezone.now().date() + timedelta(days=3),
                "notes": "Please leave at front door",
                "paid": False,
            },
        )
        if o1_created:
            OrderItem.objects.create(
                order=order1, product=carrots,
                quantity=3, price=carrots.price, status=OrderItem.STATUS_ACCEPTED,
            )
            OrderItem.objects.create(
                order=order1, product=tomatoes,
                quantity=2, price=tomatoes.price, status=OrderItem.STATUS_ACCEPTED,
            )
            # Process payment
            process_order_payment(order1)
            create_traceability_records(order1)
            self.stdout.write(self.style.SUCCESS(
                f"  Order 1 (single producer): £{3*2.50 + 2*3.00:.2f} – Bristol Valley Farm"
            ))

        # =============================================
        # ORDER 2: Multi-vendor order (TC-008)
        # Sarah buys from all three producers
        # =============================================
        order2, o2_created = Order.objects.get_or_create(
            customer=cust2,
            reference="ORD-00002",
            defaults={
                "status": Order.STATUS_PENDING,
                "delivery_method": Order.DELIVERY_DELIVERY,
                "customer_name": "Sarah Williams",
                "customer_email": "sarah.williams@email.com",
                "delivery_postcode": "BS8 1TH",
                "fulfilment_date": timezone.now().date() + timedelta(days=4),
                "notes": "",
                "paid": False,
            },
        )
        if o2_created:
            OrderItem.objects.create(
                order=order2, product=carrots,
                quantity=2, price=carrots.price, status=OrderItem.STATUS_PENDING,
            )
            OrderItem.objects.create(
                order=order2, product=milk,
                quantity=4, price=milk.price, status=OrderItem.STATUS_PENDING,
            )
            OrderItem.objects.create(
                order=order2, product=cheese,
                quantity=1, price=cheese.price, status=OrderItem.STATUS_PENDING,
            )
            OrderItem.objects.create(
                order=order2, product=sourdough,
                quantity=2, price=sourdough.price, status=OrderItem.STATUS_PENDING,
            )
            # Process payment
            process_order_payment(order2)
            create_traceability_records(order2)
            self.stdout.write(self.style.SUCCESS(
                f"  Order 2 (multi-vendor): £{2*2.50 + 4*1.80 + 1*5.50 + 2*4.00:.2f} – 3 producers"
            ))

        # =============================================
        # ORDER 3: Another single producer order
        # Robert orders bakery items
        # =============================================
        order3, o3_created = Order.objects.get_or_create(
            customer=cust1,
            reference="ORD-00003",
            defaults={
                "status": Order.STATUS_DELIVERED,
                "delivery_method": Order.DELIVERY_COLLECTION,
                "customer_name": "Robert Johnson",
                "customer_email": "robert.johnson@email.com",
                "delivery_postcode": "BS1 5JG",
                "fulfilment_date": timezone.now().date() - timedelta(days=2),
                "notes": "Collecting Saturday morning",
                "paid": False,
            },
        )
        if o3_created:
            OrderItem.objects.create(
                order=order3, product=sourdough,
                quantity=1, price=sourdough.price, status=OrderItem.STATUS_FULFILLED,
            )
            OrderItem.objects.create(
                order=order3, product=walnut_bread,
                quantity=1, price=walnut_bread.price, status=OrderItem.STATUS_FULFILLED,
            )
            # Process payment
            process_order_payment(order3)
            create_traceability_records(order3)
            self.stdout.write(self.style.SUCCESS(
                f"  Order 3 (single producer): £{4.00 + 4.50:.2f} – Sunrise Bakery"
            ))

        # =============================================
        # ORDER 4: Pending payment checkout
        # Helena has reached the payment page but not completed payment.
        # =============================================
        cust3, created = User.objects.get_or_create(
            username="helena.okafor@email.com",
            defaults={"email": "helena.okafor@email.com", "first_name": "Helena", "last_name": "Okafor"},
        )
        if created:
            cust3.set_password("TestPass123!")
            cust3.save()

        order4, o4_created = Order.objects.get_or_create(
            customer=cust3,
            reference="ORD-00004",
            defaults={
                "status": Order.STATUS_PENDING,
                "delivery_method": Order.DELIVERY_COLLECTION,
                "customer_name": "Helena Okafor",
                "customer_email": "helena.okafor@email.com",
                "delivery_postcode": "BS6 7AA",
                "delivery_address": "Collection from Bristol community hub",
                "fulfilment_date": timezone.now().date() + timedelta(days=3),
                "collection_date": timezone.now().date() + timedelta(days=3),
                "notes": "Manual test: complete payment from the payment page.",
                "paid": False,
            },
        )
        if o4_created:
            OrderItem.objects.create(order=order4, product=eggs, quantity=1, price=eggs.price)
            OrderItem.objects.create(order=order4, product=jam, quantity=2, price=jam.price)
            Payment.objects.create(
                order=order4,
                total_amount=eggs.price + (jam.price * 2),
                network_commission=((eggs.price + (jam.price * 2)) * Decimal("0.05")).quantize(Decimal("0.01")),
                producer_amount=((eggs.price + (jam.price * 2)) * Decimal("0.95")).quantize(Decimal("0.01")),
                status=Payment.STATUS_PENDING,
            )
            self.stdout.write(self.style.SUCCESS("  Order 4 (pending payment): Helena checkout in progress"))

        # =============================================
        # ORDER 5: Mixed producer workflow statuses
        # Tests customer progress rollup and producer order filters.
        # =============================================
        order5, o5_created = Order.objects.get_or_create(
            customer=cust2,
            reference="ORD-00005",
            defaults={
                "status": Order.STATUS_CONFIRMED,
                "delivery_method": Order.DELIVERY_DELIVERY,
                "customer_name": "Sarah Williams",
                "customer_email": "sarah.williams@email.com",
                "delivery_postcode": "BS9 3AA",
                "delivery_address": "44 Henleaze Road, Bristol",
                "fulfilment_date": timezone.now().date() + timedelta(days=2),
                "notes": "Manual test: producer line items intentionally have different statuses.",
                "paid": False,
            },
        )
        if o5_created:
            OrderItem.objects.create(order=order5, product=tomatoes, quantity=1, price=tomatoes.price, status=OrderItem.STATUS_ACCEPTED)
            OrderItem.objects.create(order=order5, product=eggs, quantity=2, price=eggs.price, status=OrderItem.STATUS_PREPARING)
            OrderItem.objects.create(order=order5, product=sourdough, quantity=1, price=sourdough.price, status=OrderItem.STATUS_READY)
            process_order_payment(order5)
            create_traceability_records(order5)
            self.stdout.write(self.style.SUCCESS("  Order 5 (mixed statuses): accepted/preparing/ready across 3 producers"))

        # ---- Surplus listings and producer content ----
        surplus_price = (tomatoes.price * Decimal("0.70")).quantize(Decimal("0.01"))
        SurplusListing.objects.update_or_create(
            producer=producer1,
            product=tomatoes,
            defaults={
                "quantity": 6,
                "original_price": tomatoes.price,
                "discount_percent": 30,
                "discounted_price": surplus_price,
                "available_until": timezone.now() + timedelta(days=2),
                "note": "Manual test surplus listing: ripe tomatoes for quick sale.",
                "is_active": True,
            },
        )
        ProducerContent.objects.update_or_create(
            producer=producer1,
            title="Roasted tomato freezer sauce",
            defaults={
                "product": tomatoes,
                "content_type": ProducerContent.TYPE_RECIPE,
                "season": "Spring",
                "summary": "A simple sauce for using ripe tomatoes before they soften.",
                "body": "Halve tomatoes, roast low with oil and garlic, then freeze in portions.",
                "is_published": True,
            },
        )
        ProducerContent.objects.update_or_create(
            producer=producer3,
            title="Keeping sourdough fresh",
            defaults={
                "product": sourdough,
                "content_type": ProducerContent.TYPE_STORAGE,
                "season": "Year-round",
                "summary": "Keep the cut side covered and freeze slices if needed.",
                "body": "Store sourdough in paper at room temperature. Slice and freeze anything not eaten within two days.",
                "is_published": True,
            },
        )

        # Generate settlement rows for paid seeded orders so the settlement screens have data immediately.
        for producer in (producer1, producer2, producer3):
            sync_producer_settlements(producer)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data created successfully!"))
        self.stdout.write("")
        self.stdout.write("Summary:")
        self.stdout.write(f"  Producers: 3")
        self.stdout.write(f"  Products:  10")
        self.stdout.write(f"  Customers: 3")
        self.stdout.write(f"  Orders:    5 (4 paid with traceability records, 1 pending payment)")
        self.stdout.write(f"  Surplus listings: 1")
        self.stdout.write(f"  Producer content: 2")
        self.stdout.write("")
        self.stdout.write("Test logins: all seeded users use password TestPass123!")
        self.stdout.write("  Producers: jane@bristolvalleyfarm.com, tom@hillsidedairy.com, amy@sunrisebakery.com")
        self.stdout.write("  Customers: robert.johnson@email.com, sarah.williams@email.com, helena.okafor@email.com")
        self.stdout.write("")
        self.stdout.write("Visit /admin-reports/ to see the data in your financial dashboard.")
