"""Office hours, and the team membership rules shared with chat and reviews (Academic Content Writing only).

Chat is open to every active person in the unit and nobody else, not even
Super Admins, so the team's conversations stay within the team. Office hours
are set by Super Admins and by the unit's Production Manager and HR (roles
with payroll, employee records or user management in the content unit).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import ImageUrlField

from .models import TEAM_UNIT, WEEKDAYS, OfficeHours

User = get_user_model()
MANAGER_CAPABILITIES = ["manage_payroll", "manage_employee_records", "manage_unit_users"]
PAGE_SIZE = 50


def in_team(user):
    return (
        user.is_authenticated and user.is_active and not user.is_superuser
        and user.unit is not None and user.unit.code == TEAM_UNIT
    )


def can_manage_office_hours(user):
    if user.is_superuser:
        return True
    return in_team(user) and any(user.has_perm(f"accounts.{code}") for code in MANAGER_CAPABILITIES)


class IsTeamMember(BasePermission):
    message = "Team chat is only for the Academic Content Writing team."

    def has_permission(self, request, view):
        return in_team(request.user)


class CanManageOfficeHours(BasePermission):
    message = "Your role cannot set office hours."

    def has_permission(self, request, view):
        return can_manage_office_hours(request.user)


def team_members():
    return (
        User.objects.filter(is_active=True, is_superuser=False, role__unit__code=TEAM_UNIT)
        .select_related("role")
        .order_by("first_name", "last_name", "username")
    )


def person(user):
    return {
        "id": user.pk,
        "full_name": user.get_full_name(),
        "username": user.username,
        "email": user.email,
        "avatar": ImageUrlField().to_representation(user.avatar),
        "role": user.role.name if user.role_id else None,
    }


# Office hours ---------------------------------------------------------------

class WorkDaysField(serializers.ListField):
    """Stored as "6,0,1,2,3,4"; sent and received as a sorted list of weekday numbers (Monday = 0)."""

    child = serializers.IntegerField(min_value=0, max_value=6)

    def to_representation(self, value):
        return sorted({int(d) for d in value.split(",") if d.strip()})

    def to_internal_value(self, data):
        return ",".join(str(d) for d in sorted(set(super().to_internal_value(data))))


class OfficeHoursSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format="%H:%M")
    end_time = serializers.TimeField(format="%H:%M")
    work_days = WorkDaysField(allow_empty=False)

    class Meta:
        model = OfficeHours
        fields = ["start_time", "end_time", "work_days", "reminders", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise ValidationError({"end_time": "The shift must end after it starts."})
        return attrs


def hours_row(user):
    try:
        hours = OfficeHoursSerializer(user.office_hours).data
    except OfficeHours.DoesNotExist:
        hours = None
    return {**person(user), "office_hours": hours}


def check_not_own_hours(actor, user):
    if user.pk == actor.pk and not actor.is_superuser:
        raise PermissionDenied("Your own office hours are set by someone else: a Super Admin, HR or the Production Manager.")


class OfficeHoursListView(APIView):
    permission_classes = [CanManageOfficeHours]

    def get(self, request):
        members = team_members().select_related("office_hours")
        return Response({"weekdays": WEEKDAYS, "staff": [hours_row(u) for u in members]})


class OfficeHoursDetailView(APIView):
    permission_classes = [CanManageOfficeHours]

    def put(self, request, pk):
        user = get_object_or_404(team_members(), pk=pk)
        check_not_own_hours(request.user, user)
        instance = OfficeHours.objects.filter(user=user).first()
        serializer = OfficeHoursSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        return Response(hours_row(user))

    def delete(self, request, pk):
        user = get_object_or_404(team_members(), pk=pk)
        check_not_own_hours(request.user, user)
        OfficeHours.objects.filter(user=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyOfficeHoursView(APIView):
    """The signed-in person's shift, for their reminders. Times are in the company's time zone."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        hours = OfficeHours.objects.filter(user=request.user).first()
        return Response({
            "time_zone": settings.TIME_ZONE,
            "office_hours": OfficeHoursSerializer(hours).data if hours else None,
        })
