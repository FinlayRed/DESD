import csv
from io import StringIO
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Producer,
    ProducerContent,
    ProducerSettlement,
    Product,
    SurplusListing,
    TraceabilityRecord,
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
    def test_customer_register_get_renders_form(self):
        response = self.client.get(reverse("core:customer-register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your customer account")

    def test_customer_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("core:customer-register"),
            {
                "email": "customer@example.com",
                "first_name": "Alex",
                "last_name": "Shopper",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )

        self.assertRedirects(response, reverse("core:customer-product-list"))
        user_model = get_user_model()
        user = user_model.objects.get(email="customer@example.com")
        self.assertEqual(user.username, "customer@example.com")
        self.assertEqual(user.first_name, "Alex")
        self.assertEqual(user.last_name, "Shopper")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.id))

    def test_customer_register_normalizes_email_to_lowercase(self):
        self.client.post(
            reverse("core:customer-register"),
            {
                "email": "  Customer@EXAMPLE.com  ",
                "first_name": "Alex",
                "last_name": "Shopper",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        user_model = get_user_model()
        user = user_model.objects.get(username="customer@example.com")
        self.assertEqual(user.email, "customer@example.com")

    def test_customer_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("core:customer-register"),
            {
                "email": "customer@example.com",
                "first_name": "Alex",
                "last_name": "Shopper",
                "password1": "strongpass123",
                "password2": "otherpass999",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertFalse(get_user_model().objects.filter(email="customer@example.com").exists())

    def test_customer_register_rejects_duplicate_email(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="existingpass123",
        )
        response = self.client.post(
            reverse("core:customer-register"),
            {
                "email": "customer@example.com",
                "first_name": "Alex",
                "last_name": "Shopper",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertEqual(user_model.objects.filter(email="customer@example.com").count(), 1)

    def test_customer_register_rejects_duplicate_email_case_insensitive(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="existingpass123",
        )
        response = self.client.post(
            reverse("core:customer-register"),
            {
                "email": "CUSTOMER@EXAMPLE.COM",
                "first_name": "Alex",
                "last_name": "Shopper",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")

    def test_customer_register_requires_first_and_last_name(self):
        response = self.client.post(
            reverse("core:customer-register"),
            {
                "email": "customer@example.com",
                "first_name": "",
                "last_name": "Shopper",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(get_user_model().objects.filter(email="customer@example.com").exists())

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

        response = self.client.post(reverse("core:customer-logout"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class CustomerProfileTests(TestCase):
    def test_profile_requires_login(self):
        response = self.client.get(reverse("core:customer-profile"))
        self.assertRedirects(response, f"{reverse('core:customer-login')}?next=/customer/profile/")

    def test_customer_can_view_and_update_profile(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:customer-profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your profile")

        response = self.client.post(
            reverse("core:customer-profile"),
            {
                "email": "newemail@example.com",
                "first_name": "Alex",
                "last_name": "Shopper",
            },
        )
        self.assertRedirects(response, reverse("core:customer-profile"))
        user.refresh_from_db()
        self.assertEqual(user.email, "newemail@example.com")
        self.assertEqual(user.username, "newemail@example.com")
        self.assertEqual(user.first_name, "Alex")
        self.assertEqual(user.last_name, "Shopper")

    def test_profile_rejects_duplicate_email(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="testpass123",
        )
        customer = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="testpass123",
        )
        self.client.force_login(customer)

        response = self.client.post(
            reverse("core:customer-profile"),
            {
                "email": "other@example.com",
                "first_name": "Alex",
                "last_name": "Shopper",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        customer.refresh_from_db()
        self.assertEqual(customer.email, "customer@example.com")

    def test_producer_redirected_from_customer_profile(self):
        user_model = get_user_model()
        producer_user = user_model.objects.create_user(
            username="producer@example.com",
            email="producer@example.com",
            password="testpass123",
        )
        Producer.objects.create(user=producer_user, business_name="Farm Co", postcode="BS1 1AA")
        self.client.force_login(producer_user)

        response = self.client.get(reverse("core:customer-profile"))
        self.assertRedirects(response, reverse("core:dashboard"))

    def test_customer_password_change_requires_login(self):
        response = self.client.get(reverse("core:customer-password-change"))
        self.assertRedirects(
            response,
            f"{reverse('core:customer-login')}?next=/customer/profile/password/",
        )

    def test_customer_can_change_password(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="oldpass123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("core:customer-password-change"),
            {
                "old_password": "oldpass123",
                "new_password1": "new-strong-pass-456",
                "new_password2": "new-strong-pass-456",
            },
        )
        self.assertRedirects(response, reverse("core:customer-profile"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("new-strong-pass-456"))

    def test_producer_redirected_from_customer_password_change(self):
        user_model = get_user_model()
        producer_user = user_model.objects.create_user(
            username="producer@example.com",
            email="producer@example.com",
            password="testpass123",
        )
        Producer.objects.create(user=producer_user, business_name="Farm Co", postcode="BS1 1AA")
        self.client.force_login(producer_user)

        response = self.client.get(reverse("core:customer-password-change"))
        self.assertRedirects(response, reverse("core:dashboard"))


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


class CustomerProductSearchTests(ProducerFeatureBase):
    """TC-005: name, description, producer business name; icontains (case-insensitive)."""

    def setUp(self):
        super().setUp()
        self.category_only_match_product = Product.objects.create(
            producer=self.producer,
            name="Plain Loaf",
            description="Simple daily bread",
            price=Decimal("2.00"),
            category=self.category,
            stock_quantity=5,
            minimum_order_quantity=1,
            lead_time_hours=48,
            organic=False,
            is_active=True,
        )

    def test_tc005_search_matches_name_description_producer_case_insensitive(self):
        url = reverse("core:customer-product-list")
        self.assertContains(self.client.get(url, {"q": "carrots"}), "Carrots")
        self.assertContains(self.client.get(url, {"q": "CARROTS"}), "Carrots")
        self.assertContains(self.client.get(url, {"q": "fresh"}), "Carrots")
        self.assertContains(self.client.get(url, {"q": "organic"}), "Milk")
        self.assertContains(self.client.get(url, {"q": "PRODUCER ONE"}), "Carrots")
        self.assertContains(self.client.get(url, {"q": "producer one"}), "Plain Loaf")

    def test_tc005_search_does_not_match_category_name(self):
        url = reverse("core:customer-product-list")
        response = self.client.get(url, {"q": "vegetables"})
        self.assertNotContains(response, "Plain Loaf")
        self.assertNotContains(response, "Carrots")

    def test_search_strips_whitespace_from_query(self):
        url = reverse("core:customer-product-list")
        response = self.client.get(url, {"q": "  carrots  "})
        self.assertContains(response, "<strong>Carrots</strong>")

    def test_search_excludes_inactive_products(self):
        Product.objects.create(
            producer=self.producer,
            name="Baby Carrots",
            description="Young roots",
            price=Decimal("2.20"),
            category=self.category,
            stock_quantity=8,
            minimum_order_quantity=1,
            lead_time_hours=48,
            organic=False,
            is_active=True,
        )
        self.product.is_active = False
        self.product.save()
        url = reverse("core:customer-product-list")
        response = self.client.get(url, {"q": "carrots"})
        self.assertContains(response, "<strong>Baby Carrots</strong>")
        self.assertNotContains(response, "<strong>Carrots</strong>")


class CustomerProductFilterDisplayTests(ProducerFeatureBase):
    def test_tc014_organic_filter(self):
        url = reverse("core:customer-product-list")
        self.assertContains(self.client.get(url), "Carrots")
        self.assertContains(self.client.get(url), "Milk")

        organic_only = self.client.get(url, {"organic": "1"})
        self.assertContains(organic_only, "<strong>Carrots</strong>")
        self.assertNotContains(organic_only, "<strong>Milk</strong>")

    def test_tc015_allergen_display_on_browse(self):
        self.product.allergen_info = "Contains nuts and celery."
        self.product.save()
        response = self.client.get(reverse("core:customer-product-list"))
        self.assertContains(response, "Contains nuts and celery.")
        self.assertContains(response, "Allergen notice")

    def test_allergen_exclusion_filter_excludes_matching_products(self):
        self.product.allergen_info = "Contains nuts and celery."
        self.product.save()
        self.other_product.allergen_info = "Packed in a nut-free facility."
        self.other_product.save()
        url = reverse("core:customer-product-list")
        response = self.client.get(url, {"exclude_allergen": ["nuts", "celery"]})
        self.assertNotContains(response, "<strong>Carrots</strong>")
        self.assertContains(response, "<strong>Milk</strong>")

    def test_tc015_blank_allergen_shows_none_stated(self):
        self.product.allergen_info = ""
        self.product.save()
        self.other_product.allergen_info = ""
        self.other_product.save()
        response = self.client.get(reverse("core:customer-product-list"))
        self.assertContains(response, "None stated", count=2)

    def test_active_surplus_listing_shows_discount_indicator_on_browse(self):
        SurplusListing.objects.create(
            producer=self.producer,
            product=self.product,
            quantity=3,
            original_price=Decimal("1.99"),
            discount_percent=25,
            discounted_price=Decimal("1.49"),
            available_until=timezone.now() + timedelta(days=1),
            is_active=True,
        )

        response = self.client.get(reverse("core:customer-product-list"))

        self.assertContains(response, "Surplus deal -25%")
        self.assertContains(response, "£1.49")

    def test_browse_empty_state_when_search_matches_nothing(self):
        url = reverse("core:customer-product-list")
        response = self.client.get(url, {"q": "nonexistentproductxyz123"})
        self.assertContains(response, "No products match your search or filters")
        self.assertNotContains(response, "No products currently listed in this category.")

    def test_browse_empty_state_when_no_active_products_in_catalog(self):
        Product.objects.all().update(is_active=False)
        url = reverse("core:customer-product-list")
        response = self.client.get(url)
        self.assertContains(response, "No products are available to browse right now.")
        self.assertNotContains(response, "No products currently listed in this category.")


class CustomerProductCombinedFilterTests(ProducerFeatureBase):
    """Customer browse: search, category, organic, and allergen exclusion stack (AND)."""

    def test_combined_search_and_organic(self):
        url = reverse("core:customer-product-list")
        match = self.client.get(url, {"q": "carrots", "organic": "1"})
        self.assertContains(match, "<strong>Carrots</strong>")
        empty = self.client.get(url, {"q": "milk", "organic": "1"})
        self.assertContains(empty, "No products match your search or filters")
        self.assertNotContains(empty, "<strong>Milk</strong>")

    def test_combined_search_and_category(self):
        url = reverse("core:customer-product-list")
        match = self.client.get(url, {"q": "milk", "category": "dairy"})
        self.assertContains(match, "<strong>Milk</strong>")
        empty = self.client.get(url, {"q": "carrots", "category": "dairy"})
        self.assertContains(empty, "No products match your search or filters")
        self.assertNotContains(empty, "<strong>Carrots</strong>")

    def test_combined_organic_and_allergen_exclusion(self):
        self.product.allergen_info = ""
        self.product.save()
        self.other_product.allergen_info = "May contain nuts."
        self.other_product.save()
        url = reverse("core:customer-product-list")
        response = self.client.get(url, {"organic": "1", "exclude_allergen": ["nuts"]})
        self.assertContains(response, "<strong>Carrots</strong>")
        self.assertNotContains(response, "<strong>Milk</strong>")

    def test_combined_search_category_and_organic(self):
        url = reverse("core:customer-product-list")
        match = self.client.get(
            url,
            {"q": "fresh", "category": "vegetables", "organic": "1"},
        )
        self.assertContains(match, "<strong>Carrots</strong>")
        empty = self.client.get(
            url,
            {"q": "fresh", "category": "dairy", "organic": "1"},
        )
        self.assertContains(empty, "No products match your search or filters")

    def test_combined_search_and_allergen_exclusion(self):
        self.product.allergen_info = "Contains walnuts."
        self.product.save()
        url = reverse("core:customer-product-list")
        excluded = self.client.get(url, {"q": "carrots", "exclude_allergen": ["nuts"]})
        self.assertContains(excluded, "No products match your search or filters")
        self.assertNotContains(excluded, "<strong>Carrots</strong>")
        still_shown = self.client.get(url, {"q": "milk", "exclude_allergen": ["nuts"]})
        self.assertContains(still_shown, "<strong>Milk</strong>")


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

    def test_order_list_is_paginated(self):
        for index in range(11):
            order = Order.objects.create(
                customer=self.customer_user,
                paid=True,
                customer_name="Local Buyer",
                customer_email="buyer@example.com",
                delivery_method=Order.DELIVERY_DELIVERY,
                delivery_postcode="BS32 4AQ",
                fulfilment_date=timezone.localdate() + timedelta(days=3),
            )
            OrderItem.objects.create(
                order=order,
                product=self.product,
                quantity=1,
                price=Decimal("1.99"),
                status=OrderItem.STATUS_PENDING,
            )

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:order-list"))

        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["orders"]), 10)
        self.assertContains(response, "Page 1 of 2")
        self.assertContains(response, "Next")

        page_two = self.client.get(reverse("core:order-list"), {"page": "2"})
        self.assertEqual(len(page_two.context["orders"]), 2)

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

    def test_customer_orders_reflect_line_item_status(self):
        self.order.status = Order.STATUS_CONFIRMED
        self.order.save()
        self.own_item.status = OrderItem.STATUS_PREPARING
        self.own_item.save()

        self.client.force_login(self.customer_user)
        response = self.client.get(reverse("core:customer-orders"))
        self.assertContains(response, "Preparing")

    def test_order_detail_shows_food_miles(self):
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:order-detail", kwargs={"pk": self.order.pk}))

        self.assertContains(response, "miles")
        self.assertEqual(calculate_food_miles("BS1 1AA", "BS32 4AQ"), Decimal("6.3"))


class ProducerFlowIntegrationTests(ProducerFeatureBase):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            customer=self.customer_user,
            paid=True,
            status=Order.STATUS_CONFIRMED,
            customer_name="Local Buyer",
            customer_email="buyer@example.com",
            delivery_method=Order.DELIVERY_DELIVERY,
            delivery_postcode="BS32 4AQ",
            fulfilment_date=timezone.localdate() + timedelta(days=2),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal("1.99"),
            status=OrderItem.STATUS_PENDING,
        )

    def test_producer_can_review_and_update_their_order_item(self):
        self.client.force_login(self.producer_user)

        list_response = self.client.get(reverse("core:order-list"))
        self.assertContains(list_response, self.order.reference)
        self.assertContains(list_response, "Carrots")

        detail_response = self.client.get(reverse("core:order-detail", kwargs={"pk": self.order.pk}))
        self.assertContains(detail_response, "Carrots")
        self.assertContains(detail_response, "Pending")

        update_response = self.client.post(
            reverse("core:order-item-update", kwargs={"pk": self.item.pk}),
            {
                "status": OrderItem.STATUS_PREPARING,
                "producer_notes": "Packing this for collection.",
            },
        )
        self.assertRedirects(update_response, reverse("core:order-detail", kwargs={"pk": self.order.pk}))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, OrderItem.STATUS_PREPARING)
        self.assertEqual(self.item.producer_notes, "Packing this for collection.")


class CustomerFlowIntegrationTests(ProducerFeatureBase):
    def test_customer_can_buy_product_and_see_order_progress(self):
        self.client.force_login(self.customer_user)

        browse_response = self.client.get(reverse("core:customer-product-list"))
        self.assertContains(browse_response, "Carrots")

        self.client.post(reverse("core:cart-add", kwargs={"product_id": self.product.pk}), {"quantity": "2"})
        checkout_response = self.client.post(
            reverse("core:checkout"),
            {
                "postcode": "BS32 4AQ",
                "address": "1 Market Street",
                "collection_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
            },
        )

        order = Order.objects.get(customer=self.customer_user, delivery_address="1 Market Street")
        self.assertRedirects(checkout_response, reverse("core:payment", kwargs={"order_id": order.pk}))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.payment.total_amount, Decimal("3.98"))

        success_response = self.client.get(reverse("core:payment-success", kwargs={"order_id": order.pk}))
        self.assertEqual(success_response.status_code, 200)
        order.refresh_from_db()
        self.assertTrue(order.paid)
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)
        self.assertEqual(order.payment.status, Payment.STATUS_COMPLETED)
        self.assertEqual(TraceabilityRecord.objects.filter(order_item__order=order).count(), 1)

        orders_response = self.client.get(reverse("core:customer-orders"))
        self.assertContains(orders_response, order.reference)
        self.assertContains(orders_response, "Pending")


class SeedDemoDataCommandTests(TestCase):
    def test_seed_demo_data_creates_demo_records(self):
        out = StringIO()

        call_command("seed_demo_data", stdout=out)

        self.assertIn("Demo data created successfully", out.getvalue())
        self.assertEqual(Producer.objects.count(), 3)
        self.assertEqual(Product.objects.count(), 10)
        self.assertEqual(Order.objects.count(), 5)
        self.assertEqual(Payment.objects.count(), 5)
        self.assertTrue(Product.objects.filter(name="Free Range Eggs (6 pack)", stock_quantity=5).exists())
        self.assertTrue(Product.objects.filter(name="Seeded Breakfast Rolls", is_active=False).exists())
        self.assertTrue(SurplusListing.objects.filter(product__name="Organic Tomatoes", is_active=True).exists())
        self.assertEqual(ProducerContent.objects.count(), 2)
        self.assertTrue(Order.objects.filter(reference="ORD-00004", paid=False, payment__status=Payment.STATUS_PENDING).exists())
        self.assertTrue(Order.objects.filter(reference="ORD-00005", items__status=OrderItem.STATUS_READY).exists())
        paid_item_count = OrderItem.objects.filter(order__paid=True).count()
        self.assertEqual(TraceabilityRecord.objects.count(), paid_item_count)
        self.assertGreater(ProducerSettlement.objects.count(), 0)


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
        self.assertContains(response, "£10.00")
        self.assertContains(response, "£0.50")
        self.assertContains(response, "£9.50")

    def test_producer_can_export_settlement_csv(self):
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
        self.client.get(reverse("core:settlement-list"))
        settlement = ProducerSettlement.objects.get(producer=self.producer)

        response = self.client.get(reverse("core:settlement-export", kwargs={"pk": settlement.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment;", response["Content-Disposition"])
        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertEqual(rows[0][0], "Settlement Week Start")
        self.assertEqual(rows[1][3], order.reference)
        self.assertEqual(rows[1][5], "Carrots")
        self.assertEqual(rows[1][6], "4")
        self.assertEqual(rows[1][8], "10.00")
        self.assertEqual(rows[1][9], "0.50")
        self.assertEqual(rows[1][10], "9.50")

    def test_producer_cannot_export_another_producers_settlement_csv(self):
        settlement = ProducerSettlement.objects.create(
            producer=self.other_producer,
            week_start=timezone.localdate(),
            week_end=timezone.localdate(),
        )

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:settlement-export", kwargs={"pk": settlement.pk}))

        self.assertEqual(response.status_code, 404)


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
