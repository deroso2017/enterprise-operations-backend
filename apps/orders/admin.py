from django.contrib import admin

from .models import Customer, Order, OrderItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "email",
        "city",
        "is_active",
    )
    list_filter = ("is_active", "country")
    search_fields = ("name", "company", "email")
    ordering = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "status",
        "subtotal",
        "total",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "customer__name")
    readonly_fields = (
        "order_number",
        "subtotal",
        "tax_amount",
        "total",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline]
