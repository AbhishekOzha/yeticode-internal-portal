"""Office hours and team chat for the Academic Content Writing unit."""

import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Func

TEAM_UNIT = "content"

# Python weekday numbers (Monday = 0). The office works Sunday to Friday by default.
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_WORK_DAYS = "6,0,1,2,3,4"


class OfficeHours(models.Model):
    """When one person's shift starts and ends, e.g. 09:00 to 17:00."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="office_hours"
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    work_days = models.CharField(
        max_length=20, default=DEFAULT_WORK_DAYS,
        help_text="Comma-separated weekday numbers, Monday = 0. Reminders only come on these days.",
    )
    reminders = models.BooleanField(
        default=True, help_text="Remind 30, 15 and 5 minutes before the shift and 5 minutes before it ends."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "office hours"

    def __str__(self):
        return f"{self.user}: {self.start_time:%H:%M}–{self.end_time:%H:%M}"

    @property
    def day_numbers(self):
        return [int(d) for d in self.work_days.split(",") if d.strip()]


class PrivateStorage(FileSystemStorage):
    """Files under PRIVATE_MEDIA_ROOT, which is never served directly (read on each use, so tests can change it)."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


def private_storage():
    """Voice messages live outside MEDIA_ROOT and are only served through the chat API."""
    return PrivateStorage()


def voice_upload_to(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    return f"chat_voice/{uuid.uuid4().hex}.{extension}"


def attachment_upload_to(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"chat_files/{uuid.uuid4().hex}.{extension}"


class NextMessageSeq(Func):
    """nextval() on the chat message sequence: message ids are random UUIDs, so order comes from this."""

    template = "nextval('team_chatmessage_seq')"
    output_field = models.BigIntegerField()


class ChatGroup(models.Model):
    """A group chat within the team, e.g. "Order 4512 writers"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="chat_groups")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    """A message to the whole team (no recipient or group), one colleague, or a group."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sent")
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="chat_received",
        help_text="Empty for the team room.",
    )
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="messages")
    # Increasing message number (ids are UUIDs): used for ordering, "new since", read and delivered markers.
    seq = models.BigIntegerField(db_default=NextMessageSeq(), unique=True, editable=False)
    body = models.TextField(max_length=4000, blank=True)
    audio = models.FileField(upload_to=voice_upload_to, storage=private_storage, blank=True)
    audio_duration = models.PositiveIntegerField(null=True, blank=True, help_text="Seconds.")
    attachment = models.FileField(upload_to=attachment_upload_to, storage=private_storage, blank=True, max_length=200)
    attachment_name = models.CharField(max_length=255, blank=True, help_text="The file's original name.")
    attachment_size = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["seq"]
        indexes = [models.Index(fields=["sender", "recipient", "seq"])]

    def __str__(self):
        return f"{self.sender} → {self.recipient or 'team'}: {self.body[:40] or self.attachment_name or 'voice message'}"


class ChatRead(models.Model):
    """The last message a person has seen in one conversation: a colleague, a group or the team room."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    peer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+",
        help_text="The colleague, for a one-to-one chat.",
    )
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    last_read_seq = models.PositiveBigIntegerField(default=0, help_text="The seq of the last message seen.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "peer"], name="one_read_marker_per_conversation"),
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(peer__isnull=True, group__isnull=True),
                name="one_team_read_marker",
            ),
            models.UniqueConstraint(
                fields=["user", "group"], condition=models.Q(group__isnull=False), name="one_group_read_marker",
            ),
        ]


class ChatPresence(models.Model):
    """When someone last had the app open, and the newest message their app has fetched (delivered)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="chat_presence"
    )
    last_seen = models.DateTimeField()
    delivered_up_to = models.PositiveBigIntegerField(default=0, help_text="The seq of the newest message fetched.")


class Review(models.Model):
    """One colleague's monthly review of another: a 1–5 rating and an optional comment.

    Anyone in the team can review anyone else in it (writers, supervisors, the
    Production Manager, Sales Manager, HR, …), once per person per month.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received")
    month = models.DateField(help_text="The first day of the month the review is for.")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["author", "subject", "month"], name="one_review_per_person_per_month"),
            models.CheckConstraint(condition=~models.Q(author=models.F("subject")), name="no_self_review"),
        ]

    def __str__(self):
        return f"{self.author} on {self.subject} ({self.month:%Y-%m}): {self.rating}/5"


# Leave types that are paid. For now none are: every leave day is unpaid and
# comes off the payslip. Add a type here (e.g. "sick") to make it paid.
PAID_LEAVE_KINDS = frozenset()


def leave_kind_label(kind):
    """The type's name, marked "(Unpaid)" unless it's paid, e.g. "Casual leave (Unpaid)"."""
    label = LeaveRequest.Kind(kind).label
    if kind in PAID_LEAVE_KINDS or kind == LeaveRequest.Kind.UNPAID:
        return label
    return f"{label} (Unpaid)"


class LeaveRequest(models.Model):
    """A leave application from someone in the team, approved or rejected by the Production Manager or HR."""

    class Kind(models.TextChoices):
        CASUAL = "casual", "Casual leave"
        SICK = "sick", "Sick leave"
        ANNUAL = "annual", "Annual leave"
        UNPAID = "unpaid", "Unpaid leave"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_requests")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.CASUAL)
    start_date = models.DateField()
    end_date = models.DateField()
    half_day = models.BooleanField(default=False, help_text="Only for a single day.")
    reason = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="leave_ends_after_start"),
        ]

    def __str__(self):
        return f"{self.user}: {self.get_kind_display()} {self.start_date}–{self.end_date} ({self.status})"

    @property
    def paid(self):
        return self.kind in PAID_LEAVE_KINDS

    @property
    def kind_label(self):
        return leave_kind_label(self.kind)

    @property
    def days(self):
        if self.half_day:
            return 0.5
        return (self.end_date - self.start_date).days + 1


class NextCallSignalSeq(Func):
    """nextval() on the call signal sequence, so signals can be read in order ("after" a number)."""

    template = "nextval('team_callsignal_seq')"
    output_field = models.BigIntegerField()


class Call(models.Model):
    """A one-to-one audio call between two people in the team."""

    class Status(models.TextChoices):
        RINGING = "ringing", "Ringing"
        ACTIVE = "active", "In progress"
        ENDED = "ended", "Ended"
        MISSED = "missed", "Missed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    OPEN = (Status.RINGING, Status.ACTIVE)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_made")
    callee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_received")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RINGING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Each side's app checks in every second or two during a call; a side that goes quiet has left.
    caller_seen_at = models.DateTimeField(null=True, blank=True)
    callee_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.caller} → {self.callee} ({self.status})"

    @property
    def duration_seconds(self):
        if self.answered_at and self.ended_at:
            return int((self.ended_at - self.answered_at).total_seconds())
        return None


class CallSignal(models.Model):
    """WebRTC set-up messages (offer, answer, network candidates) passed between the two browsers."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="signals")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    seq = models.BigIntegerField(db_default=NextCallSignalSeq(), unique=True, editable=False)
    kind = models.CharField(max_length=20)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seq"]
