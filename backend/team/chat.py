"""Team chat for the Academic Content Writing unit.

Three kinds of conversation, each named by a key the app uses:
  "team"   the room for everyone in the unit,
  "<id>"   a one-to-one chat with that colleague,
  "g<id>"  a group chat, visible to its members only.

Messages carry sent / delivered / seen receipts. "Delivered" means the other
person's app has fetched the message (it polls every few seconds); "seen"
means they opened the conversation. The same polling records who is online.
"""

import datetime
import uuid
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .calls import incoming_call
from .files import ALLOWED, IMAGES, check_attachment, extension_of
from .models import ChatGroup, ChatMessage, ChatPresence, ChatRead
from .views import IsTeamMember, person, team_members
from .voice import FORMATS, MAX_VOICE_SECONDS, check_voice

User = get_user_model()
PAGE_SIZE = 50
# Background browser tabs may only poll once a minute, so allow a little more than that.
ONLINE_SECONDS = 75
TEAM_ROOM = Q(recipient__isnull=True, group__isnull=True)


# Conversations ----------------------------------------------------------------

@dataclass
class Conversation:
    key: str
    peer: User | None = None
    group: ChatGroup | None = None

    @property
    def kind(self):
        return "group" if self.group else "direct" if self.peer else "team"

    def messages(self, me):
        if self.group:
            return ChatMessage.objects.filter(group=self.group)
        if self.peer:
            return ChatMessage.objects.filter(
                Q(sender=me, recipient=self.peer) | Q(sender=self.peer, recipient=me)
            )
        return ChatMessage.objects.filter(TEAM_ROOM)

    def participants(self, me):
        if self.group:
            return list(group_members(self.group))
        if self.peer:
            return [me, self.peer]
        return list(team_members())

    def marker_for(self, user, me):
        """The ChatRead lookup for `user`'s view of this conversation (me being the other side of a DM)."""
        if self.group:
            return {"user": user, "group": self.group, "peer": None}
        if self.peer:
            other = self.peer if user.pk == me.pk else me
            return {"user": user, "peer": other, "group": None}
        return {"user": user, "peer": None, "group": None}


def group_members(group):
    return team_members().filter(chat_groups=group)


def my_groups(me):
    return ChatGroup.objects.filter(members=me)


def resolve(me, value, required=False):
    """'team', a teammate's id, or 'g<group id>' for a group you're in.

    When sending (`required`), the conversation must be named explicitly, so a
    missing or garbled value is refused instead of quietly going to the team room.
    """
    value = "" if value is None else str(value)
    if value == "team" or (value == "" and not required):
        return Conversation("team")
    if value in ("", "null", "NaN", "undefined"):
        raise ValidationError({"to": "Say which conversation this is for: 'team', a colleague's id or 'g<id>'."})
    if value.startswith("g"):
        group_id = parse_uuid(value[1:], "with")
        group = my_groups(me).filter(pk=group_id).first()
        if group is None:
            raise ValidationError({"with": "You're not in that group."})
        return Conversation(f"g{group.pk}", group=group)
    peer = team_members().exclude(pk=me.pk).filter(pk=parse_uuid(value, "with")).first()
    if peer is None:
        raise ValidationError({"with": "You can only chat with your own team."})
    return Conversation(str(peer.pk), peer=peer)


def parse_uuid(value, field):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({field: "That isn't a valid id."})


def parse_seq(value, field):
    """Message positions (`seq`) are whole numbers; ids are UUIDs."""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "Use a message's seq number."})


def visible_to(me):
    """Every message `me` may read."""
    return ChatMessage.objects.filter(
        TEAM_ROOM | Q(recipient=me) | Q(sender=me) | Q(group__in=my_groups(me))
    )


def conversation_key(message, me):
    if message.group_id:
        return f"g{message.group_id}"
    if message.recipient_id is None:
        return "team"
    return str(message.recipient_id if message.sender_id == me.pk else message.sender_id)


def message_data(message):
    return {
        "id": message.pk,
        # Increasing position in the chat; used for "newer than", unread, delivered and seen.
        "seq": message.seq,
        "sender": message.sender_id,
        "recipient": message.recipient_id,
        "group": message.group_id,
        "body": message.body,
        # Voice messages and files are fetched through the API, which checks you're in the conversation.
        "audio": f"/api/chat/messages/{message.pk}/audio/" if message.audio else None,
        "audio_duration": message.audio_duration,
        "file": (
            {
                "url": f"/api/chat/messages/{message.pk}/file/",
                "name": message.attachment_name,
                "size": message.attachment_size,
                "is_image": extension_of(message.attachment.name) in IMAGES,
            }
            if message.attachment
            else None
        ),
        "created_at": message.created_at.isoformat(),
    }


