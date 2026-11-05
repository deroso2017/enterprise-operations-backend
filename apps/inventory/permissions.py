from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsManagerOrAdminOrReadOnly(BasePermission):
    message = "Only managers and administrators can modify inventory."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True

        return bool(
            request.user.is_superuser
            or request.user.role
            in (
                User.Role.ADMIN,
                User.Role.MANAGER,
            )
        )
