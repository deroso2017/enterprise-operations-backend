import django_filters

from .models import Order


class OrderFilter(django_filters.FilterSet):
    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte",
    )
    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte",
    )
    customer = django_filters.NumberFilter(
        field_name="customer_id",
    )

    class Meta:
        model = Order
        fields = [
            "status",
            "customer",
            "created_after",
            "created_before",
        ]
