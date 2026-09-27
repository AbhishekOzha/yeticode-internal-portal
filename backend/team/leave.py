"""Leave requests for the Academic Content Writing team.

Anyone in the team can apply. The unit's Production Manager and HR (roles with
user management or employee records in the unit) are notified straight away
and can approve or reject; so can Super Admins. Nobody decides their own
leave, so the Production Manager's leave goes to HR and vice versa. The
person who applied is notified of the decision.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import notify

from .models import LeaveRequest, leave_kind_label
from .views import IsTeamMember, in_team, person, team_members

APPROVER_CAPABILITIES = ["manage_unit_users", "manage_employee_records"]


def is_leave_approver(user):
    return any(user.has_perm(f"accounts.{code}") for code in APPROVER_CAPABILITIES)


def can_approve_leave(user):
    return user.is_superuser or (in_team(user) and is_leave_approver(user))


def approvers_for(applicant):
    """Who is notified of, and can decide, this person's leave: the unit's approvers except themselves."""
    return [u for u in team_members() if u.pk != applicant.pk and is_leave_approver(u)]


class CanApproveLeave(BasePermission):
    message = "Only the Production Manager, HR and Super Admins can decide leave requests."

    def has_permission(self, request, view):
        return can_approve_leave(request.user)


def leave_data(leave, viewer=None):
    return {
        "id": leave.pk,
        "user": person(leave.user),
        "kind": leave.kind,
        "kind_label": leave.kind_label,
        "paid": leave.paid,
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "half_day": leave.half_day,
        "days": leave.days,
        "reason": leave.reason,
        "status": leave.status,
        "decided_by": leave.decided_by.get_full_name() or leave.decided_by.username if leave.decided_by else None,
        "decided_at": leave.decided_at.isoformat() if leave.decided_at else None,
        "decision_note": leave.decision_note,
        "created_at": leave.created_at.isoformat(),
        "can_decide": bool(
            viewer and leave.status == LeaveRequest.Status.PENDING and leave.user_id != viewer.pk
            and can_approve_leave(viewer)
        ),
    }


def date_range(leave):
    if leave.start_date == leave.end_date:
        text = leave.start_date.strftime("%a %d %b")
        return f"{text} (half day)" if leave.half_day else text
    return f"{leave.start_date:%d %b} – {leave.end_date:%d %b}"


class LeaveApplySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=LeaveRequest.Kind.choices, default=LeaveRequest.Kind.CASUAL)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    half_day = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "The leave must end on or after the day it starts."})
        if attrs["half_day"] and attrs["end_date"] != attrs["start_date"]:
            raise serializers.ValidationError({"half_day": "A half day can only be a single day."})
        if (attrs["end_date"] - attrs["start_date"]).days > 90:
            raise serializers.ValidationError({"end_date": "Apply for at most 90 days at a time."})
        return attrs


class MyLeaveView(APIView):
    """GET: your requests and who will be notified. POST: apply for leave."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        return Response({
            "requests": [leave_data(l, me) for l in LeaveRequest.objects.filter(user=me).select_related("user__role", "decided_by")],
            "approvers": [person(u) for u in approvers_for(me)],
            "kinds": [{"value": v, "label": leave_kind_label(v)} for v, _ in LeaveRequest.Kind.choices],
        })

    def post(self, request):
        me = request.user
        serializer = LeaveApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        overlapping = LeaveRequest.objects.filter(
            user=me,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=data["end_date"],
            end_date__gte=data["start_date"],
        )
        if overlapping.exists():
            raise ValidationError({"start_date": "You already have leave pending or approved on some of these days."})
        approvers = approvers_for(me)
        with transaction.atomic():
            leave = LeaveRequest.objects.create(user=me, **data)
            name = me.get_full_name() or me.username
            notify(
                approvers,
                "leave_requested",
                f"{name} applied for {leave.kind_label[0].lower()}{leave.kind_label[1:]}",
                f"{date_range(leave)} · {leave.days:g} day{'s' if leave.days != 1 else ''}"
                + (f" · “{leave.reason[:120]}”" if leave.reason else ""),
                "leave",
            )
        return Response(
            {**leave_data(leave, me), "notified": [person(u) for u in approvers]},
            status=status.HTTP_201_CREATED,
        )


class CancelLeaveView(APIView):
    permission_classes = [IsTeamMember]

    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest, pk=pk, user=request.user)
        if leave.status != LeaveRequest.Status.PENDING:
            raise ValidationError({"status": "Only a pending request can be cancelled."})
        leave.status = LeaveRequest.Status.CANCELLED
        leave.save(update_fields=["status"])
        name = request.user.get_full_name() or request.user.username
        notify(approvers_for(request.user), "leave_cancelled", f"{name} cancelled a leave request", date_range(leave), "leave")
        return Response(leave_data(leave, request.user))


class TeamLeaveView(APIView):
    """Everyone's leave requests (not your own), for the people who decide them. ?status=pending|all."""

    permission_classes = [CanApproveLeave]

    def get(self, request):
        me = request.user
        leaves = (
            LeaveRequest.objects.filter(user__in=team_members())
            .exclude(user=me)
            .select_related("user__role", "decided_by")
        )
        if request.query_params.get("status", "pending") == "pending":
            leaves = leaves.filter(status=LeaveRequest.Status.PENDING).order_by("start_date")
        return Response({
            "pending": LeaveRequest.objects.filter(user__in=team_members(), status=LeaveRequest.Status.PENDING)
            .exclude(user=me)
            .count(),
            "requests": [leave_data(l, me) for l in leaves[:200]],
        })


class DecideLeaveView(APIView):
    """POST {"decision": "approve"|"reject", "note": "..."}."""

    permission_classes = [CanApproveLeave]

    def post(self, request, pk):
        me = request.user
        leave = get_object_or_404(LeaveRequest.objects.filter(user__in=team_members()), pk=pk)
        if leave.user_id == me.pk:
            raise PermissionDenied("You can't decide your own leave request.")
        if leave.status != LeaveRequest.Status.PENDING:
            raise ValidationError({"status": f"This request is already {leave.get_status_display().lower()}."})
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            raise ValidationError({"decision": "Choose approve or reject."})
        note = str(request.data.get("note") or "").strip()[:500]
        leave.status = LeaveRequest.Status.APPROVED if decision == "approve" else LeaveRequest.Status.REJECTED
        leave.decided_by, leave.decided_at, leave.decision_note = me, timezone.now(), note
        leave.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
        verdict = "approved" if decision == "approve" else "rejected"
        by = me.get_full_name() or me.username
        notify(
            [leave.user],
            f"leave_{verdict}",
            f"Your leave was {verdict}",
            f"{date_range(leave)} · by {by}" + (f" · “{note}”" if note else ""),
            "leave",
        )
        # Let the other approvers know it's been handled.
        others = [u for u in approvers_for(leave.user) if u.pk != me.pk]
        name = leave.user.get_full_name() or leave.user.username
        notify(others, "leave_decided", f"{by} {verdict} {name}'s leave", date_range(leave), "leave")
        return Response(leave_data(leave, me))

