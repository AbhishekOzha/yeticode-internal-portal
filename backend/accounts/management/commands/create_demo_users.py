from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Development only: create one demo account per role, named after the role code."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-pass-123")

    def handle(self, *args, password, **options):
        if not settings.DEBUG:
            raise CommandError("Demo users can only be created with DEBUG=TRUE.")
        for role in Role.objects.select_related("unit"):
            user, created = User.objects.get_or_create(
                username=role.code,
                defaults={"role": role, "first_name": role.name, "last_name": "(demo)"},
            )
            if created:
                user.set_password(password)
                user.save()
            self.stdout.write(f"{'created' if created else 'exists '}  {role.code:40} {role.unit or 'All units'}")
        self.stdout.write(self.style.SUCCESS(f"Demo password: {password}"))
