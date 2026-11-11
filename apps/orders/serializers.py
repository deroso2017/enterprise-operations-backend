from rest_framework import serializers

from .models import Customer, Order, OrderItem


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "company",
            "address",
            "city",
            "postal_code",
            "country",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )
    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )
    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
        default=None,
    )

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "warehouse",
            "warehouse_name",
            "quantity",
            "unit_price",
            "line_total",
        )
        read_only_fields = (
            "id",
            "product_name",
            "product_sku",
            "warehouse",
            "warehouse_name",
            "unit_price",
            "line_total",
        )


class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
    )
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "customer",
            "customer_name",
            "status",
            "order_date",
            "required_date",
            "shipped_at",
            "delivered_at",
            "subtotal",
            "tax_rate",
            "tax_amount",
            "total",
            "notes",
            "cancellation_reason",
            "created_by",
            "created_by_email",
            "updated_by",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True)
    required_date = serializers.DateField(required=False, allow_null=True)
    tax_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        default="0.00",
    )
    items = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate_items(self, items):
        normalized = []
        seen = set()

        for item in items:
            if set(item.keys()) != {"product_id", "quantity"}:
                raise serializers.ValidationError(
                    "Each item must contain product_id and quantity only."
                )

            try:
                product_id = int(item["product_id"])
                quantity = int(item["quantity"])
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Product IDs and quantities must be integers."
                )

            if product_id < 1 or quantity < 1:
                raise serializers.ValidationError(
                    "Product IDs and quantities must be positive."
                )

            if product_id in seen:
                raise serializers.ValidationError(
                    "A product may only appear once in an order."
                )

            seen.add(product_id)
            normalized.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )

        return normalized


class SubmitOrderSerializer(serializers.Serializer):
    pass


class ConfirmOrderSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField(min_value=1)


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=2000,
    )


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
