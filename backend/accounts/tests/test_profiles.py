import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import CompanySettings, Role, User

PASSWORD = "Str0ng-pass-123"
MEDIA_ROOT = tempfile.mkdtemp()


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


def image_file(name="photo.png", image_format="PNG", size=(32, 32)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "#3451d1").save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class UploadTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client = APIClient()
        self.boss = User.objects.create_superuser(
            username="boss@yeticode.com", email="boss@yeticode.com", password=PASSWORD
        )
        self.web_admin = User.objects.create_user(
            username="lead@yeticode.com", email="lead@yeticode.com",
            password=PASSWORD, role=role("web", "team_lead"),
        )
        self.dev = User.objects.create_user(
            username="dev@yeticode.com", email="dev@yeticode.com",
            password=PASSWORD, role=role("web", "web_developer"),
        )
        self.student = User.objects.create_user(
            username="learner", email="learner@yeticode.com",
            password=PASSWORD, role=role("training", "student"),
        )

    def as_user(self, user):
        self.client.force_authenticate(user)


class ProfileTests(UploadTestCase):
    def test_user_uploads_and_removes_own_photo(self):
        self.as_user(self.dev)
        response = self.client.patch("/api/profile/", {"avatar": image_file()}, format="multipart")
        self.assertEqual(response.status_code, 200, response.json())
        self.dev.refresh_from_db()
        self.assertTrue(self.dev.avatar.name.startswith("avatars/"))
        self.assertEqual(response.json()["avatar"], self.dev.avatar.url)
        old = self.dev.avatar.name

        response = self.client.patch("/api/profile/", {"avatar": image_file("new.jpg", "JPEG")}, format="multipart")
        self.assertEqual(response.status_code, 200, response.json())
        self.dev.refresh_from_db()
        self.assertNotEqual(self.dev.avatar.name, old)
        self.assertFalse(self.dev.avatar.storage.exists(old), "the replaced photo is deleted")

        response = self.client.patch("/api/profile/", {"avatar": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.dev.refresh_from_db()
        self.assertFalse(self.dev.avatar)
        self.assertIsNone(response.json()["avatar"])

    def test_photo_must_be_a_small_png_jpg_or_webp(self):
        self.as_user(self.dev)
        svg = SimpleUploadedFile("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", content_type="image/svg+xml")
        gif = image_file("anim.gif", "GIF")
        for bad in [svg, gif, SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")]:
            response = self.client.patch("/api/profile/", {"avatar": bad}, format="multipart")
            self.assertEqual(response.status_code, 400, bad.name)
            self.assertIn("avatar", response.json())
        big = SimpleUploadedFile("big.png", image_file().read() + b"\0" * (2 * 1024 * 1024), content_type="image/png")
        response = self.client.patch("/api/profile/", {"avatar": big}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("2 MB", str(response.json()))
        self.assertEqual(self.client.patch("/api/profile/", {"avatar": image_file("p.webp", "WEBP")}, format="multipart").status_code, 200)

    def test_user_adds_edits_and_removes_secondary_email(self):
        self.as_user(self.dev)
        response = self.client.patch("/api/profile/", {"secondary_email": "dev.personal@example.com"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["secondary_email"], "dev.personal@example.com")
        self.client.patch("/api/profile/", {"secondary_email": "dev2@example.com"}, format="json")
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.secondary_email, "dev2@example.com")
        self.client.patch("/api/profile/", {"secondary_email": ""}, format="json")
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.secondary_email, "")

    def test_secondary_email_must_be_new(self):
        self.as_user(self.dev)
        for taken in ["DEV@yeticode.com", "learner@yeticode.com"]:
            response = self.client.patch("/api/profile/", {"secondary_email": taken}, format="json")
            self.assertEqual(response.status_code, 400, taken)

    def test_user_cannot_change_or_remove_primary_email(self):
        self.as_user(self.dev)
        for email in ["someone.else@yeticode.com", ""]:
            response = self.client.patch("/api/profile/", {"email": email}, format="json")
            self.assertEqual(response.status_code, 400)
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.email, "dev@yeticode.com")

    def test_profile_only_changes_the_signed_in_user(self):
        self.as_user(self.dev)
        self.client.patch("/api/profile/", {"secondary_email": "mine@example.com", "id": self.student.pk}, format="json")
        self.student.refresh_from_db()
        self.assertEqual(self.student.secondary_email, "")
        # Regular users have no way to reach another account's profile.
        response = self.client.patch(
            f"/api/manage/users/{self.student.pk}/", {"secondary_email": "x@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_profile_needs_sign_in(self):
        self.assertEqual(self.client.get("/api/profile/").status_code, 403)

    def test_photo_shows_in_directory(self):
        self.as_user(self.dev)
        self.client.patch("/api/profile/", {"avatar": image_file()}, format="multipart")
        members = {m["username"]: m for m in self.client.get("/api/unit/members/").json()}
        self.assertTrue(members["dev@yeticode.com"]["avatar"].startswith("/media/avatars/"))
        self.assertIsNone(members["lead@yeticode.com"]["avatar"])


class AdminEmailTests(UploadTestCase):
    def test_super_admin_edits_primary_and_secondary_email(self):
        self.as_user(self.boss)
        response = self.client.patch(
            f"/api/manage/users/{self.student.pk}/",
            {"email": "student@yeticode.com", "secondary_email": "student@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "student@yeticode.com")
        self.assertEqual(self.student.secondary_email, "student@example.com")
        self.assertEqual(self.student.username, "learner", "a separate username is left alone")

    def test_changing_email_keeps_the_username(self):
        self.as_user(self.boss)
        response = self.client.patch(
            f"/api/manage/users/{self.dev.pk}/", {"email": "developer@yeticode.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.username, "dev@yeticode.com")  # usernames are separate from emails now
        self.client.logout()
        login = self.client.post(
            "/api/auth/login/", {"username": "developer@yeticode.com", "password": PASSWORD}, format="json"
        )
        self.assertEqual(login.status_code, 200)

    def test_primary_email_is_required_and_unique(self):
        self.as_user(self.boss)
        url = f"/api/manage/users/{self.dev.pk}/"
        self.assertEqual(self.client.patch(url, {"email": ""}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"email": "Learner@yeticode.com"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"secondary_email": "dev@yeticode.com"}, format="json").status_code, 400)
        self.dev.refresh_from_db()
        self.assertEqual((self.dev.email, self.dev.secondary_email), ("dev@yeticode.com", ""))

    def test_unit_admin_edits_emails_in_own_unit_only(self):
        self.as_user(self.web_admin)
        response = self.client.patch(
            f"/api/manage/users/{self.dev.pk}/",
            {"email": "webdev@yeticode.com", "secondary_email": "webdev@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        response = self.client.patch(
            f"/api/manage/users/{self.student.pk}/", {"email": "hijack@yeticode.com"}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "learner@yeticode.com")

    def test_unit_admin_cannot_change_own_primary_email(self):
        self.as_user(self.web_admin)
        url = f"/api/manage/users/{self.web_admin.pk}/"
        self.assertEqual(self.client.patch(url, {"email": "me@yeticode.com"}, format="json").status_code, 400)
        self.assertEqual(
            self.client.patch(url, {"secondary_email": "lead@example.com"}, format="json").status_code, 200
        )


class BrandingTests(UploadTestCase):
    def test_branding_is_public(self):
        response = self.client.get("/api/branding/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Yeticode Innovations")
        self.assertIsNone(response.json()["logo"])
        self.assertNotIn("phone", response.json())

    def test_super_admin_updates_details_and_logo(self):
        self.as_user(self.boss)
        response = self.client.patch(
            "/api/manage/company/",
            {"name": "Yeticode Pvt. Ltd.", "phone": "+977 1 5550000", "logo": image_file("logo.png")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())
        company = CompanySettings.load()
        self.assertEqual(company.name, "Yeticode Pvt. Ltd.")
        self.assertTrue(company.logo.name.startswith("branding/"))
        public = self.client.get("/api/branding/").json()
        self.assertEqual(public["logo"], company.logo.url)

        self.client.patch("/api/manage/company/", {"logo": None}, format="json")
        self.assertFalse(CompanySettings.load().logo)
        self.assertEqual(CompanySettings.objects.count(), 1)

    def test_logo_rejects_svg(self):
        self.as_user(self.boss)
        svg = SimpleUploadedFile("logo.svg", b"<svg onload='alert(1)'/>", content_type="image/svg+xml")
        response = self.client.patch("/api/manage/company/", {"logo": svg}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_only_super_admin_changes_branding(self):
        head_hr = User.objects.create_user(username="chief", password=PASSWORD, role=Role.objects.get(code="head_hr"))
        for user in [self.web_admin, self.dev, head_hr]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/manage/company/").status_code, 403)
            response = self.client.patch("/api/manage/company/", {"name": "Hacked"}, format="json")
            self.assertEqual(response.status_code, 403)
        self.assertEqual(CompanySettings.load().name, "Yeticode Innovations")
