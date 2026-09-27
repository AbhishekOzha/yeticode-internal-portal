import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User
from accounts.rbac import UNIT_ADMINS, UNITS

logger = logging.getLogger(__name__)

DEV_PASSWORD = "yeticode@123"
LEGACY_SYSTEM_USERNAME = "superadmin"


class Command(BaseCommand):
    """Create the Super Admin and one admin account per unit if they are missing.

    Accounts sign in with their email address. Accounts made by earlier
    versions of this command (superadmin, web_admin, ...) are renamed in place.
    """

    help = "Create the default Super Admin and unit admin accounts"

    def handle(self, *args, **options):
        system_password = self.password(settings.SYSTEM_USER_PASSWORD, "SYSTEM_USER_PASSWORD")
        unit_password = self.password(settings.UNIT_ADMIN_PASSWORD, "UNIT_ADMIN_PASSWORD")
        domain = settings.DEFAULT_EMAIL_DOMAIN

        email = settings.SYSTEM_USERNAME
        self.ensure(
            email=email,
            legacy_username=LEGACY_SYSTEM_USERNAME,
            first_name="System Administrator",
            label="Super Admin",
            create=lambda: User.objects.create_superuser(
                username=email, email=email, password=system_password,
                first_name="System Administrator",
            ),
        )

        for unit_code, (local_part, role_code, display_name, legacy) in UNIT_ADMINS.items():
            role = Role.objects.filter(unit__code=unit_code, code=role_code).first()
            if role is None:
                raise CommandError(f"Role {role_code} not found. Run `python manage.py migrate` first.")
            unit_email = f"{local_part}@{domain}"
            self.ensure(
                email=unit_email,
                legacy_username=legacy,
                first_name=display_name,
                label=f"{role.name}, {UNITS[unit_code]}",
                create=lambda unit_email=unit_email, role=role, display_name=display_name: (
                    User.objects.create_user(
                        username=unit_email, email=unit_email, password=unit_password,
                        role=role, first_name=display_name,
                    )
                ),
            )

    def ensure(self, email, legacy_username, first_name, label, create):
        if User.objects.filter(username__iexact=email).exists():
            self.say(f"Already exists: {email} ({label})")
            return
        legacy = User.objects.filter(username=legacy_username).first()
        if legacy is not None:
            legacy.username = email
            legacy.email = email
            legacy.first_name = first_name
            legacy.last_name = ""
            legacy.save()
            logger.info("Renamed %s to %s", legacy_username, email)
            self.say(f"Renamed {legacy_username} to {email} ({label})", success=True)
            return
        create()
        logger.info("Created %s (%s)", email, label)
        self.say(f"Created {email} ({label})", success=True)

    def password(self, configured, setting_name):
        if configured:
            return configured
        if settings.DEBUG:
            return DEV_PASSWORD
        raise CommandError(f"Set {setting_name} in the environment or backend/.env.")

    def say(self, message, success=False):
        self.stdout.write(self.style.SUCCESS(message) if success else message)
