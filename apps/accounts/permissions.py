from rest_framework.permissions import BasePermission

from .models import User


class IsAdmin(BasePermission):
    message = "Administrator access is required."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.role == User.Role.ADMIN)
        )


class IsManagerOrAdmin(BasePermission):
    message = "Manager or administrator access is required."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.role
                in (
                    User.Role.ADMIN,
                    User.Role.MANAGER,
                )
            )
        )
