"""Endpoints the app loads or polls often must not make more database queries as the team grows."""

import datetime
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from payroll.models import PayExtra, StaffPay
from team.models import ChatGroup, ChatMessage, LeaveRequest

PASSWORD = "Str0ng-pass-123"


class QueryCountTests(TestCase):
    def setUp(self):
        self.pm = User.objects.create_user(
            username="pm", password=PASSWORD, role=Role.objects.get(unit__code="content", code="production_manager")
        )
        self.hr = User.objects.create_user(username="hr", password=PASSWORD, role=Role.objects.get(unit__code="content", code="hr"))
        self.boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        self.writer_role = Role.objects.get(unit__code="content", code="content_writer")
        self.count = 0

    def add_people(self, n):
        """n more writers, each with pay, leave, extras, chat messages and a group."""
        month = timezone.localdate().replace(day=1)
        group = ChatGroup.objects.create(name=f"G{self.count}", created_by=self.pm)
        group.members.add(self.pm)
        for _ in range(n):
            self.count += 1
            user = User.objects.create_user(username=f"w{self.count}", password=PASSWORD, role=self.writer_role)
            StaffPay.objects.create(user=user, monthly_salary=Decimal("20000"))
            PayExtra.objects.create(staff=user, month=month, kind="effort", amount=Decimal("100"))
            LeaveRequest.objects.create(user=user, start_date=month, end_date=month + datetime.timedelta(days=1), status="approved")
            ChatMessage.objects.create(sender=user, recipient=self.pm, body="hi")
            ChatMessage.objects.create(sender=user, recipient=None, body="team")
            ChatMessage.objects.create(sender=user, group=group, body="group")
            group.members.add(user)

    def queries(self, user, url):
        client = APIClient()
        client.force_authenticate(user)
        client.get(url)  # warm up (presence rows etc.)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(captured.captured_queries)

    def assert_flat(self, user, url):
        self.add_people(3)
        small = self.queries(user, url)
        self.add_people(12)
        large = self.queries(user, url)
        self.assertEqual(small, large, f"{url} makes more queries with a bigger team ({small} -> {large})")

    def test_chat_updates(self):
        self.assert_flat(self.pm, "/api/chat/updates/?after=0")

    def test_chat_contacts(self):
        self.assert_flat(self.pm, "/api/chat/contacts/")

    def test_team_room_messages_with_receipts(self):
        self.assert_flat(self.pm, "/api/chat/messages/?with=team")

    def test_payroll_list(self):
        self.assert_flat(self.pm, "/api/payroll/staff/")

    def test_my_leave_and_approvers(self):
        self.assert_flat(self.hr, "/api/team/leave/")

    def test_roles(self):
        self.assert_flat(self.boss, "/api/manage/roles/")

    def test_users(self):
        self.assert_flat(self.boss, "/api/manage/users/")
