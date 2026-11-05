from django.db.models import F, Sum
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Category,
    Product,
    StockLevel,
    StockMovement,
    Warehouse,
)
from .permissions import IsManagerOrAdminOrReadOnly
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    StockAdjustmentSerializer,
    StockLevelSerializer,
    StockMovementSerializer,
    StockTransferSerializer,
    WarehouseSerializer,
)
from .services import adjust_stock, transfer_stock


class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]


class WarehouseListCreateView(generics.ListCreateAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]


class WarehouseDetailView(generics.RetrieveUpdateAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]

    def get_queryset(self):
        queryset = Product.objects.select_related("category").all()

        search = self.request.query_params.get("search")
        category = self.request.query_params.get("category")
        active = self.request.query_params.get("active")

        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(
                sku__icontains=search
            )

        if category:
            queryset = queryset.filter(category_id=category)

        if active in ("true", "false"):
            queryset = queryset.filter(is_active=(active == "true"))

        ordering = self.request.query_params.get("ordering")

        allowed_ordering = {
            "name",
            "-name",
            "sku",
            "-sku",
            "unit_price",
            "-unit_price",
            "created_at",
            "-created_at",
        }

        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)

        return queryset.distinct()


class ProductDetailView(generics.RetrieveUpdateAPIView):
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]


class StockLevelListView(generics.ListAPIView):
    serializer_class = StockLevelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StockLevel.objects.select_related(
            "product",
            "warehouse",
        ).filter(product__is_active=True, warehouse__is_active=True)

        warehouse = self.request.query_params.get("warehouse")
        product = self.request.query_params.get("product")
        low_stock = self.request.query_params.get("low_stock")

        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)

        if product:
            queryset = queryset.filter(product_id=product)

        if low_stock == "true":
            queryset = queryset.filter(quantity__lte=F("product__reorder_level"))

        return queryset.order_by("product__name", "warehouse__name")


class StockAdjustmentView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsManagerOrAdminOrReadOnly,
    ]

    def post(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        movement = adjust_stock(
            product=data["product"],
            warehouse=data["warehouse"],
            direction=data["direction"],
            quantity=data["quantity"],
            notes=data["notes"],
            reference=data.get("reference", ""),
            user=request.user,
        )

        return Response(
            StockMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )


class StockTransferView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsManagerOrAdminOrReadOnly,
    ]

    def post(self, request):
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        movements = transfer_stock(
            product=data["product"],
            source_warehouse=data["source_warehouse"],
            destination_warehouse=data["destination_warehouse"],
            quantity=data["quantity"],
            notes=data["notes"],
            reference=data.get("reference", ""),
            user=request.user,
        )

        return Response(
            {
                "source_movement": StockMovementSerializer(movements[0]).data,
                "destination_movement": StockMovementSerializer(movements[1]).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StockMovementListView(generics.ListAPIView):
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StockMovement.objects.select_related(
            "product",
            "warehouse",
            "created_by",
        ).all()

        product = self.request.query_params.get("product")
        warehouse = self.request.query_params.get("warehouse")
        movement_type = self.request.query_params.get("type")

        if product:
            queryset = queryset.filter(product_id=product)

        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)

        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        return queryset


class InventorySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_products = Product.objects.filter(is_active=True).count()
        active_warehouses = Warehouse.objects.filter(is_active=True).count()

        stock_rows = StockLevel.objects.filter(
            product__is_active=True,
            warehouse__is_active=True,
        )

        total_units = stock_rows.aggregate(total=Sum("quantity"))["total"] or 0

        low_stock_count = stock_rows.filter(
            quantity__lte=F("product__reorder_level")
        ).count()

        return Response(
            {
                "total_products": active_products,
                "total_warehouses": active_warehouses,
                "total_units": total_units,
                "low_stock_items": low_stock_count,
            }
        )
