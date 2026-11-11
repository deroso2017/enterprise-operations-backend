from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inventory.models import Category, Product, StockLevel, Warehouse
from apps.orders.models import Customer, Order, OrderItem
from apps.orders.services import (
    cancel_order,
    confirm_order,
    create_order,
    ship_order,
)


class OrderWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = User.objects.create_user(
            email="employee@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYEE,
        )

        cls.manager = User.objects.create_user(
            email="manager@example.com",
            password="TestPassword123!",
            role=User.Role.MANAGER,
        )

        cls.other_employee = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYEE,
        )

        cls.category = Category.objects.create(
            name="Electronics",
            description="Electronic products",
        )

        cls.warehouse = Warehouse.objects.create(
            code="WH-TEST",
            name="Test Warehouse",
            location="Cologne",
            is_active=True,
        )

        cls.product = Product.objects.create(
            sku="LAP-TEST",
            name="Test Laptop",
            description="Test product",
            category=cls.category,
            unit_price=Decimal("1000.00"),
            reorder_level=5,
            is_active=True,
        )

        cls.stock = StockLevel.objects.create(
            product=cls.product,
            warehouse=cls.warehouse,
            quantity=20,
            reserved_quantity=0,
        )

        cls.customer = Customer.objects.create(
            name="Test Customer GmbH",
            email="customer@example.com",
            country="Germany",
        )

    def create_test_order(self, quantity=5):
        return create_order(
            customer_id=self.customer.id,
            items=[
                {
                    "product_id": self.product.id,
                    "quantity": quantity,
                },
            ],
            user=self.employee,
            tax_rate=Decimal("19.00"),
        )

    def submit_test_order(self, quantity=5):
        from apps.orders.services import submit_order

        order = self.create_test_order(quantity)
        return submit_order(
            order_id=order.id,
            user=self.employee,
        )

    def test_order_total_is_calculated(self):
        order = self.create_test_order(quantity=2)

        self.assertEqual(order.subtotal, Decimal("2000.00"))
        self.assertEqual(order.tax_amount, Decimal("380.00"))
        self.assertEqual(order.total, Decimal("2380.00"))

    def test_order_starts_as_draft(self):
        order = self.create_test_order()

        self.assertEqual(order.status, Order.Status.DRAFT)

    def test_confirmation_reserves_stock(self):
        order = self.submit_test_order(quantity=5)

        confirmed = confirm_order(
            order_id=order.id,
            warehouse_id=self.warehouse.id,
            user=self.manager,
        )

        self.stock.refresh_from_db()

        self.assertEqual(confirmed.status, Order.Status.CONFIRMED)
        self.assertEqual(self.stock.quantity, 20)
        self.assertEqual(self.stock.reserved_quantity, 5)
        self.assertEqual(self.stock.available_quantity, 15)

    def test_confirmation_rejects_insufficient_stock(self):
        order = self.submit_test_order(quantity=25)

        with self.assertRaises(ValidationError):
            confirm_order(
                order_id=order.id,
                warehouse_id=self.warehouse.id,
                user=self.manager,
            )

        self.stock.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_dispatch_deducts_physical_and_reserved_stock(self):
        order = self.submit_test_order(quantity=5)

        confirm_order(
            order_id=order.id,
            warehouse_id=self.warehouse.id,
            user=self.manager,
        )

        shipped = ship_order(
            order_id=order.id,
            user=self.manager,
        )

        self.stock.refresh_from_db()

        self.assertEqual(shipped.status, Order.Status.SHIPPED)
        self.assertEqual(self.stock.quantity, 15)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.stock.available_quantity, 15)

    def test_cancellation_releases_reservation(self):
        order = self.submit_test_order(quantity=5)

        confirm_order(
            order_id=order.id,
            warehouse_id=self.warehouse.id,
            user=self.manager,
        )

        cancelled = cancel_order(
            order_id=order.id,
            user=self.manager,
            reason="Customer cancellation",
        )

        self.stock.refresh_from_db()

        self.assertEqual(cancelled.status, Order.Status.CANCELLED)
        self.assertEqual(self.stock.quantity, 20)
        self.assertEqual(self.stock.reserved_quantity, 0)

    def test_shipped_order_cannot_be_cancelled(self):
        order = self.submit_test_order(quantity=5)

        confirm_order(
            order_id=order.id,
            warehouse_id=self.warehouse.id,
            user=self.manager,
        )

        ship_order(
            order_id=order.id,
            user=self.manager,
        )

        with self.assertRaises(ValidationError):
            cancel_order(
                order_id=order.id,
                user=self.manager,
                reason="Too late",
            )

    def test_employee_cannot_access_another_users_order(self):
        order = self.create_test_order()

        client = APIClient()
        client.force_authenticate(user=self.other_employee)

        response = client.get(f"/api/orders/{order.id}/")

        self.assertEqual(response.status_code, 404)

    def test_employee_cannot_confirm_order(self):
        order = self.submit_test_order()

        client = APIClient()
        client.force_authenticate(user=self.employee)

        response = client.post(
            f"/api/orders/{order.id}/confirm/",
            {"warehouse_id": self.warehouse.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
