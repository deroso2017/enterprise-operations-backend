from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import OrderFilter
from .models import Customer, Order, OrderItem
from .permissions import (
    CanAccessOrder,
    CanManageCustomer,
    is_manager_or_admin,
)
from .serializers import (
    CancelOrderSerializer,
    ConfirmOrderSerializer,
    CustomerSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)
from . import services


def handle_business_error(error):
    raise ValidationError({"detail": str(error)})


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, CanManageCustomer]
    search_fields = ["name", "email", "company"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return Customer.objects.filter(is_active=True)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, CanAccessOrder]
    filterset_class = OrderFilter
    search_fields = ["order_number", "customer__name"]
    ordering_fields = ["created_at", "total", "order_date"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Order.objects.select_related(
            "customer", "created_by", "updated_by"
        ).prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related(
                    "product",
                    "warehouse",
                ),
            )
        )

        if not is_manager_or_admin(self.request.user):
            queryset = queryset.filter(
                created_by=self.request.user,
            )

        return queryset

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def _run_action(self, function, **kwargs):
        try:
            order = function(**kwargs)
        except DjangoValidationError as error:
            handle_business_error(error)

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_200_OK,
        )

    def create(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = services.create_order(
                customer_id=serializer.validated_data["customer_id"],
                items=serializer.validated_data["items"],
                user=request.user,
                notes=serializer.validated_data.get("notes", ""),
                required_date=serializer.validated_data.get("required_date"),
                tax_rate=serializer.validated_data["tax_rate"],
            )
        except DjangoValidationError as error:
            handle_business_error(error)

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        order = self.get_object()

        if order.status != Order.Status.DRAFT:
            raise ValidationError("Only draft orders can be edited.")

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = services.update_draft_order(
                order_id=order.id,
                customer_id=serializer.validated_data["customer_id"],
                items=serializer.validated_data["items"],
                user=request.user,
                notes=serializer.validated_data.get("notes", ""),
                required_date=serializer.validated_data.get("required_date"),
                tax_rate=serializer.validated_data["tax_rate"],
            )
        except DjangoValidationError as error:
            handle_business_error(error)

        return Response(OrderSerializer(order).data)

    def destroy(self, request, *args, **kwargs):
        raise ValidationError("Orders cannot be deleted. Use the cancel action.")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        order = self.get_object()
        return self._run_action(
            services.submit_order,
            order_id=order.id,
            user=request.user,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        if not is_manager_or_admin(request.user):
            raise PermissionDenied("Manager or administrator access is required.")

        order = self.get_object()
        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return self._run_action(
            services.confirm_order,
            order_id=order.id,
            warehouse_id=serializer.validated_data["warehouse_id"],
            user=request.user,
        )

    @action(detail=True, methods=["post"])
    def processing(self, request, pk=None):
        if not is_manager_or_admin(request.user):
            raise PermissionDenied("Manager or administrator access is required.")

        order = self.get_object()

        return self._run_action(
            services.start_processing,
            order_id=order.id,
            user=request.user,
        )

    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        if not is_manager_or_admin(request.user):
            raise PermissionDenied("Manager or administrator access is required.")

        order = self.get_object()

        return self._run_action(
            services.ship_order,
            order_id=order.id,
            user=request.user,
        )

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        if not is_manager_or_admin(request.user):
            raise PermissionDenied("Manager or administrator access is required.")

        order = self.get_object()

        return self._run_action(
            services.deliver_order,
            order_id=order.id,
            user=request.user,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if not is_manager_or_admin(request.user) and order.status not in (
            Order.Status.DRAFT,
            Order.Status.PENDING,
        ):
            raise PermissionDenied("You cannot cancel this order.")

        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return self._run_action(
            services.cancel_order,
            order_id=order.id,
            user=request.user,
            reason=serializer.validated_data["reason"],
        )
