from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_manager_or_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role in ("ADMIN", "MANAGER"))
    )


class IsManagerOrAdmin(BasePermission):
    message = "Manager or administrator access is required."

    def has_permission(self, request, view):
        return is_manager_or_admin(request.user)


class CanAccessOrder(BasePermission):
    def has_object_permission(self, request, view, obj):
        if is_manager_or_admin(request.user):
            return True

        return obj.created_by_id == request.user.id


class CanManageCustomer(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        return is_manager_or_admin(request.user)