# Receipts and presence ----------------------------------------------------------

def presence_of(users):
    """{user id: {"online": bool, "last_seen": iso or None}} for these users."""
    cutoff = timezone.now() - datetime.timedelta(seconds=ONLINE_SECONDS)
    rows = {p.user_id: p for p in ChatPresence.objects.filter(user__in=users)}
    result = {}
    for user in users:
        p = rows.get(user.pk)
        result[str(user.pk)] = {
            "online": bool(p and p.last_seen >= cutoff),
            "last_seen": p.last_seen.isoformat() if p else None,
        }
    return result


def touch_presence(me, delivered_up_to=None):
    """Record that me's app is open, and how far it has fetched messages."""
    presence, created = ChatPresence.objects.get_or_create(
        user=me, defaults={"last_seen": timezone.now(), "delivered_up_to": delivered_up_to or 0}
    )
    if not created:
        presence.last_seen = timezone.now()
        fields = ["last_seen"]
        if delivered_up_to and delivered_up_to > presence.delivered_up_to:
            presence.delivered_up_to = delivered_up_to
            fields.append("delivered_up_to")
        presence.save(update_fields=fields)


def receipts(conversation, me):
    """How far each other participant has received and read this conversation.

    The app turns this into ticks on your own messages: one tick when sent, two
    when delivered to everyone, two blue ones when everyone has seen it.
    """
    others = [u for u in conversation.participants(me) if u.pk != me.pk]
    delivered = dict(ChatPresence.objects.filter(user__in=others).values_list("user", "delivered_up_to"))
    rows = []
    for user in others:
        lookup = conversation.marker_for(user, me)
        read = ChatRead.objects.filter(**lookup).values_list("last_read_seq", flat=True).first() or 0
        rows.append({
            "id": user.pk,
            "name": user.get_full_name() or user.username,
            "read_up_to": read,
            # Reading a message means it was delivered too.
            "delivered_up_to": max(delivered.get(user.pk, 0), read),
        })
    return rows


def mark_read(conversation, me, last_seq):
    marker, _ = ChatRead.objects.get_or_create(**conversation.marker_for(me, me))
    if last_seq > marker.last_read_seq:
        marker.last_read_seq = last_seq
        marker.save(update_fields=["last_read_seq"])


def unread_counts(me):
    """Unread messages per conversation key: {"team": n, "<colleague id>": n, "g<group id>": n}."""
    markers = ChatRead.objects.filter(user=me)
    team_read = (
        markers.filter(peer__isnull=True, group__isnull=True).values_list("last_read_seq", flat=True).first() or 0
    )
    counts = {
        "team": ChatMessage.objects.filter(TEAM_ROOM, seq__gt=team_read).exclude(sender=me).count()
    }
    direct_marker = markers.filter(peer=OuterRef("sender")).values("last_read_seq")[:1]
    direct = (
        ChatMessage.objects.filter(recipient=me, sender__in=team_members())
        .annotate(read_up_to=Coalesce(Subquery(direct_marker), Value(0)))
        .filter(seq__gt=F("read_up_to"))
        .values("sender")
        .annotate(n=Count("id"))
    )
    for row in direct:
        counts[str(row["sender"])] = row["n"]
    group_marker = markers.filter(group=OuterRef("group")).values("last_read_seq")[:1]
    grouped = (
        ChatMessage.objects.filter(group__in=my_groups(me))
        .exclude(sender=me)
        .annotate(read_up_to=Coalesce(Subquery(group_marker), Value(0)))
        .filter(seq__gt=F("read_up_to"))
        .values("group")
        .annotate(n=Count("id"))
    )
    for row in grouped:
        counts[f"g{row['group']}"] = row["n"]
    return counts


# Groups -----------------------------------------------------------------------

def can_manage_group(user, group):
    """The group's creator, or the unit's Production Manager (user management in the unit)."""
    return group.created_by_id == user.pk or user.has_perm("accounts.manage_unit_users")


def group_data(group, me, unread=None, last=None):
    members = list(group_members(group))
    return {
        "id": group.pk,
        "key": f"g{group.pk}",
        "name": group.name,
        "created_by": group.created_by_id,
        "members": [m.pk for m in members],
        "member_count": len(members),
        "can_manage": can_manage_group(me, group),
        "unread": (unread or {}).get(f"g{group.pk}", 0),
        "last_message": message_data(last) if last else None,
    }


