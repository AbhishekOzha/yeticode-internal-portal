from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from team.models import ChatMessage, OfficeHours

PASSWORD = "Str0ng-pass-123"


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


class TeamTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        self.production = User.objects.create_user(
            username="pm", first_name="Priya", password=PASSWORD, role=role("content", "production_manager")
        )
        self.hr = User.objects.create_user(username="hr", password=PASSWORD, role=role("content", "hr"))
        self.writer = User.objects.create_user(
            username="writer", first_name="Asha", password=PASSWORD, role=role("content", "content_writer")
        )
        self.sales = User.objects.create_user(
            username="sales", password=PASSWORD, role=role("content", "sales_executive")
        )
        self.dev = User.objects.create_user(username="dev", password=PASSWORD, role=role("web", "web_developer"))
        self.head_hr = User.objects.create_user(
            username="chief", password=PASSWORD, role=Role.objects.get(code="head_hr")
        )

    def as_user(self, user):
        self.client.force_authenticate(user)


class OfficeHoursTests(TeamTestCase):
    def test_managers_set_shifts(self):
        for manager, shift in [(self.boss, ("07:00", "15:00")), (self.production, ("09:00", "17:00")), (self.hr, ("10:00", "18:00"))]:
            self.as_user(manager)
            response = self.client.put(
                f"/api/team/office-hours/{self.writer.pk}/",
                {"start_time": shift[0], "end_time": shift[1], "work_days": [6, 0, 1, 2, 3, 4], "reminders": True},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.json())
            self.assertEqual(response.json()["office_hours"]["start_time"], shift[0])
        hours = OfficeHours.objects.get(user=self.writer)
        self.assertEqual(hours.day_numbers, [0, 1, 2, 3, 4, 6])

    def test_others_cannot_set_shifts(self):
        for user in [self.writer, self.sales, self.dev, self.head_hr]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/team/office-hours/").status_code, 403)
            response = self.client.put(
                f"/api/team/office-hours/{self.writer.pk}/",
                {"start_time": "09:00", "end_time": "17:00", "work_days": [0]},
                format="json",
            )
            self.assertEqual(response.status_code, 403)

    def test_only_content_staff_have_office_hours(self):
        self.as_user(self.boss)
        names = {row["username"] for row in self.client.get("/api/team/office-hours/").json()["staff"]}
        self.assertEqual(names, {"pm", "hr", "writer", "sales"})
        response = self.client.put(
            f"/api/team/office-hours/{self.dev.pk}/", {"start_time": "09:00", "end_time": "17:00", "work_days": [0]}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_shift_must_end_after_it_starts(self):
        self.as_user(self.production)
        response = self.client.put(
            f"/api/team/office-hours/{self.writer.pk}/",
            {"start_time": "17:00", "end_time": "09:00", "work_days": [0]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.put(
            f"/api/team/office-hours/{self.writer.pk}/",
            {"start_time": "09:00", "end_time": "17:00", "work_days": []},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_staff_read_their_own_shift(self):
        OfficeHours.objects.create(user=self.writer, start_time="10:00", end_time="18:00")
        self.as_user(self.writer)
        data = self.client.get("/api/team/office-hours/me/").json()
        self.assertEqual(data["office_hours"]["start_time"], "10:00")
        self.assertEqual(data["office_hours"]["work_days"], [0, 1, 2, 3, 4, 6])
        self.assertEqual(data["time_zone"], "Asia/Kathmandu")
        self.as_user(self.dev)
        self.assertEqual(self.client.get("/api/team/office-hours/me/").status_code, 403)

    def test_clear_shift(self):
        OfficeHours.objects.create(user=self.writer, start_time="10:00", end_time="18:00")
        self.as_user(self.hr)
        self.assertEqual(self.client.delete(f"/api/team/office-hours/{self.writer.pk}/").status_code, 204)
        self.assertFalse(OfficeHours.objects.filter(user=self.writer).exists())


class ChatTests(TeamTestCase):
    def send(self, body, to=None):
        return self.client.post("/api/chat/messages/", {"to": to, "body": body}, format="json")

    def test_only_the_content_team_can_chat(self):
        for outsider in [self.dev, self.head_hr, self.boss]:
            self.as_user(outsider)
            self.assertEqual(self.client.get("/api/chat/contacts/").status_code, 403, outsider.username)
            self.assertEqual(self.send("hi").status_code, 403, outsider.username)
            self.assertEqual(self.client.get("/api/chat/messages/?with=team").status_code, 403)

    def test_contacts_are_the_whole_team(self):
        self.as_user(self.writer)
        data = self.client.get("/api/chat/contacts/").json()
        self.assertEqual({c["username"] for c in data["contacts"]}, {"pm", "hr", "sales"})
        self.assertEqual(data["team"]["member_count"], 4)
        self.assertIn("avatar", data["contacts"][0])

    def test_cannot_message_outside_the_team(self):
        self.as_user(self.writer)
        self.assertEqual(self.send("hi", to=self.dev.pk).status_code, 400)
        self.assertEqual(self.client.get(f"/api/chat/messages/?with={self.dev.pk}").status_code, 400)

    def test_team_room_and_direct_messages(self):
        self.as_user(self.writer)
        self.assertEqual(self.send("Morning, team!").status_code, 201)
        self.assertEqual(self.send("Draft is ready", to=self.production.pk).status_code, 201)

        self.as_user(self.production)
        updates = self.client.get("/api/chat/updates/").json()
        self.assertEqual(updates["unread"]["team"], 1)
        self.assertEqual(updates["unread"][str(self.writer.pk)], 1)
        self.assertEqual(updates["total_unread"], 2)
        direct = self.client.get(f"/api/chat/messages/?with={self.writer.pk}").json()
        self.assertEqual([m["body"] for m in direct], ["Draft is ready"])

        # Direct messages stay between the two people.
        self.as_user(self.hr)
        self.assertEqual(self.client.get(f"/api/chat/messages/?with={self.writer.pk}").json(), [])
        self.assertEqual(self.client.get("/api/chat/updates/").json()["total_unread"], 1)

    def test_read_markers_and_new_message_updates(self):
        self.as_user(self.production)
        latest = self.client.get("/api/chat/updates/").json()["latest_id"]
        self.as_user(self.writer)
        first = self.send("One", to=self.production.pk).json()
        self.send("Two", to=self.production.pk)

        self.as_user(self.production)
        updates = self.client.get(f"/api/chat/updates/?after={latest}").json()
        self.assertEqual([m["body"] for m in updates["new"]], ["One", "Two"])
        self.assertEqual(updates["new"][0]["sender_person"]["full_name"], "Asha")
        response = self.client.post("/api/chat/read/", {"with": self.writer.pk, "last_id": first["id"]}, format="json")
        self.assertEqual(response.json()["unread"][str(self.writer.pk)], 1)
        self.client.post("/api/chat/read/", {"with": self.writer.pk, "last_id": updates["latest_id"]}, format="json")
        self.assertEqual(self.client.get("/api/chat/updates/").json()["total_unread"], 0)

    def test_own_messages_are_not_unread(self):
        self.as_user(self.writer)
        self.send("Hello")
        self.assertEqual(self.client.get("/api/chat/updates/").json()["total_unread"], 0)

    def test_empty_message_is_refused(self):
        self.as_user(self.writer)
        self.assertEqual(self.send("   ").status_code, 400)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_deactivated_people_drop_out(self):
        self.sales.is_active = False
        self.sales.save()
        self.as_user(self.writer)
        names = {c["username"] for c in self.client.get("/api/chat/contacts/").json()["contacts"]}
        self.assertNotIn("sales", names)
