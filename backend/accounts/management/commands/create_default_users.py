import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User
from accounts.rbac import UNIT_ADMINS, UNITS

logger = logging.getLogger(__name__)

DEV_PASSWORD = "yeticode@123"


class Command(BaseCommand):
    """Create the Super Admin and one admin account per unit if they are missing."""

    help = "Create the default Super Admin and unit admin accounts"

    def handle(self, *args, **options):
        system_password = self.password(settings.SYSTEM_USER_PASSWORD, "SYSTEM_USER_PASSWORD")
        unit_password = self.password(settings.UNIT_ADMIN_PASSWORD, "UNIT_ADMIN_PASSWORD")
        domain = settings.DEFAULT_EMAIL_DOMAIN

        username = settings.SYSTEM_USERNAME
        if User.objects.filter(username=username).exists():
            self.report(username, "Super Admin", created=False)
        else:
            User.objects.create_superuser(
                username=username,
                email=settings.SYSTEM_USER_EMAIL or f"{username}@{domain}",
                password=system_password,
                first_name="Super",
                last_name="Admin",
            )
            self.report(username, "Super Admin", created=True)

        for unit_code, (username, role_code) in UNIT_ADMINS.items():
            role = Role.objects.filter(unit__code=unit_code, code=role_code).first()
            if role is None:
                raise CommandError(f"Role {role_code} not found. Run `python manage.py migrate` first.")
            label = f"{role.name}, {UNITS[unit_code]}"
            if User.objects.filter(username=username).exists():
                self.report(username, label, created=False)
                continue
            User.objects.create_user(
                username=username,
                email=f"{username}@{domain}",
                password=unit_password,
                role=role,
                first_name=UNITS[unit_code],
                last_name="Admin",
            )
            self.report(username, label, created=True)

    def password(self, configured, setting_name):
        if configured:
            return configured
        if settings.DEBUG:
            return DEV_PASSWORD
        raise CommandError(f"Set {setting_name} in the environment or backend/.env.")

    def report(self, username, label, created):
        if created:
            logger.info("Created %s (%s)", username, label)
            self.stdout.write(self.style.SUCCESS(f"Created {username} ({label})"))
        else:
            logger.info("%s already exists", username)
            self.stdout.write(f"Already exists: {username} ({label})")
