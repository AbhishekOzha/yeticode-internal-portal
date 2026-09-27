from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.rbac import ROLES, UNITS
from accounts.models import Role, Unit, User


def make_user(role_code, username=None, password="s3cret-pass!", unit=None):
    roles = Role.objects.filter(code=role_code)
    if unit:
        roles = roles.filter(unit__code=unit)
    role = roles.get()
    return User.objects.create_user(username=username or role_code, password=password, role=role)


class SeedTests(TestCase):
    def test_all_units_and_roles_are_seeded(self):
        self.assertEqual(set(Unit.objects.values_list("code", flat=True)), set(UNITS))
        self.assertEqual(Role.objects.count(), len(ROLES))
        for unit_code, code, name, _, capabilities in ROLES:
            role = Role.objects.get(unit__code=unit_code, code=code) if unit_code else Role.objects.get(unit=None, code=code)
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

    def test_student_sees_unit_directory(self):
        self.assertTrue(make_user("student").has_perm("accounts.view_unit_directory"))

    def test_only_head_hr_has_company_wide_records(self):
        for role in Role.objects.exclude(code="head_hr"):
            self.assertFalse(
                role.permissions.filter(codename="view_all_employee_records").exists(), role
            )
        self.assertTrue(make_user("head_hr").has_perm("accounts.view_all_employee_records"))

    def test_unit_role_cannot_be_given_cross_unit_capability(self):
        hr = Role.objects.get(code="hr")
        perm = Permission.objects.get(codename="view_all_employee_records")
        with transaction.atomic(), self.assertRaises(ValidationError):
            hr.permissions.add(perm)
        self.assertFalse(hr.permissions.filter(pk=perm.pk).exists())

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

    def test_login_with_email(self):
        user = make_user("hr", username="hr_person")
        user.email = "Maya@Yeticode.com"
        user.save()
        self.assertEqual(self.login("maya@yeticode.com").status_code, 200)

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


    def test_head_hr_sees_everyone_across_units(self):
        make_user("head_hr", username="chief_hr")
        make_user("team_lead", username="lead")
        make_user("student", username="learner")
        make_user("hr", username="content_hr")
        User.objects.create_superuser(username="boss", password="x")
        body = self.login("chief_hr").json()
        self.assertIsNone(body["unit"])
        self.assertEqual(body["role"]["name"], "Head HR")
        rows = self.client.get(reverse("company-members")).json()
        units = {r["username"]: r["unit"] for r in rows}
        self.assertEqual(units["lead"], "Web App Development")
        self.assertEqual(units["learner"], "Training")
        self.assertEqual(units["content_hr"], "Academic Content Writing")
        self.assertNotIn("boss", units)

    def test_unit_roles_cannot_see_other_units(self):
        roles = Role.objects.exclude(unit=None).select_related("unit")
        for role in roles:
            make_user(role.code, username=f"{role.unit.code}_{role.code}", unit=role.unit.code)
        for role in roles:
            self.client.logout()
            self.login(f"{role.unit.code}_{role.code}")
            self.assertEqual(
                self.client.get(reverse("company-members")).status_code, 403, role.code
            )
            response = self.client.get(reverse("unit-members"))
            if response.status_code == 200:
                others = {
                    u.role.unit_id
                    for u in User.objects.filter(username__in=[m["username"] for m in response.json()])
                }
                self.assertEqual(others, {role.unit_id}, role.code)

    def test_head_hr_has_no_unit_directory(self):
        make_user("head_hr", username="chief_hr")
        self.login("chief_hr")
        self.assertEqual(self.client.get(reverse("unit-members")).status_code, 403)


class AdminSiteTests(TestCase):
    def test_head_hr_cannot_open_admin(self):
        make_user("head_hr", username="chief_hr", password="pw-12345!")
        self.client.login(username="chief_hr", password="pw-12345!")
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 302)
        self.assertFalse(User.objects.get(username="chief_hr").is_staff)

    def test_admin_blocks_cross_unit_capability_on_unit_role(self):
        User.objects.create_superuser(username="boss", password="pw-12345!")
        self.client.login(username="boss", password="pw-12345!")
        hr = Role.objects.get(code="hr")
        perm = Permission.objects.get(codename="view_all_employee_records")
        response = self.client.post(
            f"/admin/accounts/role/{hr.pk}/change/",
            {"unit": hr.unit_id, "code": hr.code, "name": hr.name, "rank": hr.rank,
             "permissions": [perm.pk]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only company-wide roles")
        self.assertFalse(hr.permissions.filter(pk=perm.pk).exists())

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
