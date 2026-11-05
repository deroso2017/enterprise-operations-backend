from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class RegistrationTests(APITestCase):
    def test_registration_creates_employee(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "employee@example.com",
                "first_name": "Alex",
                "last_name": "Smith",
                "password": "A-Strong-Password-934!",
                "password_confirm": "A-Strong-Password-934!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="employee@example.com")
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertTrue(user.check_password("A-Strong-Password-934!"))

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "employee@example.com",
                "password": "A-Strong-Password-934!",
                "password_confirm": "Different-Password-934!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="employee@example.com").exists())

    def test_registration_cannot_choose_admin_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "attacker@example.com",
                "password": "A-Strong-Password-934!",
                "password_confirm": "A-Strong-Password-934!",
                "role": "ADMIN",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="attacker@example.com")
        self.assertEqual(user.role, User.Role.EMPLOYEE)


class AuthenticationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            password="A-Strong-Password-934!",
        )

    def test_login_returns_tokens_and_user(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": "employee@example.com",
                "password": "A-Strong-Password-934!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "EMPLOYEE")

    def test_current_user_requires_authentication(self):
        response = self.client.get(reverse("current-user"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_current_user_returns_authenticated_profile(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = self.client.get(reverse("current-user"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_logout_blacklists_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(
            reverse("logout"),
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        refresh_response = self.client.post(
            reverse("token_refresh"),
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_employee_cannot_access_admin_endpoint(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = self.client.get(reverse("admin-check"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_access_management_endpoint(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = self.client.get(reverse("management-check"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_admin_endpoint(self):
        admin = User.objects.create_user(
            email="admin@example.com",
            password="A-Strong-Password-934!",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        refresh = RefreshToken.for_user(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = self.client.get(reverse("admin-check"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
