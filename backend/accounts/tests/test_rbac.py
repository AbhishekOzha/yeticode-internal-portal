from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.rbac import ROLES, UNITS
from accounts.models import Role, Unit, User


def make_user(role_code, username=None, password="s3cret-pass!"):
    role = Role.objects.get(code=role_code)
    return User.objects.create_user(username=username or role_code, password=password, role=role)


class SeedTests(TestCase):
    def test_all_units_and_roles_are_seeded(self):
        self.assertEqual(set(Unit.objects.values_list("code", flat=True)), set(UNITS))
        self.assertEqual(Role.objects.count(), len(ROLES))
        for unit_code, code, name, _, capabilities in ROLES:
            role = Role.objects.get(unit__code=unit_code, code=code)
            self.assertEqual(role.name, name)
            self.assertEqual(
                set(role.permissions.values_list("codename", flat=True)), set(capabilities)
            )


class UserRoleRulesTests(TestCase):
    def test_unit_comes_from_role(self):
        user = make_user("instructor")
        self.assertEqual(user.unit.code, "training")

    def test_regular_user_needs_a_role(self):
        with self.assertRaises(ValidationError):
            User(username="nobody").full_clean()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user(username="nobody", password="x")

    def test_super_admin_has_no_role(self):
        admin = User.objects.create_superuser(username="boss", password="x")
        self.assertIsNone(admin.unit)
        admin.role = Role.objects.get(code="hr")
        with self.assertRaises(ValidationError):
            admin.full_clean()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            admin.save()

    def test_only_super_admins_are_staff(self):
        user = make_user("team_lead")
        user.is_staff = True
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertTrue(User.objects.create_superuser(username="boss", password="x").is_staff)


class PermissionTests(TestCase):
    def test_role_grants_its_capabilities_only(self):
        lead = make_user("team_lead")
        junior = make_user("junior_web_developer")
        self.assertTrue(lead.has_perm("accounts.assign_tasks"))
        self.assertFalse(junior.has_perm("accounts.assign_tasks"))
        self.assertTrue(junior.has_perm("accounts.work_on_tasks"))
        self.assertFalse(junior.has_perm("accounts.manage_leads"))

    def test_super_admin_has_everything(self):
        admin = User.objects.create_superuser(username="boss", password="x")
        self.assertTrue(admin.has_perm("accounts.manage_employee_records"))

    def test_inactive_user_has_nothing(self):
        user = make_user("hr")
        user.is_active = False
        user.save()
        self.assertFalse(user.has_perm("accounts.manage_employee_records"))


class ApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, username, password="s3cret-pass!"):
        return self.client.post(
            reverse("login"), {"username": username, "password": password}, format="json"
        )

    def test_there_is_no_signup_endpoint(self):
        for path in ["/api/auth/register/", "/api/auth/signup/", "/api/users/"]:
            self.assertEqual(self.client.post(path, {}).status_code, 404, path)

    def test_login_returns_role_dashboard(self):
        make_user("sales_manager", username="sita")
        response = self.login("sita")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["unit"]["name"], "Academic Content Writing")
        self.assertEqual(body["role"]["name"], "Sales Manager")
        self.assertIn("view_sales_reports", body["capabilities"])
        self.assertEqual(
            [w["key"] for w in body["dashboard"]], body["capabilities"]
        )

    def test_wrong_password_is_rejected(self):
        make_user("student", username="ram")
        self.assertEqual(self.login("ram", "wrong").status_code, 400)

    def test_me_requires_login(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 403)

    def test_unit_directory_is_scoped_to_own_unit(self):
        make_user("instructor", username="teacher")
        make_user("student", username="learner")
        make_user("hr", username="hr_person")
        self.login("teacher")
        usernames = {m["username"] for m in self.client.get(reverse("unit-members")).json()}
        self.assertEqual(usernames, {"teacher", "learner"})

    def test_unit_directory_needs_capability(self):
        make_user("student", username="learner")
        self.login("learner")
        self.assertEqual(self.client.get(reverse("unit-members")).status_code, 403)


class AdminSiteTests(TestCase):
    def test_only_super_admins_can_open_admin(self):
        make_user("team_lead", username="lead", password="pw-12345!")
        self.client.login(username="lead", password="pw-12345!")
        self.assertEqual(self.client.get("/admin/").status_code, 302)

        User.objects.create_superuser(username="boss", password="pw-12345!")
        self.client.login(username="boss", password="pw-12345!")
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_super_admin_creates_user_with_role(self):
        User.objects.create_superuser(username="boss", password="pw-12345!")
        self.client.login(username="boss", password="pw-12345!")
        for page in ["/admin/accounts/user/", "/admin/accounts/user/add/", "/admin/accounts/role/1/change/", "/admin/accounts/unit/"]:
            self.assertEqual(self.client.get(page).status_code, 200, page)
        role = Role.objects.get(code="web_developer")
        response = self.client.post(
            "/admin/accounts/user/add/",
            {
                "username": "hari",
                "first_name": "Hari",
                "last_name": "K",
                "email": "hari@example.com",
                "role": role.pk,
                "password1": "Very-strong-pw-1",
                "password2": "Very-strong-pw-1",
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        hari = User.objects.get(username="hari")
        self.assertEqual(hari.unit.code, "web")
        self.assertTrue(hari.check_password("Very-strong-pw-1"))

    def test_admin_rejects_regular_user_without_role(self):
        User.objects.create_superuser(username="boss", password="pw-12345!")
        self.client.login(username="boss", password="pw-12345!")
        response = self.client.post(
            "/admin/accounts/user/add/",
            {"username": "norole", "password1": "Very-strong-pw-1", "password2": "Very-strong-pw-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="norole").exists())
