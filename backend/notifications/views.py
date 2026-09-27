import uuid

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification

LATEST = 30


def notification_data(n):
    return {
        "id": n.pk,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat(),
    }


class NotificationListView(APIView):
    """Your latest notifications and how many are unread. The app polls this."""

    def get(self, request):
        mine = Notification.objects.filter(recipient=request.user)
        return Response({
            "unread": mine.filter(read_at__isnull=True).count(),
            "notifications": [notification_data(n) for n in mine[:LATEST]],
        })


class NotificationReadView(APIView):
    """POST {"ids": [...]} marks those read; POST {} marks all of yours read."""

    def post(self, request):
        mine = Notification.objects.filter(recipient=request.user, read_at__isnull=True)
        ids = request.data.get("ids")
        if ids:
            valid = []
            for value in ids if isinstance(ids, list) else [ids]:
                try:
                    valid.append(uuid.UUID(str(value)))
                except ValueError:
                    continue
            mine = mine.filter(pk__in=valid)
        mine.update(read_at=timezone.now())
        return Response({"unread": Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()})
