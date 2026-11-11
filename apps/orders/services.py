from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import Product, StockLevel
from apps.inventory.services import (
    dispatch_reserved_stock,
    release_reserved_stock,
    reserve_stock,
)

from .models import Customer, Order, OrderItem

MONEY_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def recalculate_order(order: Order) -> Order:
    subtotal = sum(
        (item.unit_price * item.quantity for item in order.items.all()),
        Decimal("0.00"),
    )

    subtotal = money(subtotal)
    tax_amount = money(subtotal * order.tax_rate / Decimal("100"))

    order.subtotal = subtotal
    order.tax_amount = tax_amount
    order.total = money(subtotal + tax_amount)

    order.save(
        update_fields=[
            "subtotal",
            "tax_amount",
            "total",
            "updated_at",
        ]
    )

    return order


@transaction.atomic
def create_order(
    *,
    customer_id: int,
    items: list[dict],
    user,
    notes: str = "",
    required_date=None,
    tax_rate: Decimal = Decimal("0.00"),
) -> Order:
    if not items:
        raise ValidationError("An order must contain at least one item.")

    if tax_rate < 0 or tax_rate > 100:
        raise ValidationError("Tax rate must be between 0 and 100.")

    customer = Customer.objects.filter(
        id=customer_id,
        is_active=True,
    ).first()

    if customer is None:
        raise ValidationError("The selected customer is unavailable.")

    order = Order.objects.create(
        customer=customer,
        created_by=user,
        notes=notes,
        required_date=required_date,
        tax_rate=tax_rate,
    )

    seen_product_ids = set()

    for item_data in items:
        product_id = item_data["product_id"]
        quantity = item_data["quantity"]

        if quantity < 1:
            raise ValidationError("Item quantities must be positive.")

        if product_id in seen_product_ids:
            raise ValidationError("A product may only appear once in an order.")

        seen_product_ids.add(product_id)

        product = Product.objects.filter(
            id=product_id,
            is_active=True,
        ).first()

        if product is None:
            raise ValidationError(
                f"Product {product_id} does not exist or is inactive."
            )

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price=product.unit_price,
        )

    return recalculate_order(order)


@transaction.atomic
def update_draft_order(
    *,
    order_id: int,
    customer_id: int,
    items: list[dict],
    user,
    notes: str = "",
    required_date=None,
    tax_rate: Decimal = Decimal("0.00"),
) -> Order:
    order = Order.objects.select_for_update().get(id=order_id)

    if order.status != Order.Status.DRAFT:
        raise ValidationError("Only draft orders can be edited.")

    if order.created_by_id != user.id and not (
        user.is_superuser or user.role in ("ADMIN", "MANAGER")
    ):
        raise ValidationError("You cannot edit this order.")

    if not items:
        raise ValidationError("An order must contain at least one item.")

    customer = Customer.objects.filter(
        id=customer_id,
        is_active=True,
    ).first()

    if customer is None:
        raise ValidationError("The selected customer is unavailable.")

    order.customer = customer
    order.notes = notes
    order.required_date = required_date
    order.tax_rate = tax_rate
    order.updated_by = user
    order.save()

    order.items.all().delete()

    seen_product_ids = set()

    for item_data in items:
        product_id = item_data["product_id"]
        quantity = item_data["quantity"]

        if quantity < 1:
            raise ValidationError("Item quantities must be positive.")

        if product_id in seen_product_ids:
            raise ValidationError("A product may only appear once in an order.")

        seen_product_ids.add(product_id)

        product = Product.objects.filter(
            id=product_id,
            is_active=True,
        ).first()

        if product is None:
            raise ValidationError("A selected product is unavailable.")

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price=product.unit_price,
        )

    return recalculate_order(order)


@transaction.atomic
def submit_order(*, order_id: int, user) -> Order:
    order = Order.objects.select_for_update().get(id=order_id)

    if order.status != Order.Status.DRAFT:
        raise ValidationError("Only draft orders can be submitted.")

    if order.created_by_id != user.id and not (
        user.is_superuser or user.role in ("ADMIN", "MANAGER")
    ):
        raise ValidationError("You cannot submit this order.")

    if not order.items.exists():
        raise ValidationError("An empty order cannot be submitted.")

    order.status = Order.Status.PENDING
    order.updated_by = user
    order.save(update_fields=["status", "updated_by", "updated_at"])

    return order


