from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.inventory.models import Category


class InventoryPermissionTests(APITestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            email="employee@example.com",
            password="StrongPassword123!",
            role=User.Role.EMPLOYEE,
        )

        self.category = Category.objects.create(name="Electronics")

    def test_employee_can_list_categories(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.get(reverse("category-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_employee_cannot_create_category(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.post(
            reverse("category-list"),
            {"name": "Furniture"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
