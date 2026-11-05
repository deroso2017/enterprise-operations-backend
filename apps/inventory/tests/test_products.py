from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import Category, Product


class ProductAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="manager@example.com",
            password="StrongPassword123!",
            role=User.Role.MANAGER,
        )

        self.category = Category.objects.create(
            name="Electronics",
        )

        self.client.force_authenticate(user=self.user)

    def test_create_product(self):
        response = self.client.post(
            reverse("product-list"),
            {
                "sku": "LAP-001",
                "name": "Business Laptop",
                "description": "Laptop for employees",
                "category": self.category.id,
                "unit_price": "899.00",
                "reorder_level": 5,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.first().sku, "LAP-001")

    def test_duplicate_sku_is_rejected(self):
        Product.objects.create(
            sku="LAP-001",
            name="Laptop",
            category=self.category,
            unit_price="899.00",
        )

        response = self.client.post(
            reverse("product-list"),
            {
                "sku": "LAP-001",
                "name": "Another Laptop",
                "category": self.category.id,
                "unit_price": "999.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_list_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("product-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
