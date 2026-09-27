from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User


class CreateDefaultUsersTests(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("create_default_users", stdout=out)
        return out.getvalue()

    @override_settings(SYSTEM_USERNAME="boss", SYSTEM_USER_PASSWORD="Boss-pw-1", UNIT_ADMIN_PASSWORD="Unit-pw-1")
    def test_creates_super_admin_and_one_admin_per_unit(self):
        self.run_command()
        boss = User.objects.get(username="boss")
        self.assertTrue(boss.is_superuser)
        self.assertTrue(boss.check_password("Boss-pw-1"))
        expected = {
            "web_admin": ("web", "team_lead"),
            "training_admin": ("training", "training_manager"),
            "content_admin": ("content", "production_manager"),
        }
        for username, (unit, role) in expected.items():
            user = User.objects.get(username=username)
            self.assertEqual((user.unit.code, user.role.code), (unit, role))
            self.assertFalse(user.is_staff)
            self.assertTrue(user.check_password("Unit-pw-1"))

    @override_settings(SYSTEM_USER_PASSWORD="Boss-pw-1", UNIT_ADMIN_PASSWORD="Unit-pw-1")
    def test_running_twice_changes_nothing(self):
        self.run_command()
        output = self.run_command()
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(output.count("Already exists"), 4)

    @override_settings(DEBUG=False, SYSTEM_USER_PASSWORD="", UNIT_ADMIN_PASSWORD="")
    def test_production_requires_passwords(self):
        with self.assertRaises(CommandError):
            self.run_command()
        self.assertFalse(User.objects.exists())
