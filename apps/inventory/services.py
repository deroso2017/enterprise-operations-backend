from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.db.models import F

from .models import (
    Product,
    StockLevel,
    StockMovement,
    Warehouse,
)


@transaction.atomic
def adjust_stock(
    *,
    product: Product,
    warehouse: Warehouse,
    direction: str,
    quantity: int,
    notes: str,
    user,
    reference: str = "",
) -> StockMovement:
    if direction not in ("IN", "OUT"):
        raise ValidationError("Invalid stock adjustment direction.")

    if quantity < 1:
        raise ValidationError("Adjustment quantity must be positive.")

    # Lock the product and warehouse rows first.
    # This serializes stock operations for the same product/location.
    Product.objects.select_for_update().get(pk=product.pk)
    Warehouse.objects.select_for_update().get(pk=warehouse.pk)

    stock, _ = StockLevel.objects.get_or_create(
        product=product,
        warehouse=warehouse,
        defaults={"quantity": 0},
    )

    stock = StockLevel.objects.select_for_update().get(pk=stock.pk)

    if stock.available_quantity < quantity and direction == "OUT":
        raise ValidationError("Cannot issue reserved stock.")

    quantity_before = stock.quantity

    if direction == "IN":
        quantity_after = quantity_before + quantity
        movement_type = StockMovement.MovementType.RECEIPT
    else:
        if quantity_before < quantity:
            raise ValidationError(
                {"quantity": (f"Insufficient stock. Available: {quantity_before}.")}
            )

        if stock.available_quantity < quantity:
            raise ValidationError(
                {
                    "quantity": (
                        f"Cannot issue reserved stock. "
                        f"Total: {quantity_before}, "
                        f"Reserved: {stock.reserved_quantity}, "
                        f"Available: {stock.available_quantity}."
                    )
                }
            )

        quantity_after = quantity_before - quantity
        movement_type = StockMovement.MovementType.ISSUE

    stock.quantity = quantity_after
    stock.save(update_fields=["quantity", "updated_at"])

    return StockMovement.objects.create(
        product=product,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=quantity,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        reference=reference,
        notes=notes,
        created_by=user,
    )


@transaction.atomic
def transfer_stock(
    *,
    product: Product,
    source_warehouse: Warehouse,
    destination_warehouse: Warehouse,
    quantity: int,
    notes: str,
    user,
    reference: str = "",
) -> tuple[StockMovement, StockMovement]:
    if source_warehouse.pk == destination_warehouse.pk:
        raise ValidationError("Source and destination warehouses must be different.")

    if quantity < 1:
        raise ValidationError("Transfer quantity must be positive.")

    Product.objects.select_for_update().get(pk=product.pk)

    # Lock in consistent primary-key order to reduce deadlock risk.
    warehouse_ids = sorted(
        [
            source_warehouse.pk,
            destination_warehouse.pk,
        ]
    )

    list(
        Warehouse.objects.select_for_update()
        .filter(pk__in=warehouse_ids)
        .order_by("pk")
    )

    source_stock, _ = StockLevel.objects.get_or_create(
        product=product,
        warehouse=source_warehouse,
        defaults={"quantity": 0},
    )

    destination_stock, _ = StockLevel.objects.get_or_create(
        product=product,
        warehouse=destination_warehouse,
        defaults={"quantity": 0},
    )

    # Re-read and lock the stock rows.
    stock_ids = sorted(
        [
            source_stock.pk,
            destination_stock.pk,
        ]
    )

    locked_stocks = {
        stock.pk: stock
        for stock in StockLevel.objects.select_for_update()
        .filter(pk__in=stock_ids)
        .order_by("pk")
    }

    source_stock = locked_stocks[source_stock.pk]
    destination_stock = locked_stocks[destination_stock.pk]

    if source_stock.quantity < quantity:
        raise ValidationError(
            {
                "quantity": (
                    f"Insufficient source stock. "
                    f"Available: {source_stock.quantity}."
                )
            }
        )

    if source_stock.available_quantity < quantity:
        raise ValidationError(
            {
                "quantity": (
                    f"Cannot transfer reserved stock. "
                    f"Total: {source_stock.quantity}, "
                    f"Reserved: {source_stock.reserved_quantity}, "
                    f"Available: {source_stock.available_quantity}."
                )
            }
        )

    source_before = source_stock.quantity
    destination_before = destination_stock.quantity

    source_stock.quantity -= quantity
    destination_stock.quantity += quantity

    source_stock.save(update_fields=["quantity", "updated_at"])
    destination_stock.save(update_fields=["quantity", "updated_at"])

    movements = StockMovement.objects.bulk_create(
        [
            StockMovement(
                product=product,
                warehouse=source_warehouse,
                movement_type=StockMovement.MovementType.TRANSFER_OUT,
                quantity=quantity,
                quantity_before=source_before,
                quantity_after=source_stock.quantity,
                reference=reference,
                notes=notes,
                created_by=user,
            ),
            StockMovement(
                product=product,
                warehouse=destination_warehouse,
                movement_type=StockMovement.MovementType.TRANSFER_IN,
                quantity=quantity,
                quantity_before=destination_before,
                quantity_after=destination_stock.quantity,
                reference=reference,
                notes=notes,
                created_by=user,
            ),
        ]
    )

    return movements[0], movements[1]


