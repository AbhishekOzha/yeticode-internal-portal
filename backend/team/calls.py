"""One-to-one audio calls for the Academic Content Writing team, while the app is open.

The audio goes straight between the two browsers (WebRTC). This server only
rings the other person and passes the browsers' set-up messages ("signals":
offer, answer, network candidates) between them. Nothing is recorded.

Calls that nobody answers become "missed" after RING_SECONDS; a call whose
other side stops checking in (tab closed, connection lost) ends after
GONE_SECONDS. Every call leaves a note in the two people's chat.
"""

import datetime
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Call, CallSignal, ChatMessage
from .views import IsTeamMember, person, team_members

RING_SECONDS = 35
GONE_SECONDS = 20
# offer/answer/candidate set up the connection; "screen" says whether the sender is sharing their screen.
SIGNAL_KINDS = {"offer", "answer", "candidate", "screen"}
MAX_SIGNAL_BYTES = 20_000


def ice_servers():
    """STUN finds a direct route; an optional TURN relay (from .env) covers strict networks."""
    servers = [{"urls": settings.CALL_STUN_URLS}]
    if settings.CALL_TURN_URL:
        servers.append({
            "urls": settings.CALL_TURN_URL,
            "username": settings.CALL_TURN_USERNAME,
            "credential": settings.CALL_TURN_PASSWORD,
        })
    return servers


def duration_text(seconds):
    minutes, secs = divmod(max(seconds or 0, 0), 60)
    return f"{minutes}:{secs:02d}"


def log_call(call):
    """Leave a note in the two people's chat, like "📞 Audio call · 3:12" or "📞 Missed audio call"."""
    text = {
        Call.Status.ENDED: f"📞 Audio call · {duration_text(call.duration_seconds)}",
        Call.Status.MISSED: "📞 Missed audio call",
        Call.Status.DECLINED: "📞 Declined audio call",
        Call.Status.CANCELLED: "📞 Cancelled audio call",
    }.get(call.status)
    if text:
        ChatMessage.objects.create(sender=call.caller, recipient=call.callee, body=text)


def finish(call, new_status):
    """Close an open call once (safe if two requests race)."""
    with transaction.atomic():
        call = Call.objects.select_for_update().get(pk=call.pk)
        if call.status not in Call.OPEN:
            return call
        call.status = new_status
        call.ended_at = timezone.now()
        call.save(update_fields=["status", "ended_at"])
        log_call(call)
    return call


def expire(call):
    """Ringing too long -> missed; one side gone quiet during the call -> ended."""
    now = timezone.now()
    if call.status == Call.Status.RINGING and now - call.created_at > datetime.timedelta(seconds=RING_SECONDS):
        return finish(call, Call.Status.MISSED)
    if call.status == Call.Status.ACTIVE:
        gone = now - datetime.timedelta(seconds=GONE_SECONDS)
        if (call.caller_seen_at and call.caller_seen_at < gone) or (call.callee_seen_at and call.callee_seen_at < gone):
            return finish(call, Call.Status.ENDED)
    return call


def open_calls(user):
    """The user's calls still ringing or in progress, after tidying up stale ones."""
    calls = Call.objects.filter(Q(caller=user) | Q(callee=user), status__in=Call.OPEN).select_related("caller", "callee")
    return [c for c in (expire(c) for c in calls) if c.status in Call.OPEN]


def call_data(call, me):
    peer = call.callee if call.caller_id == me.pk else call.caller
    return {
        "id": call.pk,
        "status": call.status,
        "incoming": call.callee_id == me.pk,
        "peer": person(peer),
        "created_at": call.created_at.isoformat(),
        "answered_at": call.answered_at.isoformat() if call.answered_at else None,
        "duration": call.duration_seconds,
    }


def incoming_call(me):
    """A call ringing for `me`, for the app's regular check (None if there isn't one)."""
    ringing = [c for c in open_calls(me) if c.callee_id == me.pk and c.status == Call.Status.RINGING]
    return call_data(ringing[0], me) if ringing else None


