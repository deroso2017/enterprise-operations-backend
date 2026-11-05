from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import (
    Category,
    Product,
    StockLevel,
    StockMovement,
    Warehouse,
)


class StockAPITests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="StrongPassword123!",
            role=User.Role.MANAGER,
        )

        self.category = Category.objects.create(name="Electronics")

        self.product = Product.objects.create(
            sku="LAP-001",
            name="Laptop",
            category=self.category,
            unit_price="899.00",
            reorder_level=5,
        )

        self.warehouse = Warehouse.objects.create(
            code="WH-001",
            name="Main Warehouse",
        )

        self.destination = Warehouse.objects.create(
            code="WH-002",
            name="Secondary Warehouse",
        )

        self.client.force_authenticate(user=self.manager)

    def test_receive_stock(self):
        response = self.client.post(
            reverse("stock-adjust"),
            {
                "product": self.product.id,
                "warehouse": self.warehouse.id,
                "direction": "IN",
                "quantity": 20,
                "notes": "Supplier delivery",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        stock = StockLevel.objects.get(
            product=self.product,
            warehouse=self.warehouse,
        )

        self.assertEqual(stock.quantity, 20)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_issue_stock(self):
        StockLevel.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=20,
        )

        response = self.client.post(
            reverse("stock-adjust"),
            {
                "product": self.product.id,
                "warehouse": self.warehouse.id,
                "direction": "OUT",
                "quantity": 5,
                "notes": "Issued to employee",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        stock = StockLevel.objects.get(
            product=self.product,
            warehouse=self.warehouse,
        )

        self.assertEqual(stock.quantity, 15)

    def test_cannot_issue_more_than_available(self):
        StockLevel.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=5,
        )

        response = self.client.post(
            reverse("stock-adjust"),
            {
                "product": self.product.id,
                "warehouse": self.warehouse.id,
                "direction": "OUT",
                "quantity": 10,
                "notes": "Invalid issue",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        stock = StockLevel.objects.get(
            product=self.product,
            warehouse=self.warehouse,
        )

        self.assertEqual(stock.quantity, 5)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_transfer_stock(self):
        StockLevel.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=20,
        )

        response = self.client.post(
            reverse("stock-transfer"),
            {
                "product": self.product.id,
                "source_warehouse": self.warehouse.id,
                "destination_warehouse": self.destination.id,
                "quantity": 5,
                "notes": "Warehouse transfer",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        source_stock = StockLevel.objects.get(
            product=self.product,
            warehouse=self.warehouse,
        )

        destination_stock = StockLevel.objects.get(
            product=self.product,
            warehouse=self.destination,
        )

        self.assertEqual(source_stock.quantity, 15)
        self.assertEqual(destination_stock.quantity, 5)
        self.assertEqual(StockMovement.objects.count(), 2)
