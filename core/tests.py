from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("health-check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(
            response.json()["service"],
            "enterprise-operations-api",
        )
        self.assertEqual(response.json()["database"], "ok")

    def test_health_endpoint_only_accepts_get(self):
        response = self.client.post(reverse("health-check"))

        self.assertEqual(response.status_code, 405)