@transaction.atomic
def reserve_stock(*, product_id: int, warehouse_id: int, quantity: int) -> StockLevel:
    if quantity < 1:
        raise ValidationError("Reservation quantity must be positive.")

    stock = (
        StockLevel.objects.select_for_update()
        .filter(product_id=product_id, warehouse_id=warehouse_id)
        .first()
    )

    if stock is None:
        raise ValidationError("No stock record exists for this product and warehouse.")

    if stock.available_quantity < quantity:
        raise ValidationError(
            f"Insufficient available stock. Available: {stock.available_quantity}."
        )

    stock.reserved_quantity = F("reserved_quantity") + quantity
    stock.save(update_fields=["reserved_quantity"])

    stock.refresh_from_db()
    return stock


@transaction.atomic
def release_reserved_stock(
    *,
    product_id: int,
    warehouse_id: int,
    quantity: int,
) -> StockLevel:
    if quantity < 1:
        raise ValidationError("Release quantity must be positive.")

    stock = (
        StockLevel.objects.select_for_update()
        .filter(product_id=product_id, warehouse_id=warehouse_id)
        .first()
    )

    if stock is None or stock.reserved_quantity < quantity:
        raise ValidationError("The requested stock reservation does not exist.")

    stock.reserved_quantity = F("reserved_quantity") - quantity
    stock.save(update_fields=["reserved_quantity"])

    stock.refresh_from_db()
    return stock


@transaction.atomic
def dispatch_reserved_stock(
    *,
    product_id: int,
    warehouse_id: int,
    quantity: int,
    reference: str,
    notes: str,
    user,
) -> StockLevel:
    if quantity < 1:
        raise ValidationError("Dispatch quantity must be positive.")

    stock = (
        StockLevel.objects.select_for_update()
        .select_related("product", "warehouse")
        .filter(product_id=product_id, warehouse_id=warehouse_id)
        .first()
    )

    if stock is None:
        raise ValidationError("No stock record exists.")

    if stock.reserved_quantity < quantity or stock.quantity < quantity:
        raise ValidationError("Insufficient reserved or physical stock.")

    before = stock.quantity

    stock.quantity = F("quantity") - quantity
    stock.reserved_quantity = F("reserved_quantity") - quantity
    stock.save(update_fields=["quantity", "reserved_quantity"])
    stock.refresh_from_db()

    StockMovement.objects.create(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovement.MovementType.ISSUE,
        quantity=quantity,
        quantity_before=before,
        quantity_after=stock.quantity,
        reference=reference,
        notes=notes,
        created_by=user,
    )

    return stock
