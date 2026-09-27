from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Users, units and roles"

    def ready(self):
        from . import signals  # noqa: F401
        from .seed import seed_units_and_roles

        post_migrate.connect(seed_units_and_roles, sender=self)
