from django.urls import path

from .views import (
    CategoryDetailView,
    CategoryListCreateView,
    InventorySummaryView,
    ProductDetailView,
    ProductListCreateView,
    StockAdjustmentView,
    StockLevelListView,
    StockMovementListView,
    StockTransferView,
    WarehouseDetailView,
    WarehouseListCreateView,
)

urlpatterns = [
    path("summary/", InventorySummaryView.as_view(), name="inventory-summary"),
    path("categories/", CategoryListCreateView.as_view(), name="category-list"),
    path(
        "categories/<int:pk>/",
        CategoryDetailView.as_view(),
        name="category-detail",
    ),
    path("warehouses/", WarehouseListCreateView.as_view(), name="warehouse-list"),
    path(
        "warehouses/<int:pk>/",
        WarehouseDetailView.as_view(),
        name="warehouse-detail",
    ),
    path("products/", ProductListCreateView.as_view(), name="product-list"),
    path(
        "products/<int:pk>/",
        ProductDetailView.as_view(),
        name="product-detail",
    ),
    path("stock/", StockLevelListView.as_view(), name="stock-list"),
    path("stock/adjust/", StockAdjustmentView.as_view(), name="stock-adjust"),
    path("stock/transfer/", StockTransferView.as_view(), name="stock-transfer"),
    path(
        "movements/",
        StockMovementListView.as_view(),
        name="stock-movement-list",
    ),
]
