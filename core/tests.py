from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Product


class ProductCrudTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.producer = user_model.objects.create_user(username="producer", password="testpass123")
        self.other_user = user_model.objects.create_user(username="other", password="testpass123")

    def test_product_list_only_shows_owner_products(self):
        Product.objects.create(
            owner=self.producer,
            name="Own Product",
            description="Owned by logged in user",
            price="2.50",
            category=Product.CATEGORY_BAKERY,
        )
        Product.objects.create(
            owner=self.other_user,
            name="Other Product",
            description="Owned by another user",
            price="3.25",
            category=Product.CATEGORY_DAIRY,
        )

        self.client.force_login(self.producer)
        response = self.client.get(reverse("core:product-list"))

        self.assertContains(response, "Own Product")
        self.assertNotContains(response, "Other Product")

    def test_create_product_assigns_owner(self):
        self.client.force_login(self.producer)

        response = self.client.post(
            reverse("core:product-create"),
            {
                "name": "Carrots",
                "description": "Fresh carrots",
                "price": "1.99",
                "category": Product.CATEGORY_VEGETABLES,
                "available_from": "2026-02-01",
                "available_to": "2026-02-28",
                "is_active": True,
            },
        )

        self.assertRedirects(response, reverse("core:product-list"))
        product = Product.objects.get(name="Carrots")
        self.assertEqual(product.owner, self.producer)

    def test_cannot_edit_other_users_product(self):
        product = Product.objects.create(
            owner=self.other_user,
            name="Milk",
            description="Organic milk",
            price="2.10",
            category=Product.CATEGORY_DAIRY,
        )

        self.client.force_login(self.producer)
        response = self.client.post(
            reverse("core:product-update", kwargs={"pk": product.pk}),
            {
                "name": "Updated Milk",
                "description": "Should not update",
                "price": "2.50",
                "category": Product.CATEGORY_DAIRY,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 404)
        product.refresh_from_db()
        self.assertEqual(product.name, "Milk")

    def test_date_validation_on_form(self):
        self.client.force_login(self.producer)
        response = self.client.post(
            reverse("core:product-create"),
            {
                "name": "Tomatoes",
                "description": "Seasonal",
                "price": "1.20",
                "category": Product.CATEGORY_VEGETABLES,
                "available_from": "2026-03-10",
                "available_to": "2026-03-01",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Available to date cannot be before available from date.")
        self.assertFalse(Product.objects.filter(name="Tomatoes").exists())
