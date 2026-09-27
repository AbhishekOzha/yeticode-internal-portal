"""In-app notifications: the bell in the header. Other apps create them with notify()."""

import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40, help_text="What it's about, e.g. leave_requested.")
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=120, blank=True, help_text="The app page to open, e.g. leave?tab=requests.")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self):
        return f"{self.recipient}: {self.title}"


def notify(recipients, kind, title, body="", link=""):
    """Create one notification per recipient (skipping duplicates and inactive users)."""
    seen = set()
    rows = []
    for user in recipients:
        if user.pk in seen or not user.is_active:
            continue
        seen.add(user.pk)
        rows.append(Notification(recipient=user, kind=kind, title=title[:160], body=body[:500], link=link))
    Notification.objects.bulk_create(rows)
    return rows
