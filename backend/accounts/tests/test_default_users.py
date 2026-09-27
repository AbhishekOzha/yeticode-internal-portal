from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import Role, User

EXPECTED = {
    "webdev.lead@yeticode.com": ("web", "team_lead", "Web Development Lead"),
    "training.manager@yeticode.com": ("training", "training_manager", "Training Manager"),
    "production.manager@yeticode.com": ("content", "production_manager", "Production Manager"),
}


@override_settings(DEFAULT_EMAIL_DOMAIN="yeticode.com", SYSTEM_USERNAME="admin@yeticode.com")
class CreateDefaultUsersTests(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("create_default_users", stdout=out)
        return out.getvalue()

    @override_settings(SYSTEM_USER_PASSWORD="Boss-pw-1", UNIT_ADMIN_PASSWORD="Unit-pw-1")
    def test_creates_super_admin_and_one_admin_per_unit(self):
        self.run_command()
        boss = User.objects.get(username="admin@yeticode.com")
        self.assertTrue(boss.is_superuser)
        self.assertEqual(boss.get_full_name(), "System Administrator")
        self.assertTrue(boss.check_password("Boss-pw-1"))
        for email, (unit, role, name) in EXPECTED.items():
            user = User.objects.get(username=email)
            self.assertEqual((user.unit.code, user.role.code), (unit, role))
            self.assertEqual((user.email, user.get_full_name()), (email, name))
            self.assertFalse(user.is_staff)
            self.assertTrue(user.check_password("Unit-pw-1"))

    @override_settings(SYSTEM_USER_PASSWORD="Boss-pw-1", UNIT_ADMIN_PASSWORD="Unit-pw-1")
    def test_running_twice_changes_nothing(self):
        self.run_command()
        output = self.run_command()
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(output.count("Already exists"), 4)

    @override_settings(SYSTEM_USER_PASSWORD="Boss-pw-1", UNIT_ADMIN_PASSWORD="Unit-pw-1")
    def test_renames_accounts_from_older_versions(self):
        User.objects.create_superuser(username="superadmin", password="Old-pw-1")
        User.objects.create_user(
            username="web_admin", password="Old-pw-1",
            role=Role.objects.get(unit__code="web", code="team_lead"),
        )
        self.run_command()
        self.assertFalse(User.objects.filter(username__in=["superadmin", "web_admin"]).exists())
        lead = User.objects.get(username="webdev.lead@yeticode.com")
        self.assertTrue(lead.check_password("Old-pw-1"))  # passwords are kept
        self.assertEqual(User.objects.count(), 4)

    @override_settings(DEBUG=False, SYSTEM_USER_PASSWORD="", UNIT_ADMIN_PASSWORD="")
    def test_production_requires_passwords(self):
        with self.assertRaises(CommandError):
            self.run_command()
        self.assertFalse(User.objects.exists())
