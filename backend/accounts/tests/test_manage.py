from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User

PASSWORD = "Str0ng-pass-123"


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


class ManageUsersTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        self.web_admin = User.objects.create_user(
            username="web_admin", password=PASSWORD, role=role("web", "team_lead")
        )
        self.dev = User.objects.create_user(
            username="dev", password=PASSWORD, role=role("web", "web_developer")
        )
        self.student = User.objects.create_user(
            username="learner", password=PASSWORD, role=role("training", "student")
        )

    def as_user(self, user):
        self.client.force_authenticate(user)

    def test_regular_roles_cannot_manage_users(self):
        for user in [self.dev, self.student]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/manage/users/").status_code, 403)
            self.assertEqual(self.client.get("/api/manage/roles/").status_code, 403)

    def test_only_senior_roles_manage_users(self):
        managers = set(
            Role.objects.filter(permissions__codename="manage_unit_users")
            .values_list("unit__code", "code")
        )
        self.assertEqual(
            managers,
            {("web", "team_lead"), ("training", "training_manager"), ("content", "production_manager")},
        )
        self.assertFalse(Role.objects.filter(code="unit_admin").exists())

    def test_head_hr_cannot_manage_users(self):
        head_hr = User.objects.create_user(
            username="chief", password=PASSWORD, role=Role.objects.get(code="head_hr")
        )
        self.as_user(head_hr)
        self.assertEqual(self.client.get("/api/manage/users/").status_code, 403)

    def test_super_admin_sees_and_creates_users_in_any_unit(self):
        self.as_user(self.boss)
        usernames = {u["username"] for u in self.client.get("/api/manage/users/").json()}
        self.assertEqual(usernames, {"boss", "web_admin", "dev", "learner"})
        response = self.client.post(
            "/api/manage/users/",
            {"username": "writer", "password": PASSWORD, "role": role("content", "content_writer").pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        writer = User.objects.get(username="writer")
        self.assertEqual(writer.unit.code, "content")
        self.assertTrue(writer.check_password(PASSWORD))

    def test_super_admin_can_create_head_hr_and_super_admins(self):
        self.as_user(self.boss)
        r1 = self.client.post(
            "/api/manage/users/",
            {"username": "chief", "password": PASSWORD, "role": Role.objects.get(code="head_hr").pk},
            format="json",
        )
        r2 = self.client.post(
            "/api/manage/users/",
            {"username": "boss2", "password": PASSWORD, "is_super_admin": True,
             "role": role("web", "team_lead").pk},
            format="json",
        )
        self.assertEqual((r1.status_code, r2.status_code), (201, 201))
        boss2 = User.objects.get(username="boss2")
        self.assertTrue(boss2.is_superuser)
        self.assertIsNone(boss2.role)

    def test_unit_admin_only_sees_own_unit(self):
        self.as_user(self.web_admin)
        usernames = {u["username"] for u in self.client.get("/api/manage/users/").json()}
        self.assertEqual(usernames, {"web_admin", "dev"})
        self.assertEqual(self.client.get(f"/api/manage/users/{self.student.pk}/").status_code, 404)
        self.assertEqual(
            self.client.patch(f"/api/manage/users/{self.student.pk}/", {"is_active": False}).status_code,
            404,
        )
        roles = {(r["unit"], r["code"]) for r in self.client.get("/api/manage/roles/").json()}
        self.assertTrue(roles)
        self.assertEqual({unit for unit, _ in roles}, {"Web App Development"})

    def test_unit_admin_creates_users_only_with_own_unit_roles(self):
        self.as_user(self.web_admin)
        ok = self.client.post(
            "/api/manage/users/",
            {"username": "junior", "password": PASSWORD, "role": role("web", "junior_web_developer").pk},
            format="json",
        )
        self.assertEqual(ok.status_code, 201, ok.json())
        for bad_role in [role("training", "student"), Role.objects.get(code="head_hr")]:
            bad = self.client.post(
                "/api/manage/users/",
                {"username": f"x{bad_role.pk}", "password": PASSWORD, "role": bad_role.pk},
                format="json",
            )
            self.assertEqual(bad.status_code, 400)
        sneaky = self.client.post(
            "/api/manage/users/",
            {"username": "sneaky", "password": PASSWORD, "is_super_admin": True},
            format="json",
        )
        self.assertEqual(sneaky.status_code, 400)
        self.assertFalse(User.objects.filter(username__in=["sneaky"]).exists())

    def test_unit_admin_cannot_move_user_to_other_unit(self):
        self.as_user(self.web_admin)
        response = self.client.patch(
            f"/api/manage/users/{self.dev.pk}/", {"role": role("content", "hr").pk}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.role.code, "web_developer")

    def test_deactivate_and_reset_password(self):
        self.as_user(self.web_admin)
        self.client.patch(f"/api/manage/users/{self.dev.pk}/", {"password": "An0ther-pass-456"}, format="json")
        self.client.patch(f"/api/manage/users/{self.dev.pk}/", {"is_active": False}, format="json")
        self.dev.refresh_from_db()
        self.assertTrue(self.dev.check_password("An0ther-pass-456"))
        self.assertFalse(self.dev.is_active)

    def test_cannot_lock_yourself_out(self):
        self.as_user(self.web_admin)
        r = self.client.patch(f"/api/manage/users/{self.web_admin.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 400)
        self.as_user(self.boss)
        r = self.client.patch(f"/api/manage/users/{self.boss.pk}/", {"is_super_admin": False,
                              "role": role("web", "team_lead").pk}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_weak_passwords_are_rejected(self):
        self.as_user(self.boss)
        r = self.client.post(
            "/api/manage/users/",
            {"username": "weak", "password": "123", "role": role("web", "web_developer").pk},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.json())

    def test_users_cannot_be_deleted(self):
        self.as_user(self.boss)
        self.assertEqual(self.client.delete(f"/api/manage/users/{self.dev.pk}/").status_code, 405)


class ManageRolesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        self.web_admin = User.objects.create_user(
            username="web_admin", password=PASSWORD, role=role("web", "team_lead")
        )

    def test_super_admin_edits_role_capabilities(self):
        self.client.force_authenticate(self.boss)
        student = role("training", "student")
        r = self.client.patch(
            f"/api/manage/roles/{student.pk}/",
            {"capabilities": ["view_courses"]},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.json())
        self.assertEqual(r.json()["capabilities"], ["view_courses"])

    def test_cross_unit_capability_refused_for_unit_role(self):
        self.client.force_authenticate(self.boss)
        hr = role("content", "hr")
        r = self.client.patch(
            f"/api/manage/roles/{hr.pk}/",
            {"capabilities": ["view_all_employee_records"]},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(hr.permissions.filter(codename="view_all_employee_records").exists())

    def test_unit_admin_cannot_edit_roles(self):
        self.client.force_authenticate(self.web_admin)
        r = self.client.patch(
            f"/api/manage/roles/{role('web', 'web_developer').pk}/",
            {"capabilities": ["manage_unit_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/manage/capabilities/").status_code, 403)
