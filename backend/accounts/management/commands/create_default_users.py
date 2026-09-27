import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import CompanySettings, Role, User
from accounts.usernames import slugify_username
from accounts.rbac import UNIT_ADMINS, UNITS

logger = logging.getLogger(__name__)

DEV_PASSWORD = "yeticode@123"
LEGACY_SYSTEM_USERNAME = "superadmin"


class Command(BaseCommand):
    """Create the Super Admin and one admin account per unit if they are missing.

    Usernames are short (admin, webdev.lead, ...) and emails use DEFAULT_EMAIL_DOMAIN.
    Accounts made by earlier versions of this command (superadmin, web_admin, or
    email-style usernames) are renamed in place, keeping their passwords.
    """

    help = "Create the default Super Admin and unit admin accounts"

    def handle(self, *args, **options):
        system_password = self.password(settings.SYSTEM_USER_PASSWORD, "SYSTEM_USER_PASSWORD")
        unit_password = self.password(settings.UNIT_ADMIN_PASSWORD, "UNIT_ADMIN_PASSWORD")
        domain = settings.DEFAULT_EMAIL_DOMAIN

        company = CompanySettings.load()
        if not company.domain:
            company.domain = domain.lower()
            company.save()

        # SYSTEM_USERNAME may be an older-style email; the username is just its name part.
        system_username = slugify_username(settings.SYSTEM_USERNAME) or "admin"
        system_email = f"{system_username}@{domain}"
        self.ensure(
            username=system_username,
            email=system_email,
            legacy_usernames=[LEGACY_SYSTEM_USERNAME, settings.SYSTEM_USERNAME, system_email],
            first_name="System Administrator",
            label="Super Admin",
            create=lambda: User.objects.create_superuser(
                username=system_username, email=system_email, password=system_password,
                first_name="System Administrator",
            ),
        )

        for unit_code, (local_part, role_code, display_name, legacy) in UNIT_ADMINS.items():
            role = Role.objects.filter(unit__code=unit_code, code=role_code).first()
            if role is None:
                raise CommandError(f"Role {role_code} not found. Run `python manage.py migrate` first.")
            unit_email = f"{local_part}@{domain}"
            self.ensure(
                username=local_part,
                email=unit_email,
                legacy_usernames=[legacy, unit_email],
                first_name=display_name,
                label=f"{role.name}, {UNITS[unit_code]}",
                create=lambda local_part=local_part, unit_email=unit_email, role=role, display_name=display_name: (
                    User.objects.create_user(
                        username=local_part, email=unit_email, password=unit_password,
                        role=role, first_name=display_name,
                    )
                ),
            )

    def ensure(self, username, email, legacy_usernames, first_name, label, create):
        if User.objects.filter(username__iexact=username).exists():
            self.say(f"Already exists: {username} ({label})")
            return
        legacy = User.objects.filter(username__in=[u for u in legacy_usernames if u]).first()
        if legacy is not None:
            old = legacy.username
            legacy.username = username
            legacy.email = email
            legacy.first_name = first_name
            legacy.last_name = ""
            legacy.save()
            logger.info("Renamed %s to %s", old, username)
            self.say(f"Renamed {old} to {username} ({label})", success=True)
            return
        create()
        logger.info("Created %s (%s)", username, label)
        self.say(f"Created {username} <{email}> ({label})", success=True)

    def password(self, configured, setting_name):
        if configured:
            return configured
        if settings.DEBUG:
            return DEV_PASSWORD
        raise CommandError(f"Set {setting_name} in the environment or backend/.env.")

    def say(self, message, success=False):
        self.stdout.write(self.style.SUCCESS(message) if success else message)
