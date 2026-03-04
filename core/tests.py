from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Producer, Product


class ProducerAuthTests(TestCase):
    def test_producer_register_creates_user_and_profile(self):
        response = self.client.post(
            reverse("core:producer-register"),
            {
                "business_name": "Farm Co",
                "postcode": "BS1 1AA",
                "organic": True,
                "email": "producer@example.com",
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )

        self.assertRedirects(response, reverse("core:product-list"))
        user_model = get_user_model()
        user = user_model.objects.get(email="producer@example.com")
        producer = Producer.objects.get(user=user)
        self.assertEqual(producer.business_name, "Farm Co")
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

        self.assertRedirects(response, reverse("core:product-list"))
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


class ProductCrudTests(TestCase):
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
        self.producer = Producer.objects.create(
            user=self.producer_user,
            business_name="Producer One",
            postcode="BS1 1AA",
        )
        self.other_producer = Producer.objects.create(
            user=self.other_user,
            business_name="Producer Two",
            postcode="BS2 2BB",
        )
        self.category = Category.objects.create(name="Vegetables")
        self.other_category = Category.objects.create(name="Dairy")

    def test_product_list_only_shows_owner_products(self):
        Product.objects.create(
            producer=self.producer,
            name="Own Product",
            description="Owned by logged in user",
            price="2.50",
            category=self.category,
        )
        Product.objects.create(
            producer=self.other_producer,
            name="Other Product",
            description="Owned by another user",
            price="3.25",
            category=self.other_category,
        )

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse("core:product-list"))

        self.assertContains(response, "Own Product")
        self.assertNotContains(response, "Other Product")

    def test_create_product_assigns_producer(self):
        self.client.force_login(self.producer_user)

        response = self.client.post(
            reverse("core:product-create"),
            {
                "name": "Carrots",
                "description": "Fresh carrots",
                "price": "1.99",
                "category": self.category.pk,
                "available_from": "2026-02-01",
                "available_to": "2026-02-28",
                "is_active": True,
            },
        )

        self.assertRedirects(response, reverse("core:product-list"))
        product = Product.objects.get(name="Carrots")
        self.assertEqual(product.producer, self.producer)

    def test_cannot_edit_other_users_product(self):
        product = Product.objects.create(
            producer=self.other_producer,
            name="Milk",
            description="Organic milk",
            price="2.10",
            category=self.other_category,
        )

        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:product-update", kwargs={"pk": product.pk}),
            {
                "name": "Updated Milk",
                "description": "Should not update",
                "price": "2.50",
                "category": self.other_category.pk,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 404)
        product.refresh_from_db()
        self.assertEqual(product.name, "Milk")

    def test_date_validation_on_form(self):
        self.client.force_login(self.producer_user)
        response = self.client.post(
            reverse("core:product-create"),
            {
                "name": "Tomatoes",
                "description": "Seasonal",
                "price": "1.20",
                "category": self.category.pk,
                "available_from": "2026-03-10",
                "available_to": "2026-03-01",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Available to date cannot be before available from date.")
        self.assertFalse(Product.objects.filter(name="Tomatoes").exists())
