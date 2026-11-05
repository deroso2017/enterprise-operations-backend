from django.contrib import admin

from .models import (
    Category,
    Product,
    StockLevel,
    StockMovement,
    Warehouse,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "location", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "category",
        "unit_price",
        "reorder_level",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("sku", "name")


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "quantity")
    list_filter = ("warehouse",)
    search_fields = ("product__sku", "product__name")
    readonly_fields = ("product", "warehouse", "quantity")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "warehouse",
        "movement_type",
        "quantity",
        "created_by",
        "created_at",
    )
    list_filter = ("movement_type", "warehouse")
    search_fields = ("product__sku", "reference")
    readonly_fields = (
        "product",
        "warehouse",
        "movement_type",
        "quantity",
        "quantity_before",
        "quantity_after",
        "reference",
        "notes",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
