from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Warehouse(TimeStampedModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Product(TimeStampedModel):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    reorder_level = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


class StockLevel(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_levels",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_levels",
    )

    quantity = models.PositiveIntegerField(default=0)

    reserved_quantity = models.PositiveIntegerField(default=0)

    @property
    def available_quantity(self) -> int:
        return self.quantity - self.reserved_quantity

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "warehouse"],
                name="unique_product_warehouse_stock",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="stock_quantity_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__lte=models.F("quantity")),
                name="stock_reserved_lte_quantity",
            ),
        ]
        indexes = [
            models.Index(fields=["warehouse", "product"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.sku} @ {self.warehouse.code}: {self.quantity}"


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RECEIPT = "RECEIPT", "Receipt"
        ISSUE = "ISSUE", "Issue"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        TRANSFER_IN = "TRANSFER_IN", "Transfer In"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    quantity_before = models.PositiveIntegerField()
    quantity_after = models.PositiveIntegerField()

    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["warehouse", "-created_at"]),
            models.Index(fields=["movement_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.movement_type}: " f"{self.product.sku} ({self.quantity})"