@transaction.atomic
def confirm_order(
    *,
    order_id: int,
    warehouse_id: int,
    user,
) -> Order:
    order = Order.objects.select_for_update().prefetch_related("items").get(id=order_id)

    if order.status != Order.Status.PENDING:
        raise ValidationError("Only pending orders can be confirmed.")

    items = list(order.items.all())

    # Lock stock rows in a consistent order to reduce deadlock risk.
    stock_product_ids = sorted(item.product_id for item in items)

    for product_id in stock_product_ids:
        stock = (
            StockLevel.objects.select_for_update()
            .filter(
                product_id=product_id,
                warehouse_id=warehouse_id,
            )
            .first()
        )

        if stock is None:
            raise ValidationError(f"No stock record exists for product {product_id}.")

        item = next(i for i in items if i.product_id == product_id)

        if stock.available_quantity < item.quantity:
            raise ValidationError(
                f"Insufficient stock for {item.product.name}. "
                f"Available: {stock.available_quantity}; "
                f"required: {item.quantity}."
            )

    for item in items:
        item.warehouse_id = warehouse_id
        item.save(update_fields=["warehouse"])

        reserve_stock(
            product_id=item.product_id,
            warehouse_id=warehouse_id,
            quantity=item.quantity,
        )

    order.status = Order.Status.CONFIRMED
    order.updated_by = user
    order.save(update_fields=["status", "updated_by", "updated_at"])

    return order


@transaction.atomic
def start_processing(*, order_id: int, user) -> Order:
    order = Order.objects.select_for_update().get(id=order_id)

    if order.status != Order.Status.CONFIRMED:
        raise ValidationError("Only confirmed orders can enter processing.")

    order.status = Order.Status.PROCESSING
    order.updated_by = user
    order.save(update_fields=["status", "updated_by", "updated_at"])

    return order


@transaction.atomic
def ship_order(*, order_id: int, user) -> Order:
    order = Order.objects.select_for_update().prefetch_related("items").get(id=order_id)

    if order.status not in (
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
    ):
        raise ValidationError("Only confirmed or processing orders can ship.")

    # A warehouse must be recorded on each order item before shipping.
    for item in order.items.all():
        if not item.warehouse_id:
            raise ValidationError("An order item is missing its warehouse assignment.")

    for item in order.items.all():
        dispatch_reserved_stock(
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            quantity=item.quantity,
            reference=order.order_number,
            notes=f"Dispatch for order {order.order_number}",
            user=user,
        )

    order.status = Order.Status.SHIPPED
    order.shipped_at = timezone.now()
    order.updated_by = user
    order.save(
        update_fields=[
            "status",
            "shipped_at",
            "updated_by",
            "updated_at",
        ]
    )

    return order


@transaction.atomic
def deliver_order(*, order_id: int, user) -> Order:
    order = Order.objects.select_for_update().get(id=order_id)

    if order.status != Order.Status.SHIPPED:
        raise ValidationError("Only shipped orders can be delivered.")

    order.status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()
    order.updated_by = user
    order.save(
        update_fields=[
            "status",
            "delivered_at",
            "updated_by",
            "updated_at",
        ]
    )

    return order


@transaction.atomic
def cancel_order(
    *,
    order_id: int,
    user,
    reason: str,
) -> Order:
    order = Order.objects.select_for_update().prefetch_related("items").get(id=order_id)

    if order.status in (
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,
        Order.Status.CANCELLED,
    ):
        raise ValidationError("This order cannot be cancelled in its current status.")

    if order.status in (
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
    ):
        for item in order.items.all():
            if not item.warehouse_id:
                raise ValidationError(
                    "An order item is missing its warehouse assignment."
                )

            release_reserved_stock(
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                quantity=item.quantity,
            )

    order.status = Order.Status.CANCELLED
    order.cancellation_reason = reason
    order.updated_by = user
    order.save(
        update_fields=[
            "status",
            "cancellation_reason",
            "updated_by",
            "updated_at",
        ]
    )

    return order
