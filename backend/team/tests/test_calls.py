import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from team.models import Call, ChatMessage

PASSWORD = "Str0ng-pass-123"


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


class CallTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username="asha", first_name="Asha", password=PASSWORD, role=role("content", "content_writer"))
        self.b = User.objects.create_user(username="bina", first_name="Bina", password=PASSWORD, role=role("content", "hr"))
        self.c = User.objects.create_user(username="chet", first_name="Chet", password=PASSWORD, role=role("content", "sales_executive"))
        self.dev = User.objects.create_user(username="dev", password=PASSWORD, role=role("web", "web_developer"))
        self.clients = {}

    def client_for(self, user):
        if user.pk not in self.clients:
            client = APIClient()
            client.force_authenticate(user)
            self.clients[user.pk] = client
        return self.clients[user.pk]

    def start(self, caller, callee):
        return self.client_for(caller).post("/api/calls/", {"to": str(callee.pk)}, format="json")

    def test_a_full_call(self):
        call = self.start(self.a, self.b).json()
        self.assertEqual(call["status"], "ringing")
        # Bina's app sees it ringing in its regular check.
        incoming = self.client_for(self.b).get("/api/chat/updates/").json()["incoming_call"]
        self.assertEqual((incoming["id"], incoming["peer"]["username"], incoming["incoming"]), (call["id"], "asha", True))
        self.assertIsNone(self.client_for(self.c).get("/api/chat/updates/").json()["incoming_call"])

        accepted = self.client_for(self.b).post(f"/api/calls/{call['id']}/accept/").json()
        self.assertEqual(accepted["status"], "active")

        # The browsers exchange set-up messages; each side only receives the other's.
        a, b = self.client_for(self.a), self.client_for(self.b)
        self.assertEqual(a.post(f"/api/calls/{call['id']}/signal/", {"kind": "offer", "data": {"sdp": "o"}}, format="json").status_code, 201)
        b.post(f"/api/calls/{call['id']}/signal/", {"kind": "answer", "data": {"sdp": "x"}}, format="json")
        b.post(f"/api/calls/{call['id']}/signal/", {"kind": "candidate", "data": {"candidate": "c1"}}, format="json")
        from_b = a.get(f"/api/calls/{call['id']}/?after=0").json()["signals"]
        self.assertEqual([s["kind"] for s in from_b], ["answer", "candidate"])
        last = from_b[-1]["seq"]
        self.assertEqual(a.get(f"/api/calls/{call['id']}/?after={last}").json()["signals"], [])
        self.assertEqual([s["kind"] for s in b.get(f"/api/calls/{call['id']}/?after=0").json()["signals"]], ["offer"])

        Call.objects.filter(pk=call["id"]).update(answered_at=timezone.now() - datetime.timedelta(seconds=192))
        ended = a.post(f"/api/calls/{call['id']}/end/").json()
        self.assertEqual((ended["status"], ended["duration"] >= 190), ("ended", True))
        note = ChatMessage.objects.get()
        self.assertEqual((note.sender, note.recipient, note.body), (self.a, self.b, "📞 Audio call · 3:12"))

    def test_decline_and_cancel(self):
        call = self.start(self.a, self.b).json()
        self.assertEqual(self.client_for(self.b).post(f"/api/calls/{call['id']}/decline/").json()["status"], "declined")
        call = self.start(self.a, self.b).json()
        self.assertEqual(self.client_for(self.a).post(f"/api/calls/{call['id']}/end/").json()["status"], "cancelled")
        self.assertEqual(
            list(ChatMessage.objects.order_by("seq").values_list("body", flat=True)),
            ["📞 Declined audio call", "📞 Cancelled audio call"],
        )

    def test_unanswered_call_becomes_missed(self):
        call = self.start(self.a, self.b).json()
        Call.objects.filter(pk=call["id"]).update(created_at=timezone.now() - datetime.timedelta(seconds=40))
        self.assertIsNone(self.client_for(self.b).get("/api/chat/updates/").json()["incoming_call"])
        self.assertEqual(Call.objects.get(pk=call["id"]).status, "missed")
        self.assertEqual(ChatMessage.objects.get().body, "📞 Missed audio call")
        # Bina now has an unread note about it.
        self.assertEqual(self.client_for(self.b).get("/api/chat/updates/").json()["unread"][str(self.a.pk)], 1)

    def test_call_ends_when_one_side_disappears(self):
        call = self.start(self.a, self.b).json()
        self.client_for(self.b).post(f"/api/calls/{call['id']}/accept/")
        Call.objects.filter(pk=call["id"]).update(callee_seen_at=timezone.now() - datetime.timedelta(seconds=30))
        self.assertEqual(self.client_for(self.a).get(f"/api/calls/{call['id']}/").json()["call"]["status"], "ended")

    def test_busy(self):
        self.start(self.a, self.b)
        busy = self.start(self.c, self.b)
        self.assertEqual(busy.status_code, 409)
        self.assertIn("Bina is on another call", busy.json()["detail"])
        self.assertEqual(self.start(self.a, self.c).status_code, 400)  # Asha is already in a call

    def test_only_the_team_and_the_two_people(self):
        self.assertEqual(self.start(self.a, self.dev).status_code, 400)
        self.assertEqual(self.start(self.a, self.a).status_code, 400)
        self.assertEqual(self.start(self.dev, self.a).status_code, 403)
        call = self.start(self.a, self.b).json()
        outsider = self.client_for(self.c)
        self.assertEqual(outsider.get(f"/api/calls/{call['id']}/").status_code, 403)
        self.assertEqual(outsider.post(f"/api/calls/{call['id']}/accept/").status_code, 403)
        self.assertEqual(
            outsider.post(f"/api/calls/{call['id']}/signal/", {"kind": "offer", "data": {}}, format="json").status_code, 403
        )
        # Only the person being called can pick up.
        self.assertEqual(self.client_for(self.a).post(f"/api/calls/{call['id']}/accept/").status_code, 400)

    def test_config_has_stun(self):
        config = self.client_for(self.a).get("/api/calls/config/").json()
        self.assertTrue(config["ice_servers"][0]["urls"][0].startswith("stun:"))


    def test_screen_share_signal_reaches_the_other_side(self):
        call = self.start(self.a, self.b).json()
        self.client_for(self.b).post(f"/api/calls/{call['id']}/accept/")
        a, b = self.client_for(self.a), self.client_for(self.b)
        self.assertEqual(
            a.post(f"/api/calls/{call['id']}/signal/", {"kind": "screen", "data": {"sharing": True}}, format="json").status_code, 201
        )
        signals = b.get(f"/api/calls/{call['id']}/?after=0").json()["signals"]
        self.assertEqual([(s["kind"], s["data"]) for s in signals], [("screen", {"sharing": True})])
        self.assertEqual(
            a.post(f"/api/calls/{call['id']}/signal/", {"kind": "video", "data": {}}, format="json").status_code, 400
        )
