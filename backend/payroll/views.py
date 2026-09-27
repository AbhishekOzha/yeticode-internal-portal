"""Payroll API for the Academic Content Writing unit.

Super Admins, and content-unit roles with the `manage_payroll` capability
(Production Manager and HR by default), set up each staff member's salary and
record their monthly extras. Only a Super Admin can change their own pay.
"""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import ImageUrlField

from .models import PAYROLL_UNIT, PayExtra, StaffPay, extra_amount

User = get_user_model()


def can_manage_payroll(user):
    if user.is_superuser:
        return True
    return (
        user.is_authenticated
        and user.unit is not None
        and user.unit.code == PAYROLL_UNIT
        and user.has_perm("accounts.manage_payroll")
    )


class CanManagePayroll(BasePermission):
    message = "Your role cannot manage payroll."

    def has_permission(self, request, view):
        return can_manage_payroll(request.user)


def payroll_staff():
    """Everyone who is paid through this payroll: active people in the content unit."""
    return (
        User.objects.filter(is_active=True, role__unit__code=PAYROLL_UNIT)
        .select_related("role", "pay")
        .order_by("role__rank", "first_name", "username")
    )


def check_not_own_pay(actor, staff):
    if staff.pk == actor.pk and not actor.is_superuser:
        raise PermissionDenied("Only a Super Admin can change your own pay.")


def parse_month(value):
    """'2026-09' -> date(2026, 9, 1). Missing means the current month."""
    if not value:
        return timezone.localdate().replace(day=1)
    try:
        return datetime.datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        raise ValidationError({"month": "Use the form YYYY-MM, e.g. 2026-09."})


class MonthField(serializers.Field):
    def to_representation(self, value):
        return value.strftime("%Y-%m")

    def to_internal_value(self, data):
        return parse_month(str(data))


class StaffPaySerializer(serializers.ModelSerializer):
    monthly_salary = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False
    )
    words_per_rate = serializers.IntegerField(min_value=1, required=False)
    words_rate_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False)
    hours_per_rate = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0.01"), required=False)
    hours_rate_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False)

    class Meta:
        model = StaffPay
        fields = [
            "monthly_salary", "words_per_rate", "words_rate_amount",
            "hours_per_rate", "hours_rate_amount", "daily_extra", "note",
        ]


def pay_for(user):
    """The saved pay setup, or an unsaved one holding the default rates."""
    try:
        return user.pay
    except StaffPay.DoesNotExist:
        return StaffPay(user=user)


def staff_row(user, extras):
    pay = pay_for(user)
    by_kind = {kind: Decimal("0") for kind in PayExtra.Kind.values}
    for extra in extras:
        by_kind[extra.kind] += extra.amount
    extras_total = sum(by_kind.values(), Decimal("0"))
    salary = pay.monthly_salary or Decimal("0")
    return {
        "id": user.pk,
        "full_name": user.get_full_name(),
        "username": user.username,
        "email": user.email,
        "avatar": ImageUrlField().to_representation(user.avatar),
        "role": user.role.name,
        "pay": StaffPaySerializer(pay).data,
        "extras_by_kind": {kind: str(amount) for kind, amount in by_kind.items()},
        "extras_count": len(extras),
        "extras_total": str(extras_total),
        "total": str(salary + extras_total),
    }


def extras_by_staff(month, staff_ids):
    grouped = defaultdict(list)
    for extra in PayExtra.objects.filter(month=month, staff_id__in=staff_ids):
        grouped[extra.staff_id].append(extra)
    return grouped


class StaffPayListView(APIView):
    """Everyone in the content unit with their pay setup and totals for ?month=YYYY-MM."""

    permission_classes = [CanManagePayroll]

    def get(self, request):
        month = parse_month(request.query_params.get("month"))
        staff = list(payroll_staff())
        grouped = extras_by_staff(month, [u.pk for u in staff])
        return Response({
            "month": month.strftime("%Y-%m"),
            "staff": [staff_row(user, grouped[user.pk]) for user in staff],
        })