def team_ids(values, me):
    """Validate a list of teammate ids."""
    ids = {parse_uuid(v, "members") for v in values or []}
    found = set(team_members().filter(pk__in=ids).values_list("pk", flat=True))
    if ids - found:
        raise ValidationError({"members": "Groups can only include people in your own team."})
    return found


def clean_name(value):
    name = str(value or "").strip()
    if not name:
        raise ValidationError({"name": "Give the group a name."})
    if len(name) > 80:
        raise ValidationError({"name": "Group names can be at most 80 characters."})
    return name


class ChatGroupsView(APIView):
    """POST {"name": "...", "members": [ids]} creates a group with you in it."""

    permission_classes = [IsTeamMember]

    def post(self, request):
        me = request.user
        name = clean_name(request.data.get("name"))
        members = team_ids(request.data.get("members"), me) | {me.pk}
        if len(members) < 2:
            raise ValidationError({"members": "Add at least one other person."})
        with transaction.atomic():
            group = ChatGroup.objects.create(name=name, created_by=me)
            group.members.set(members)
        return Response(group_data(group, me), status=status.HTTP_201_CREATED)


class ChatGroupDetailView(APIView):
    """PATCH {"name"?, "add"?: [ids], "remove"?: [ids]}: for the group's creator or the Production Manager."""

    permission_classes = [IsTeamMember]

    def patch(self, request, pk):
        me = request.user
        group = get_object_or_404(my_groups(me), pk=pk)
        if not can_manage_group(me, group):
            raise PermissionDenied("Only the person who made this group, or the Production Manager, can change it.")
        if "name" in request.data:
            group.name = clean_name(request.data.get("name"))
            group.save(update_fields=["name"])
        add = team_ids(request.data.get("add"), me)
        remove = team_ids(request.data.get("remove"), me)
        if me.pk in remove:
            raise ValidationError({"remove": "Use Leave group to leave it yourself."})
        group.members.add(*add)
        group.members.remove(*remove)
        return Response(group_data(group, me))


