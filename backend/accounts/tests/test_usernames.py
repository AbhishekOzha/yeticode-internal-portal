from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CompanySettings, Role, User
from accounts.usernames import slugify_username, unique_username

PASSWORD = "Str0ng-pass-123"


class UsernameTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        company = CompanySettings.load()
        company.domain = "corecontent.com"
        company.save()
        self.boss = User.objects.create_superuser(username="boss", email="boss@example.com", password=PASSWORD)
        self.writer_role = Role.objects.get(unit__code="content", code="content_writer")

    def create(self, **data):
        self.client.force_authenticate(self.boss)
        payload = {
            "first_name": "Abhishek", "last_name": "Ojha", "email": "abhishek@gmail.com",
            "password": PASSWORD, "role": str(self.writer_role.pk), **data,
        }
        return self.client.post("/api/manage/users/", payload, format="json")

    def test_username_is_the_name_part_and_login_adds_the_domain(self):
        response = self.create(username="AbhishekOjha")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["username"], "abhishekojha")
        self.assertEqual(response.json()["login"], "abhishekojha@corecontent.com")
        self.assertEqual(User.objects.get(email="abhishek@gmail.com").username, "abhishekojha")

    def test_username_rules(self):
        for bad in ["abhishekojha@corecontent.com", "a", "has space", "-start", "end.", "x" * 31, "émile"]:
            response = self.create(username=bad, email=f"{abs(hash(bad))}@x.com")
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn("username", response.json())
        self.create(username="abhishekojha")
        taken = self.create(username="AbhishekOjha", email="other@x.com")
        self.assertEqual(taken.status_code, 400)
        self.assertIn("already has this username", str(taken.json()))

    def test_username_is_suggested_when_left_empty(self):
        self.assertEqual(self.create().json()["username"], "abhishekojha")
        self.assertEqual(self.create(email="twin@x.com").json()["username"], "abhishekojha2")

    def test_sign_in_with_username_full_username_or_email(self):
        self.create(username="abhishekojha")
        for typed in ["abhishekojha", "AbhishekOjha", "abhishekojha@corecontent.com", "abhishek@gmail.com"]:
            client = APIClient()
            response = client.post("/api/auth/login/", {"username": typed, "password": PASSWORD}, format="json")
            self.assertEqual(response.status_code, 200, typed)
            self.assertEqual(response.json()["login"], "abhishekojha@corecontent.com")
        # Another domain isn't ours: it's treated as an email and doesn't match.
        wrong = APIClient().post("/api/auth/login/", {"username": "abhishekojha@other.com", "password": PASSWORD}, format="json")
        self.assertEqual(wrong.status_code, 400)

    def test_domain_is_set_in_company_settings(self):
        self.client.force_authenticate(self.boss)
        response = self.client.patch("/api/manage/company/", {"domain": " @CoreContent.com "}, format="json")
        self.assertEqual(response.json()["domain"], "corecontent.com")
        self.assertEqual(self.client.patch("/api/manage/company/", {"domain": "https://x"}, format="json").status_code, 400)
        self.assertEqual(APIClient().get("/api/branding/").json()["domain"], "corecontent.com")

    def test_helpers(self):
        self.assertEqual(slugify_username("Abhishek Ojha"), "abhishekojha")
        self.assertEqual(slugify_username("paulozajr@gmail.com"), "paulozajr")
        self.assertEqual(slugify_username("abhishekojha.work@gmail.com"), "abhishekojha.work")
        self.assertEqual(unique_username("abc", {"abc", "abc2"}), "abc3")


    def test_email_sign_in_ignores_deactivated_accounts_with_the_same_email(self):
        self.create(username="abhishekojha")
        User.objects.create_user(username="oldcopy", email="abhishek@gmail.com", password=PASSWORD, is_active=False,
                                 role=self.writer_role)
        response = APIClient().post("/api/auth/login/", {"username": "abhishek@gmail.com", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "abhishekojha")


class SessionEndpointTests(TestCase):
    def test_signed_out_is_a_normal_answer_and_sets_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.get("/api/auth/session/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["user"])
        self.assertIn("csrftoken", response.cookies)

    def test_signed_in_returns_the_user(self):
        role = Role.objects.get(unit__code="content", code="content_writer")
        user = User.objects.create_user(username="asha", password=PASSWORD, role=role)
        client = APIClient()
        client.force_authenticate(user)
        data = client.get("/api/auth/session/").json()["user"]
        self.assertEqual(data["username"], "asha")
        payroll = [d for d in data["dashboard"] if d["key"] == "write_content"]
        self.assertEqual(payroll[0]["unit"], "Academic Content Writing")

    def test_super_admin_payroll_card_names_the_unit(self):
        boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        client = APIClient()
        client.force_authenticate(boss)
        cards = {d["key"]: d for d in client.get("/api/auth/session/").json()["user"]["dashboard"]}
        self.assertEqual(cards["manage_payroll"]["unit"], "Academic Content Writing")
        self.assertIsNone(cards["manage_users"]["unit"])
