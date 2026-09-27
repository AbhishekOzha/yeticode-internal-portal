from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User

# Sample people for local development, one per role: (unit, role) -> (first, last).
DEMO_PEOPLE = {
    ("web", "junior_web_developer"): ("Aarav", "Shrestha"),
    ("web", "web_developer"): ("Sneha", "Gurung"),
    ("web", "senior_web_developer"): ("Rohan", "Karki"),
    ("web", "team_lead"): ("Priya", "Adhikari"),
    ("training", "student"): ("Kiran", "Thapa"),
    ("training", "instructor"): ("Anisha", "Rai"),
    ("training", "front_desk_coordinator"): ("Sujan", "Maharjan"),
    ("training", "training_manager"): ("Meera", "Joshi"),
    ("content", "content_writer"): ("Nabin", "Poudel"),
    ("content", "content_writer_research_specialist"): ("Asmita", "Bhandari"),
    ("content", "production_manager"): ("Bikash", "Tamang"),
    ("content", "sales_executive"): ("Sita", "Lama"),
    ("content", "sales_manager"): ("Rajesh", "Koirala"),
    ("content", "hr"): ("Pooja", "Basnet"),
    (None, "head_hr"): ("Sarita", "Khadka"),
}


class Command(BaseCommand):
    help = "Development only: create one sample person per role, signing in with their email."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-pass-123")

    def handle(self, *args, password, **options):
        if not settings.DEBUG:
            raise CommandError("Demo users can only be created with DEBUG=TRUE.")
        domain = settings.DEFAULT_EMAIL_DOMAIN
        for role in Role.objects.select_related("unit"):
            unit_code = role.unit.code if role.unit else None
            first, last = DEMO_PEOPLE.get((unit_code, role.code), (role.name, "Demo"))
            email = f"{first}.{last}@{domain}".lower()
            user, created = User.objects.get_or_create(
                username=email,
                defaults={"role": role, "email": email, "first_name": first, "last_name": last},
            )
            if created:
                user.set_password(password)
                user.save()
            status = "created" if created else "exists "
            self.stdout.write(f"{status}  {email:40} {role.name} ({role.unit or 'All units'})")
        self.stdout.write(self.style.SUCCESS(f"Demo password: {password}"))
