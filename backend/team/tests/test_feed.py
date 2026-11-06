import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Role, User

PASSWORD = "Str0ng-pass-123"
TEMP = tempfile.mkdtemp()


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


def photo(name="p.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(PRIVATE_MEDIA_ROOT=TEMP)
class FeedTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP, ignore_errors=True)

    def setUp(self):
        self.a = User.objects.create_user(username="asha", first_name="Asha", password=PASSWORD, role=role("content", "content_writer"))
        self.b = User.objects.create_user(username="bina", first_name="Bina", password=PASSWORD, role=role("content", "hr"))
        self.dev = User.objects.create_user(username="dev", password=PASSWORD, role=role("web", "web_developer"))

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_post_like_comment_delete(self):
        a, b = self.client_for(self.a), self.client_for(self.b)
        post = a.post("/api/feed/posts/", {"body": "Hello team", "image": photo()}, format="multipart").json()
        self.assertTrue(post["image"])
        self.assertEqual(b.get(post["image"]).status_code, 200)
        self.assertEqual(b.post(f"/api/feed/posts/{post['id']}/like/").json()["like_count"], 1)
        b.post(f"/api/feed/posts/{post['id']}/like/")
        liked = b.get("/api/feed/posts/").json()["results"][0]
        self.assertEqual((liked["like_count"], liked["liked"]), (1, True))
        self.assertFalse(a.get("/api/feed/posts/").json()["results"][0]["liked"])
        self.assertEqual(b.delete(f"/api/feed/posts/{post['id']}/like/").json()["like_count"], 0)
        self.assertEqual(b.post(f"/api/feed/posts/{post['id']}/comments/", {"body": "Nice"}, format="json").status_code, 201)
        self.assertEqual(a.get("/api/feed/posts/").json()["results"][0]["comment_count"], 1)
        self.assertEqual(b.delete(f"/api/feed/posts/{post['id']}/").status_code, 403)
        self.assertEqual(a.delete(f"/api/feed/posts/{post['id']}/").status_code, 204)

    def test_empty_and_bad_posts_refused(self):
        a = self.client_for(self.a)
        self.assertEqual(a.post("/api/feed/posts/", {"body": " "}, format="multipart").status_code, 400)
        bad = SimpleUploadedFile("x.html", b"<script>", content_type="text/html")
        self.assertEqual(a.post("/api/feed/posts/", {"image": bad}, format="multipart").status_code, 400)

    def test_outsiders_are_kept_out(self):
        self.assertEqual(self.client_for(self.dev).get("/api/feed/posts/").status_code, 403)
        self.assertEqual(self.client_for(self.dev).get("/api/feed/stories/").status_code, 403)

    def test_stories(self):
        a, b = self.client_for(self.a), self.client_for(self.b)
        story = a.post("/api/feed/stories/", {"image": photo(), "caption": "Morning"}, format="multipart").json()
        rows = b.get("/api/feed/stories/").json()["results"]
        self.assertEqual(rows[0]["user"]["username"], "asha")
        self.assertFalse(rows[0]["all_seen"])
        self.assertEqual(b.get(story["image"]).status_code, 200)
        b.post(f"/api/feed/stories/{story['id']}/viewed/")
        self.assertTrue(b.get("/api/feed/stories/").json()["results"][0]["all_seen"])
        self.assertEqual([v["username"] for v in a.get(f"/api/feed/stories/{story['id']}/viewed/").json()["results"]], ["bina"])
        self.assertEqual(b.get(f"/api/feed/stories/{story['id']}/viewed/").status_code, 403)

    def test_stories_expire_after_a_day(self):
        import datetime

        from django.utils import timezone

        from team.models import Story

        a = self.client_for(self.a)
        story = a.post("/api/feed/stories/", {"image": photo()}, format="multipart").json()
        Story.objects.filter(pk=story["id"]).update(created_at=timezone.now() - datetime.timedelta(hours=25))
        self.assertEqual(a.get("/api/feed/stories/").json()["results"], [])
        self.assertEqual(a.get(story["image"]).status_code, 404)
