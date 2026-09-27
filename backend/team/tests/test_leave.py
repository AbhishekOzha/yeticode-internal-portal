from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import Notification
from team.models import LeaveRequest

PASSWORD = "Str0ng-pass-123"


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


class LeaveTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        self.production = User.objects.create_user(
            username="pm", first_name="Priya", password=PASSWORD, role=role("content", "production_manager")
        )
        self.hr = User.objects.create_user(username="hr", first_name="Hari", password=PASSWORD, role=role("content", "hr"))
        self.writer = User.objects.create_user(
            username="writer", first_name="Asha", password=PASSWORD, role=role("content", "content_writer")
        )
        self.sales = User.objects.create_user(username="sales", password=PASSWORD, role=role("content", "sales_executive"))
        self.dev = User.objects.create_user(username="dev", password=PASSWORD, role=role("web", "web_developer"))
        self.web_lead = User.objects.create_user(username="lead", password=PASSWORD, role=role("web", "team_lead"))

    def as_user(self, user):
        self.client.force_authenticate(user)

    def apply(self, **data):
        payload = {"kind": "casual", "start_date": "2026-10-05", "end_date": "2026-10-06", "reason": "Family event", **data}
        return self.client.post("/api/team/leave/", payload, format="json")

    def test_applying_notifies_production_manager_and_hr(self):
        self.as_user(self.writer)
        preview = self.client.get("/api/team/leave/").json()
        self.assertEqual({a["username"] for a in preview["approvers"]}, {"pm", "hr"})
        response = self.apply()
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["days"], 2)
        self.assertEqual({a["username"] for a in response.json()["notified"]}, {"pm", "hr"})

        notified = set(Notification.objects.filter(kind="leave_requested").values_list("recipient__username", flat=True))
        self.assertEqual(notified, {"pm", "hr"})  # not other staff, other units or the applicant
        self.as_user(self.production)
        bell = self.client.get("/api/notifications/").json()
        self.assertEqual(bell["unread"], 1)
        self.assertIn("Asha applied for casual leave", bell["notifications"][0]["title"])
        self.assertEqual(bell["notifications"][0]["link"], "leave")

    def test_approve_and_the_applicant_is_notified(self):
        self.as_user(self.writer)
        leave_id = self.apply().json()["id"]
        self.as_user(self.hr)
        pending = self.client.get("/api/team/leave/requests/").json()
        self.assertEqual(pending["pending"], 1)
        self.assertTrue(pending["requests"][0]["can_decide"])
        response = self.client.post(f"/api/team/leave/{leave_id}/decide/", {"decision": "approve", "note": "Enjoy!"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["status"], "approved")
        self.assertEqual(response.json()["decided_by"], "Hari")

        self.as_user(self.writer)
        bell = self.client.get("/api/notifications/").json()
        self.assertEqual(bell["notifications"][0]["title"], "Your leave was approved")
        self.assertIn("Enjoy!", bell["notifications"][0]["body"])
        # The other approver hears it was handled; it can't be decided twice.
        self.assertTrue(Notification.objects.filter(recipient=self.production, kind="leave_decided").exists())
        self.as_user(self.production)
        again = self.client.post(f"/api/team/leave/{leave_id}/decide/", {"decision": "reject"}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_reject(self):
        self.as_user(self.writer)
        leave_id = self.apply().json()["id"]
        self.as_user(self.production)
        self.client.post(f"/api/team/leave/{leave_id}/decide/", {"decision": "reject", "note": "Deadline week"}, format="json")
        self.assertEqual(LeaveRequest.objects.get().status, "rejected")
        self.assertTrue(Notification.objects.filter(recipient=self.writer, title="Your leave was rejected").exists())

    def test_nobody_decides_their_own_leave(self):
        self.as_user(self.production)
        response = self.apply()
        self.assertEqual({a["username"] for a in response.json()["notified"]}, {"hr"})
        leave_id = response.json()["id"]
        self.assertEqual(self.client.get("/api/team/leave/requests/").json()["requests"], [])
        self.assertEqual(
            self.client.post(f"/api/team/leave/{leave_id}/decide/", {"decision": "approve"}, format="json").status_code, 403
        )
        self.as_user(self.hr)
        self.assertEqual(
            self.client.post(f"/api/team/leave/{leave_id}/decide/", {"decision": "approve"}, format="json").status_code, 200
        )

    def test_super_admin_can_decide(self):
        self.as_user(self.writer)
        leave_id = self.apply().json()["id"]
        self.as_user(self.boss)
        self.assertEqual(
            self.client.post(f"/api/team/leave/{leave_id}/decide/", {"decision": "approve"}, format="json").status_code, 200
        )

    def test_who_can_apply_and_decide(self):
        for outsider in [self.dev, self.web_lead, self.boss]:
            self.as_user(outsider)
            self.assertEqual(self.apply().status_code, 403, outsider.username)
        for user in [self.writer, self.sales, self.dev, self.web_lead]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/team/leave/requests/").status_code, 403, user.username)

    def test_validation(self):
        self.as_user(self.writer)
        self.assertEqual(self.apply(start_date="2026-10-06", end_date="2026-10-05").status_code, 400)
        self.assertEqual(self.apply(half_day=True).status_code, 400)  # half day over two days
        response = self.apply(start_date="2026-10-09", end_date="2026-10-09", half_day=True)
        self.assertEqual(response.json()["days"], 0.5)
        self.assertEqual(self.apply(start_date="2026-10-09", end_date="2026-10-12").status_code, 400)  # overlaps

    def test_cancel_own_pending_request(self):
        self.as_user(self.writer)
        leave_id = self.apply().json()["id"]
        self.as_user(self.sales)
        self.assertEqual(self.client.post(f"/api/team/leave/{leave_id}/cancel/").status_code, 404)
        self.as_user(self.writer)
        self.assertEqual(self.client.post(f"/api/team/leave/{leave_id}/cancel/").json()["status"], "cancelled")
        self.assertEqual(self.apply().status_code, 201)  # the days are free again

    def test_notifications_can_be_marked_read(self):
        self.as_user(self.writer)
        self.apply()
        self.as_user(self.hr)
        note = self.client.get("/api/notifications/").json()["notifications"][0]
        self.assertEqual(self.client.post("/api/notifications/read/", {"ids": [note["id"], "nonsense"]}, format="json").json()["unread"], 0)
        # Only your own.
        self.as_user(self.production)
        self.assertEqual(self.client.get("/api/notifications/").json()["unread"], 1)
