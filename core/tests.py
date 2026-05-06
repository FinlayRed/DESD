from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Category,
    Order,
    OrderItem,
    Producer,
    ProducerContent,
    ProducerSettlement,
    Product,
    SurplusListing,
)
from .services import calculate_food_miles


class ProducerAuthTests(TestCase):
    def test_producer_register_creates_user_and_profile(self):
        response = self.client.post(
            reverse("core:producer-register"),
            {
                "business_name": "Farm Co",
                "postcode": "bs1 1aa",
                "organic": True,
                "email": "producer@example.com",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )

        self.assertRedirects(response, reverse("core:dashboard"))
        user_model = get_user_model()
        user = user_model.objects.get(email="producer@example.com")
        producer = Producer.objects.get(user=user)
        self.assertEqual(producer.business_name, "Farm Co")
        self.assertEqual(producer.postcode, "BS1 1AA")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.id))

    def test_producer_login_with_email(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="producer@example.com",
            email="producer@example.com",
            password="testpass123",
        )
        Producer.objects.create(user=user, business_name="Farm Co", postcode="BS1 1AA")

        response = self.client.post(
            reverse("core:producer-login"),
            {
                "email": "producer@example.com",
                "password": "testpass123",
            },
        )

        self.assertRedirects(response, reverse("core:dashboard"))
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.id))

    def test_login_rejects_non_producer_account(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
        )

        response = self.client.post(
            reverse("core:producer-login"),
            {
                "email": "customer@example.com",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account is not registered as a producer.")


class CustomerAuthTests(TestCase):
    def test_customer_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("core:customer-register"),
            {
                "email": "customer@example.com",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )

        self.assertRedirects(response, reverse("core:customer-product-list"))
        user_model = get_user_model()
        user = user_model.objects.get(email="customer@example.com")
        self.assertEqual(user.username, "customer@example.com")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.id))

    def test_customer_login_with_email(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
        )

        response = self.client.post(
            reverse("core:customer-login"),
            {
                "email": "customer@example.com",
                "password": "testpass123",
            },
        )

        self.assertRedirects(response, reverse("core:customer-product-list"))
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.id))

    def test_customer_login_rejects_producer_account(self):
        user_model = get_user_model()
        producer_user = user_model.objects.create_user(
            username="producer@example.com",
            email="producer@example.com",
            password="testpass123",
        )
        Producer.objects.create(user=producer_user, business_name="Farm Co", postcode="BS1 1AA")

        response = self.client.post(
            reverse("core:customer-login"),
            {
                "email": "producer@example.com",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account is registered as a producer. Please use producer login.")

    def test_customer_login_rejects_invalid_password(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
        )

        response = self.client.post(
            reverse("core:customer-login"),
            {
                "email": "customer@example.com",
                "password": "wrongpass123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct email and password.")

    def test_customer_logout_clears_session(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:customer-logout"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProducerFeatureBase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.producer_user = user_model.objects.create_user(
            username="producer@example.com",
            email="producer@example.com",
            password="testpass123",
        )
        self.other_user = user_model.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="testpass123",
        )
        self.customer_user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
            first_name="Local",
            last_name="Buyer",
        )
        self.producer = Producer.objects.create(
            user=self.producer_user,
            business_name="Producer One",
            postcode="BS1 1AA",
            organic=True,
        )
        self.other_producer = Producer.objects.create(
            user=self.other_user,
            business_name="Producer Two",
            postcode="BS32 4AQ",
        )
        self.category = Category.objects.create(name="Vegetables")
        self.other_category = Category.objects.create(name="Dairy")
        self.product = Product.objects.create(
            producer=self.producer,
            name="Carrots",
            description="Fresh carrots",
            price=Decimal("1.99"),
            category=self.category,
            stock_quantity=12,
            minimum_order_quantity=1,
            lead_time_hours=48,
            farm_origin="Easton Farm",
            organic=True,
            allergen_info="None",
        )
        self.other_product = Product.objects.create(
            producer=self.other_producer,
            name="Milk",
            description="Organic milk",
            price=Decimal("2.10"),
            category=self.other_category,
            stock_quantity=20,
            minimum_order_quantity=1,
            lead_time_hours=48,
        )


class ProductCrudTests(ProducerFeatureBase):
    def test_product_list_only_shows_owner_products(self):
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:product-list"))

        self.assertContains(response, "Carrots")
        self.assertNotContains(response, "Milk")

    def test_create_product_assigns_producer_and_traceability_fields(self):
        self.client.force_login(self.producer_user)

        response = self.client.post(
            reverse("core:product-create"),
            {
                "name": "Tomatoes",
                "description": "Sweet tomatoes",
                "price": "3.50",
                "category": self.category.pk,
                "stock_quantity": 8,
                "minimum_order_quantity": 2,
                "lead_time_hours": 48,
                "available_from": "2026-06-01",
                "available_to": "2026-06-30",
                "harvest_date": "2026-05-31",
                "best_before_date": "2026-06-07",
                "farm_origin": "North Plot",
                "seasonal_highlight": "Peak June crop",
                "organic": True,
                "allergen_info": "Packed in a nut-free area",
                "storage_guidance": "Keep cool and dry",
                "is_active": True,
            },
        )

        self.assertRedirects(response, reverse("core:product-list"))
        product = Product.objects.get(name="Tomatoes")
        self.assertEqual(product.producer, self.producer)
        self.assertEqual(product.farm_origin, "North Plot")
        self.assertEqual(product.stock_quantity, 8)
        self.assertTrue(product.organic)

    def test_cannot_edit_other_users_product(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:product-update", kwargs={"pk": self.other_product.pk}),
            {
                "name": "Updated Milk",
                "description": "Should not update",
                "price": "2.50",
                "category": self.other_category.pk,
                "stock_quantity": 4,
                "minimum_order_quantity": 1,
                "lead_time_hours": 48,
                "organic": False,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.other_product.refresh_from_db()
        self.assertEqual(self.other_product.name, "Milk")

    def test_date_validation_on_form(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:product-create"),
            {
                "name": "Spinach",
                "description": "Seasonal greens",
                "price": "1.20",
                "category": self.category.pk,
                "stock_quantity": 5,
                "minimum_order_quantity": 1,
                "lead_time_hours": 48,
                "available_from": "2026-03-10",
                "available_to": "2026-03-01",
                "harvest_date": "2026-03-02",
                "best_before_date": "2026-03-01",
                "organic": True,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Available to date cannot be before available from date.")
        self.assertContains(response, "Best before date cannot be before the harvest date.")
        self.assertFalse(Product.objects.filter(name="Spinach").exists())


class OrderWorkflowTests(ProducerFeatureBase):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            customer=self.customer_user,
            paid=True,
            customer_name="Local Buyer",
            customer_email="buyer@example.com",
            delivery_method=Order.DELIVERY_DELIVERY,
            delivery_postcode="BS32 4AQ",
            fulfilment_date=timezone.localdate() + timedelta(days=1),
            notes="Leave by the side gate",
        )
        self.own_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3,
            price=Decimal("1.99"),
            status=OrderItem.STATUS_PENDING,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.other_product,
            quantity=2,
            price=Decimal("2.10"),
            status=OrderItem.STATUS_READY,
        )

    def test_order_list_only_shows_producer_items(self):
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:order-list"))

        self.assertContains(response, self.order.reference)
        self.assertContains(response, "Carrots")
        self.assertNotContains(response, "Milk")
        self.assertContains(response, "Under 48h")

    def test_order_item_update_is_scoped_to_producer(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:order-item-update", kwargs={"pk": self.own_item.pk}),
            {
                "status": OrderItem.STATUS_PREPARING,
                "producer_notes": "Packing for tomorrow morning.",
            },
        )

        self.assertRedirects(response, reverse("core:order-detail", kwargs={"pk": self.order.pk}))
        self.own_item.refresh_from_db()
        self.assertEqual(self.own_item.status, OrderItem.STATUS_PREPARING)
        self.assertEqual(self.own_item.producer_notes, "Packing for tomorrow morning.")

    def test_order_detail_shows_food_miles(self):
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:order-detail", kwargs={"pk": self.order.pk}))

        self.assertContains(response, "miles")
        self.assertEqual(calculate_food_miles("BS1 1AA", "BS32 4AQ"), Decimal("6.3"))


class SettlementTests(ProducerFeatureBase):
    def test_settlement_list_creates_weekly_audit_trail(self):
        order = Order.objects.create(
            customer=self.customer_user,
            paid=True,
            fulfilment_date=timezone.localdate(),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=4,
            price=Decimal("2.50"),
            status=OrderItem.STATUS_READY,
        )

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:settlement-list"))

        self.assertEqual(response.status_code, 200)
        settlement = ProducerSettlement.objects.get(producer=self.producer)
        self.assertEqual(settlement.gross_amount, Decimal("10.00"))
        self.assertEqual(settlement.commission_amount, Decimal("0.50"))
        self.assertEqual(settlement.net_amount, Decimal("9.50"))
        self.assertContains(response, "10.00")
        self.assertContains(response, "0.50")
        self.assertContains(response, "9.50")


class SurplusAndContentTests(ProducerFeatureBase):
    def test_create_surplus_listing_for_own_product(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:surplus-create"),
            {
                "product": self.product.pk,
                "quantity": 6,
                "discounted_price": "1.49",
                "available_until": (timezone.localtime() + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M"),
                "note": "Use within two days.",
                "is_active": True,
            },
        )

        self.assertRedirects(response, reverse("core:surplus-list"))
        listing = SurplusListing.objects.get(product=self.product)
        self.assertEqual(listing.producer, self.producer)
        self.assertEqual(listing.original_price, self.product.price)
        self.assertEqual(listing.discount_percent, 25)

    def test_surplus_listing_rejects_discounted_price_above_product_price(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:surplus-create"),
            {
                "product": self.product.pk,
                "quantity": 6,
                "discounted_price": "2.50",
                "available_until": (timezone.localtime() + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M"),
                "note": "Use within two days.",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discounted price cannot be more than the product price.")

    def test_surplus_form_restricts_products_to_owner(self):
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:surplus-create"))

        self.assertContains(response, "Carrots")
        self.assertNotContains(response, "Milk")

    def test_create_producer_content(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:content-create"),
            {
                "content_type": ProducerContent.TYPE_RECIPE,
                "title": "Spring carrot slaw",
                "season": "Spring",
                "product": self.product.pk,
                "summary": "A quick seasonal side.",
                "body": "Shred carrots, add herbs, then chill before serving.",
                "is_published": True,
            },
        )

        self.assertRedirects(response, reverse("core:content-list"))
        content = ProducerContent.objects.get(title="Spring carrot slaw")
        self.assertEqual(content.producer, self.producer)
        self.assertEqual(content.product, self.product)

    def test_dashboard_summarises_producer_tools(self):
        ProducerContent.objects.create(
            producer=self.producer,
            product=self.product,
            content_type=ProducerContent.TYPE_STORY,
            title="Early harvest notes",
            body="The polytunnel crop came in a week ahead of schedule.",
        )
        SurplusListing.objects.create(
            producer=self.producer,
            product=self.product,
            quantity=2,
            original_price=Decimal("1.99"),
            discount_percent=20,
            discounted_price=Decimal("1.59"),
            available_until=timezone.localtime() + timedelta(hours=5),
        )

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:dashboard"))

        self.assertContains(response, "Producer One")
        self.assertContains(response, "Stories & guides")
        self.assertContains(response, "Surplus listings")
