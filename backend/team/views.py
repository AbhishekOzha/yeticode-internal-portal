"""Office hours and team chat, for the Academic Content Writing unit only.

Chat is open to every active person in the unit and nobody else, not even
Super Admins, so the team's conversations stay within the team. Office hours
are set by Super Admins and by the unit's Production Manager and HR (roles
with payroll, employee records or user management in the content unit).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import ImageUrlField

from .models import TEAM_UNIT, WEEKDAYS, ChatMessage, ChatRead, OfficeHours

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


class OfficeHoursListView(APIView):
    permission_classes = [CanManageOfficeHours]

    def get(self, request):
        members = team_members().select_related("office_hours")
        return Response({"weekdays": WEEKDAYS, "staff": [hours_row(u) for u in members]})


class OfficeHoursDetailView(APIView):
    permission_classes = [CanManageOfficeHours]

    def put(self, request, pk):
        user = get_object_or_404(team_members(), pk=pk)
        instance = OfficeHours.objects.filter(user=user).first()
        serializer = OfficeHoursSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=user)
        return Response(hours_row(user))

    def delete(self, request, pk):
        user = get_object_or_404(team_members(), pk=pk)
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


# Chat -----------------------------------------------------------------------

def conversation_filter(me, peer):
    """Messages in the team room (peer None) or between me and one colleague."""
    if peer is None:
        return Q(recipient__isnull=True)
    return Q(sender=me, recipient=peer) | Q(sender=peer, recipient=me)


def resolve_peer(me, value):
    """'team' (or empty) is the team room; anything else must be a teammate's id."""
    if value in (None, "", "team"):
        return None
    try:
        return team_members().exclude(pk=me.pk).get(pk=int(value))
    except (User.DoesNotExist, ValueError, TypeError):
        raise ValidationError({"with": "You can only chat with your own team."})


def message_data(message):
    return {
        "id": message.pk,
        "sender": message.sender_id,
        "recipient": message.recipient_id,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }


def unread_counts(me):
    """Unread messages per conversation: {"team": n, "<colleague id>": n}."""
    markers = ChatRead.objects.filter(user=me)
    team_read = markers.filter(peer__isnull=True).values_list("last_read_id", flat=True).first() or 0
    counts = {
        "team": ChatMessage.objects.filter(recipient__isnull=True, id__gt=team_read).exclude(sender=me).count()
    }
    # Each colleague's messages to me, beyond my read marker for that colleague.
    marker = markers.filter(peer=OuterRef("sender")).values("last_read_id")[:1]
    direct = (
        ChatMessage.objects.filter(recipient=me, sender__in=team_members())
        .annotate(read_up_to=Coalesce(Subquery(marker), Value(0)))
        .filter(id__gt=F("read_up_to"))
        .values("sender")
        .annotate(n=Count("id"))
    )
    for row in direct:
        counts[str(row["sender"])] = row["n"]
    return counts


class ChatContactsView(APIView):
    """Everyone in the team, with the last message and unread count for each conversation."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        unread = unread_counts(me)
        last_team = ChatMessage.objects.filter(recipient__isnull=True).order_by("-id").first()
        contacts = []
        for member in team_members().exclude(pk=me.pk):
            last = ChatMessage.objects.filter(conversation_filter(me, member)).order_by("-id").first()
            contacts.append({
                **person(member),
                "unread": unread.get(str(member.pk), 0),
                "last_message": message_data(last) if last else None,
            })
        return Response({
            "me": person(me),
            "team": {
                "unread": unread["team"],
                "last_message": message_data(last_team) if last_team else None,
                "member_count": len(contacts) + 1,
            },
            "contacts": contacts,
        })


class ChatMessagesView(APIView):
    """GET ?with=team|<id>[&after=<id>|&before=<id>]; POST {"to": null|<id>, "body": "..."}."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        peer = resolve_peer(me, request.query_params.get("with"))
        messages = ChatMessage.objects.filter(conversation_filter(me, peer))
        after, before = request.query_params.get("after"), request.query_params.get("before")
        try:
            if after:
                return Response([message_data(m) for m in messages.filter(id__gt=int(after))[:PAGE_SIZE * 4]])
            if before:
                messages = messages.filter(id__lt=int(before))
        except ValueError:
            raise ValidationError({"after": "Use a message id."})
        latest = list(messages.order_by("-id")[:PAGE_SIZE])
        return Response([message_data(m) for m in reversed(latest)])

    def post(self, request):
        me = request.user
        peer = resolve_peer(me, request.data.get("to"))
        body = str(request.data.get("body", "")).strip()
        if not body:
            raise ValidationError({"body": "Write a message first."})
        if len(body) > 4000:
            raise ValidationError({"body": "Messages can be at most 4,000 characters."})
        message = ChatMessage.objects.create(sender=me, recipient=peer, body=body)
        # Your own message counts as read.
        ChatRead.objects.update_or_create(user=me, peer=peer, defaults={"last_read_id": message.pk})
        return Response(message_data(message), status=status.HTTP_201_CREATED)


class ChatReadView(APIView):
    """POST {"with": "team"|<id>, "last_id": <id>} marks a conversation read up to that message."""

    permission_classes = [IsTeamMember]

    def post(self, request):
        me = request.user
        peer = resolve_peer(me, request.data.get("with"))
        try:
            last_id = int(request.data.get("last_id") or 0)
        except (TypeError, ValueError):
            raise ValidationError({"last_id": "Use a message id."})
        marker, _ = ChatRead.objects.get_or_create(user=me, peer=peer)
        if last_id > marker.last_read_id:
            marker.last_read_id = last_id
            marker.save(update_fields=["last_read_id"])
        return Response({"unread": unread_counts(me)})


class ChatUpdatesView(APIView):
    """Polled by the app: unread counts, plus messages to you or the team newer than ?after=<id>."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        unread = unread_counts(me)
        visible = ChatMessage.objects.filter(Q(recipient__isnull=True) | Q(recipient=me) | Q(sender=me))
        latest = visible.order_by("-id").values_list("id", flat=True).first() or 0
        new = []
        after = request.query_params.get("after")
        if after and after.isdigit():
            incoming = (
                visible.filter(id__gt=int(after))
                .exclude(sender=me)
                .select_related("sender")
                .order_by("id")[:20]
            )
            new = [{**message_data(m), "sender_person": person(m.sender)} for m in incoming]
        return Response({
            "latest_id": latest,
            "unread": unread,
            "total_unread": sum(unread.values()),
            "new": new,
        })
