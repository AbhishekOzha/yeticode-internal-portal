import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from team.models import ChatMessage, OfficeHours

PASSWORD = "Str0ng-pass-123"
PRIVATE_ROOT = tempfile.mkdtemp()


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


class OwnOfficeHoursTests(TeamTestCase):
    def put_hours(self, user):
        return self.client.put(
            f"/api/team/office-hours/{user.pk}/",
            {"start_time": "09:00", "end_time": "17:00", "work_days": [0]},
            format="json",
        )

    def test_nobody_but_a_super_admin_sets_their_own_hours(self):
        self.as_user(self.writer)
        self.assertEqual(self.put_hours(self.writer).status_code, 403)
        for manager in [self.production, self.hr]:
            self.as_user(manager)
            self.assertEqual(self.put_hours(manager).status_code, 403, manager.username)
            self.assertEqual(self.client.delete(f"/api/team/office-hours/{manager.pk}/").status_code, 403)
        # HR sets the Production Manager's hours, and the other way round.
        self.assertEqual(self.put_hours(self.production).status_code, 200)
        self.as_user(self.production)
        self.assertEqual(self.put_hours(self.hr).status_code, 200)


class ReviewTests(TeamTestCase):
    def setUp(self):
        super().setUp()
        self.supervisor = User.objects.create_user(
            username="sup", password=PASSWORD, role=role("content", "supervisor")
        )
        self.sales_manager = User.objects.create_user(
            username="salesmgr", password=PASSWORD, role=role("content", "sales_manager")
        )
        self.writer2 = User.objects.create_user(
            username="writer2", password=PASSWORD, role=role("content", "content_writer")
        )

    def review(self, subject, rating=4, comment="", month="2026-09"):
        return self.client.post(
            "/api/team/reviews/", {"subject": subject.pk, "rating": rating, "comment": comment, "month": month}, format="json"
        )

    def test_writer_reviews_everyone_in_the_team(self):
        self.as_user(self.writer)
        people = {p["username"] for p in self.client.get("/api/team/reviews/people/?month=2026-09").json()["people"]}
        self.assertEqual(people, {"pm", "hr", "sales", "sup", "salesmgr", "writer2"})
        for subject in [self.production, self.supervisor, self.writer2, self.sales_manager, self.hr]:
            self.assertEqual(self.review(subject, comment="Helpful").status_code, 201, subject.username)

    def test_sales_manager_reviews_too(self):
        self.as_user(self.sales_manager)
        for subject in [self.production, self.supervisor, self.writer, self.hr]:
            self.assertEqual(self.review(subject).status_code, 201)

    def test_one_review_per_person_per_month(self):
        self.as_user(self.writer)
        self.assertEqual(self.review(self.production, rating=3).status_code, 201)
        response = self.review(self.production, rating=5, comment="Better now")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rating"], 5)
        self.assertEqual(self.review(self.production, month="2026-08").status_code, 201)
        mine = self.client.get("/api/team/reviews/people/?month=2026-09").json()["people"]
        pm = next(p for p in mine if p["username"] == "pm")
        self.assertEqual(pm["my_review"]["comment"], "Better now")

    def test_rules(self):
        self.as_user(self.writer)
        self.assertEqual(self.review(self.writer).status_code, 400)  # yourself
        self.assertEqual(self.review(self.dev).status_code, 400)  # another unit
        self.assertEqual(self.review(self.production, rating=6).status_code, 400)
        self.assertEqual(self.review(self.production, month="2099-01").status_code, 400)
        for outsider in [self.dev, self.head_hr, self.boss]:
            self.as_user(outsider)
            self.assertEqual(self.review(self.writer).status_code, 403, outsider.username)

    def test_only_the_author_withdraws_a_review(self):
        self.as_user(self.writer)
        review_id = self.review(self.production).json()["id"]
        self.as_user(self.writer2)
        self.assertEqual(self.client.delete(f"/api/team/reviews/{review_id}/").status_code, 403)
        self.as_user(self.writer)
        self.assertEqual(self.client.delete(f"/api/team/reviews/{review_id}/").status_code, 204)

    def test_who_reads_reviews(self):
        self.as_user(self.writer)
        self.review(self.production, rating=2, comment="Late feedback")
        self.review(self.supervisor, rating=5)
        self.as_user(self.writer2)
        self.review(self.supervisor, rating=4)

        for reader in [self.boss, self.hr]:
            self.as_user(reader)
            rows = {p["username"]: p for p in self.client.get("/api/team/reviews/summary/?month=2026-09").json()["people"]}
            self.assertEqual(rows["sup"]["average"], 4.5)
            self.assertEqual(rows["pm"]["reviews"][0]["comment"], "Late feedback")
            self.assertEqual(rows["pm"]["reviews"][0]["author"]["username"], "writer")

        # The Production Manager reads everyone's reviews except the ones about themselves.
        self.as_user(self.production)
        rows = {p["username"] for p in self.client.get("/api/team/reviews/summary/?month=2026-09").json()["people"]}
        self.assertNotIn("pm", rows)
        self.assertIn("sup", rows)

        for user in [self.writer, self.supervisor, self.sales_manager, self.dev, self.head_hr]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/team/reviews/summary/").status_code, 403, user.username)


WEBM_HEADER = b"\x1a\x45\xdf\xa3" + b"\x00" * 60


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE_ROOT)
class VoiceMessageTests(TeamTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE_ROOT, ignore_errors=True)

    def send_voice(self, to=None, data=WEBM_HEADER, name="voice.webm", duration="7"):
        payload = {"audio": SimpleUploadedFile(name, data, content_type="audio/webm"), "duration": duration}
        if to:
            payload["to"] = to.pk
        return self.client.post("/api/chat/messages/", payload, format="multipart")

    def test_send_and_play_a_direct_voice_message(self):
        self.as_user(self.writer)
        response = self.send_voice(to=self.production)
        self.assertEqual(response.status_code, 201, response.json())
        message = response.json()
        self.assertEqual(message["audio_duration"], 7)
        self.assertEqual(message["body"], "")
        self.assertTrue(message["audio"].startswith("/api/chat/messages/"))

        self.as_user(self.production)
        played = self.client.get(message["audio"])
        self.assertEqual(played.status_code, 200)
        self.assertEqual(played["Content-Type"], "audio/webm")
        self.assertEqual(b"".join(played.streaming_content), WEBM_HEADER)

        # Nobody else in the team can play a direct voice message, and outsiders can't play any.
        for user in [self.hr, self.sales]:
            self.as_user(user)
            self.assertEqual(self.client.get(message["audio"]).status_code, 404)
        self.as_user(self.dev)
        self.assertEqual(self.client.get(message["audio"]).status_code, 403)

    def test_team_room_voice_message(self):
        self.as_user(self.writer)
        message = self.send_voice().json()
        self.as_user(self.sales)
        self.assertEqual(self.client.get(message["audio"]).status_code, 200)
        self.assertEqual(self.client.get("/api/chat/updates/").json()["unread"]["team"], 1)

    def test_only_audio_is_accepted(self):
        self.as_user(self.writer)
        self.assertEqual(self.send_voice(data=b"<html>not audio</html>", name="x.webm").status_code, 400)
        big = WEBM_HEADER + b"\x00" * (5 * 1024 * 1024)
        self.assertEqual(self.send_voice(data=big).status_code, 400)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_voice_files_are_not_public_media(self):
        self.as_user(self.writer)
        self.send_voice()
        stored = ChatMessage.objects.get().audio
        self.assertTrue(stored.path.startswith(PRIVATE_ROOT))
        self.assertNotIn("/media/", stored.name)