class ChatGroupLeaveView(APIView):
    permission_classes = [IsTeamMember]

    def post(self, request, pk):
        group = get_object_or_404(my_groups(request.user), pk=pk)
        group.members.remove(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# Messages -----------------------------------------------------------------------

class ChatContactsView(APIView):
    """The team room, your groups and everyone in the team, with last messages, unread counts and who's online."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        touch_presence(me)
        unread = unread_counts(me)
        members = list(team_members())
        online = presence_of(members)
        contacts = []
        for member in members:
            if member.pk == me.pk:
                continue
            last = Conversation(str(member.pk), peer=member).messages(me).order_by("-seq").first()
            contacts.append({
                **person(member),
                **online[str(member.pk)],
                "unread": unread.get(str(member.pk), 0),
                "last_message": message_data(last) if last else None,
            })
        groups = [
            group_data(g, me, unread, g.messages.order_by("-seq").first()) for g in my_groups(me)
        ]
        last_team = ChatMessage.objects.filter(TEAM_ROOM).order_by("-seq").first()
        return Response({
            "me": person(me),
            "team": {
                "unread": unread["team"],
                "last_message": message_data(last_team) if last_team else None,
                "member_count": len(members),
                "online_count": sum(1 for p in online.values() if p["online"]),
            },
            "groups": groups,
            "contacts": contacts,
        })


class ChatMessagesView(APIView):
    """GET ?with=team|<id>|g<id>[&after=<seq>|&before=<seq>]; POST {"to": ..., "body": "..."} (multipart for audio/file)."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        conversation = resolve(me, request.query_params.get("with"))
        messages = conversation.messages(me)
        after, before = request.query_params.get("after"), request.query_params.get("before")
        if after:
            page = list(messages.filter(seq__gt=parse_seq(after, "after")).order_by("seq")[:PAGE_SIZE * 4])
        else:
            if before:
                messages = messages.filter(seq__lt=parse_seq(before, "before"))
            page = list(reversed(messages.order_by("-seq")[:PAGE_SIZE]))
        if page:
            touch_presence(me, delivered_up_to=page[-1].seq)
        return Response({
            "messages": [message_data(m) for m in page],
            "receipts": receipts(conversation, me),
        })

    def post(self, request):
        me = request.user
        conversation = resolve(me, request.data.get("to"), required=True)
        body = str(request.data.get("body", "")).strip()
        audio = request.FILES.get("audio")
        upload = request.FILES.get("file")
        if not body and not audio and not upload:
            raise ValidationError({"body": "Write a message, record a voice message or attach a file first."})
        if audio and upload:
            raise ValidationError({"file": "Send the voice message and the file separately."})
        if len(body) > 4000:
            raise ValidationError({"body": "Messages can be at most 4,000 characters."})
        original_name = ""
        if upload:
            try:
                extension = check_attachment(upload)
            except DjangoValidationError as exc:
                raise ValidationError({"file": exc.messages})
            original_name = upload.name.replace("/", "_").replace("\\", "_")[:255]
            upload.name = f"file.{extension}"
        duration = None
        if audio:
            try:
                kind = check_voice(audio)
            except DjangoValidationError as exc:
                raise ValidationError({"audio": exc.messages})
            try:
                duration = max(0, min(int(float(request.data.get("duration") or 0)), MAX_VOICE_SECONDS))
            except ValueError:
                duration = None
            audio.name = f"voice.{kind}"
        message = ChatMessage.objects.create(
            sender=me, recipient=conversation.peer, group=conversation.group, body=body,
            audio=audio or "", audio_duration=duration,
            attachment=upload or "", attachment_name=original_name,
            attachment_size=upload.size if upload else None,
        )
        # seq comes from the database sequence; read it back, then count the message as read for you.
        message.refresh_from_db(fields=["seq"])
        mark_read(conversation, me, message.seq)
        touch_presence(me, delivered_up_to=message.seq)
        return Response(message_data(message), status=status.HTTP_201_CREATED)


def visible_message(me, pk):
    message = visible_to(me).filter(pk=pk).first()
    if message is None:
        raise Http404
    return message


class ChatAudioView(APIView):
    """Plays a voice message, only for people who can see its conversation."""

    permission_classes = [IsTeamMember]

    def get(self, request, pk):
        message = visible_message(request.user, pk)
        if not message.audio:
            raise Http404
        extension = message.audio.name.rsplit(".", 1)[-1]
        response = FileResponse(message.audio.open("rb"), content_type=FORMATS.get(extension, "application/octet-stream"))
        response["Cache-Control"] = "private, max-age=86400"
        return response


class ChatFileView(APIView):
    """Downloads a shared file (images open in the browser), only for people in its conversation."""

    permission_classes = [IsTeamMember]

    def get(self, request, pk):
        message = visible_message(request.user, pk)
        if not message.attachment:
            raise Http404
        extension = extension_of(message.attachment.name)
        inline = extension in IMAGES and request.query_params.get("download") is None
        response = FileResponse(
            message.attachment.open("rb"),
            as_attachment=not inline,
            filename=message.attachment_name or f"file.{extension}",
            content_type=ALLOWED.get(extension, "application/octet-stream"),
        )
        response["Cache-Control"] = "private, max-age=86400"
        # Belt and braces: nothing served here may run as a page.
        response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
        return response


class ChatReadView(APIView):
    """POST {"with": "team"|<id>|"g<id>", "last_seq": <seq>} marks a conversation read up to that message."""

    permission_classes = [IsTeamMember]

    def post(self, request):
        me = request.user
        conversation = resolve(me, request.data.get("with"), required=True)
        mark_read(conversation, me, parse_seq(request.data.get("last_seq") or 0, "last_seq"))
        return Response({"unread": unread_counts(me)})


class ChatUpdatesView(APIView):
    """Polled by the app every few seconds: unread counts, who's online, and new messages after ?after=<seq>.

    Polling also marks everything you can see as delivered to you, and you as online.
    """

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        visible = visible_to(me)
        latest = visible.order_by("-seq").values_list("seq", flat=True).first() or 0
        touch_presence(me, delivered_up_to=latest)
        unread = unread_counts(me)
        new = []
        after = request.query_params.get("after")
        if after and after.isdigit():
            incoming = (
                visible.filter(seq__gt=int(after))
                .exclude(sender=me)
                .select_related("sender", "group")
                .order_by("seq")[:20]
            )
            new = [
                {
                    **message_data(m),
                    "conversation": conversation_key(m, me),
                    "group_name": m.group.name if m.group_id else None,
                    "sender_person": person(m.sender),
                }
                for m in incoming
            ]
        return Response({
            "latest_seq": latest,
            "unread": unread,
            "total_unread": sum(unread.values()),
            "presence": presence_of(list(team_members().exclude(pk=me.pk))),
            # A call ringing for you right now, so the app can show the incoming-call screen.
            "incoming_call": incoming_call(me),
            "new": new,
        })
