from rest_framework import serializers

from .models import (
    Category,
    Product,
    StockLevel,
    StockMovement,
    Warehouse,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "id",
            "code",
            "name",
            "location",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "description",
            "category",
            "category_name",
            "unit_price",
            "reorder_level",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class StockLevelSerializer(serializers.ModelSerializer):
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
    )
    reorder_level = serializers.IntegerField(
        source="product.reorder_level",
        read_only=True,
    )
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = StockLevel
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "warehouse",
            "warehouse_name",
            "quantity",
            "reorder_level",
            "is_low_stock",
        )
        read_only_fields = fields

    def get_is_low_stock(self, obj) -> bool:
        return obj.quantity <= obj.product.reorder_level


class StockMovementSerializer(serializers.ModelSerializer):
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
    )
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
    )

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "warehouse",
            "warehouse_name",
            "movement_type",
            "quantity",
            "quantity_before",
            "quantity_after",
            "reference",
            "notes",
            "created_by",
            "created_by_email",
            "created_at",
        )
        read_only_fields = fields


class StockAdjustmentSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
    )

    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(is_active=True),
    )

    direction = serializers.ChoiceField(
        choices=("IN", "OUT"),
    )

    quantity = serializers.IntegerField(min_value=1)
    reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(
        max_length=2000,
    )


class StockTransferSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
    )

    source_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(is_active=True),
    )

    destination_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(is_active=True),
    )

    quantity = serializers.IntegerField(min_value=1)
    reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(
        max_length=2000,
    )

    def validate(self, attrs):
        if attrs["source_warehouse"] == attrs["destination_warehouse"]:
            raise serializers.ValidationError(
                "Source and destination warehouses must be different."
            )
        return attrs
