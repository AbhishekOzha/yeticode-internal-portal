"""Office hours and team chat for the Academic Content Writing unit."""

from django.conf import settings
from django.db import models

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


class ChatMessage(models.Model):
    """A message to the whole team (no recipient) or to one colleague."""

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sent")
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="chat_received",
        help_text="Empty for the team room.",
    )
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["sender", "recipient", "id"])]

    def __str__(self):
        return f"{self.sender} → {self.recipient or 'team'}: {self.body[:40]}"


class ChatRead(models.Model):
    """The last message a person has seen in one conversation (a colleague, or the team room)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    peer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+",
        help_text="Empty for the team room.",
    )
    last_read_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "peer"], name="one_read_marker_per_conversation"),
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(peer__isnull=True), name="one_team_read_marker",
            ),
        ]