def my_call(me, pk):
    call = get_object_or_404(Call.objects.select_related("caller", "callee"), pk=pk)
    if me.pk not in (call.caller_id, call.callee_id):
        raise PermissionDenied("That isn't your call.")
    return expire(call)


def check_in(call, me):
    field = "caller_seen_at" if call.caller_id == me.pk else "callee_seen_at"
    Call.objects.filter(pk=call.pk).update(**{field: timezone.now()})


class CallConfigView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request):
        return Response({"ice_servers": ice_servers(), "ring_seconds": RING_SECONDS})


class StartCallView(APIView):
    """POST {"to": <colleague id>} rings them."""

    permission_classes = [IsTeamMember]

    def post(self, request):
        me = request.user
        try:
            callee_id = uuid.UUID(str(request.data.get("to")))
        except (ValueError, TypeError):
            callee_id = None
        callee = team_members().exclude(pk=me.pk).filter(pk=callee_id).first() if callee_id else None
        if callee is None:
            raise ValidationError({"to": "You can only call people in your own team."})
        if open_calls(me):
            raise ValidationError({"detail": "You're already in a call."})
        if open_calls(callee):
            return Response(
                {"detail": f"{callee.get_full_name() or callee.username} is on another call."},
                status=status.HTTP_409_CONFLICT,
            )
        call = Call.objects.create(caller=me, callee=callee, caller_seen_at=timezone.now())
        return Response(call_data(call, me), status=status.HTTP_201_CREATED)


class CallDetailView(APIView):
    """GET ?after=<seq>: the call's status and the other side's signals since then. Also a heartbeat."""

    permission_classes = [IsTeamMember]

    def get(self, request, pk):
        me = request.user
        call = my_call(me, pk)
        if call.status in Call.OPEN:
            check_in(call, me)
        try:
            after = int(request.query_params.get("after") or 0)
        except ValueError:
            raise ValidationError({"after": "Use a signal's seq number."})
        signals = call.signals.filter(seq__gt=after).exclude(sender=me).order_by("seq")[:100]
        return Response({
            "call": call_data(call, me),
            "signals": [{"seq": s.seq, "kind": s.kind, "data": s.data} for s in signals],
        })


class CallSignalView(APIView):
    """POST {"kind": "offer"|"answer"|"candidate", "data": {...}} passes a WebRTC message to the other side."""

    permission_classes = [IsTeamMember]

    def post(self, request, pk):
        me = request.user
        call = my_call(me, pk)
        if call.status not in Call.OPEN:
            raise ValidationError({"detail": "This call has ended."})
        kind = request.data.get("kind")
        data = request.data.get("data")
        if kind not in SIGNAL_KINDS or not isinstance(data, dict):
            raise ValidationError({"kind": "Send an offer, answer, candidate or screen signal."})
        if len(str(data)) > MAX_SIGNAL_BYTES:
            raise ValidationError({"data": "That signal is too large."})
        CallSignal.objects.create(call=call, sender=me, kind=kind, data=data)
        check_in(call, me)
        return Response(status=status.HTTP_201_CREATED)


class CallActionView(APIView):
    """POST .../accept/, .../decline/ or .../end/."""

    permission_classes = [IsTeamMember]
    action = None

    def post(self, request, pk):
        me = request.user
        call = my_call(me, pk)
        if self.action == "accept":
            if call.callee_id != me.pk or call.status != Call.Status.RINGING:
                raise ValidationError({"detail": "This call isn't ringing for you any more."})
            now = timezone.now()
            Call.objects.filter(pk=call.pk, status=Call.Status.RINGING).update(
                status=Call.Status.ACTIVE, answered_at=now, caller_seen_at=now, callee_seen_at=now
            )
            call.refresh_from_db()
        elif self.action == "decline":
            if call.callee_id != me.pk:
                raise ValidationError({"detail": "Only the person being called can decline."})
            call = finish(call, Call.Status.DECLINED)
        else:  # end
            if call.status == Call.Status.RINGING:
                call = finish(call, Call.Status.CANCELLED if call.caller_id == me.pk else Call.Status.DECLINED)
            else:
                call = finish(call, Call.Status.ENDED)
        return Response(call_data(call, me))
