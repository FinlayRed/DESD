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
    Product,
    TraceabilityRecord,
)
from core.payment_service import process_order_payment
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

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data created successfully!"))
        self.stdout.write("")
        self.stdout.write("Summary:")
        self.stdout.write(f"  Producers: 3")
        self.stdout.write(f"  Products:  6")
        self.stdout.write(f"  Customers: 2")
        self.stdout.write(f"  Orders:    3 (all paid with traceability records)")
        self.stdout.write("")
        self.stdout.write("Visit /admin-reports/ to see the data in your financial dashboard.")