class StaffPayDetailView(APIView):
    """Set up one person's salary and default rates. Every field is optional."""

    permission_classes = [CanManagePayroll]

    def patch(self, request, pk):
        user = get_object_or_404(payroll_staff(), pk=pk)
        check_not_own_pay(request.user, user)
        serializer = StaffPaySerializer(pay_for(user), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        user.refresh_from_db()
        month = parse_month(request.query_params.get("month"))
        return Response(staff_row(user, extras_by_staff(month, [user.pk])[user.pk]))


class PayExtraSerializer(serializers.ModelSerializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=User.objects.none())
    month = MonthField(required=False)
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), allow_null=True, required=False
    )
    per_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), allow_null=True, required=False
    )
    per_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False
    )
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PayExtra
        fields = [
            "id", "staff", "month", "date", "kind", "quantity", "per_quantity", "per_amount",
            "amount", "note", "created_by_name", "created_at",
        ]
        read_only_fields = ["created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = payroll_staff()

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.username if obj.created_by else None

    def validate(self, attrs):
        instance = self.instance
        current = {
            field: getattr(instance, field) if instance else None
            for field in ["staff", "month", "date", "kind", "quantity", "per_quantity", "per_amount", "amount"]
        }
        data = {**current, **attrs}
        if instance and "staff" in attrs and attrs["staff"] != instance.staff:
            raise serializers.ValidationError({"staff": "Add a new extra for the other person instead."})
        check_not_own_pay(self.context["request"].user, data["staff"])

        # The month comes from the day when only the day is given.
        if data["date"] and not attrs.get("month") and not instance:
            data["month"] = data["date"].replace(day=1)
        if not data["month"]:
            raise serializers.ValidationError({"month": "Pick the month this extra is paid in."})
        if data["date"] and data["date"].replace(day=1) != data["month"]:
            raise serializers.ValidationError({"date": "The day must fall in the chosen month."})

        kind = data["kind"]
        if kind in PayExtra.MEASURED:
            pay = pay_for(data["staff"])
            if kind == PayExtra.Kind.WORDS:
                default_per, default_amount, unit = pay.words_per_rate, pay.words_rate_amount, "words"
            else:
                default_per, default_amount, unit = pay.hours_per_rate, pay.hours_rate_amount, "hours"
            if not data["quantity"]:
                raise serializers.ValidationError({"quantity": f"Enter the {unit} done."})
            # A rate left out comes from the person's pay setup (6,000 words or 8 hours = NPR 1,000 by default).
            per_quantity = data["per_quantity"] if data["per_quantity"] is not None else default_per
            per_amount = data["per_amount"] if data["per_amount"] is not None else default_amount
            data.update(
                per_quantity=Decimal(per_quantity),
                per_amount=Decimal(per_amount),
                amount=extra_amount(data["quantity"], per_quantity, per_amount),
            )
        else:
            if not data["amount"]:
                raise serializers.ValidationError({"amount": "Enter the amount in NPR."})
            data.update(quantity=None, per_quantity=None, per_amount=None)

        attrs.update({key: data[key] for key in ["month", "quantity", "per_quantity", "per_amount", "amount"]})
        return attrs


class PayExtraViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Extras for ?month=YYYY-MM, optionally for one person with ?staff=<id>."""

    serializer_class = PayExtraSerializer
    permission_classes = [CanManagePayroll]
    pagination_class = None

    def get_queryset(self):
        extras = PayExtra.objects.filter(staff__role__unit__code=PAYROLL_UNIT).select_related("created_by")
        if self.action == "list":
            extras = extras.filter(month=parse_month(self.request.query_params.get("month")))
            if staff := self.request.query_params.get("staff"):
                extras = extras.filter(staff_id=staff)
        return extras

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        check_not_own_pay(self.request.user, instance.staff)
        instance.delete()
