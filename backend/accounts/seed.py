from django.contrib.auth.management import create_permissions

from .rbac import ROLES, UNITS


def seed_units_and_roles(app_config, using="default", apps=None, verbosity=1, **kwargs):
    """Create the company's units and roles if they don't exist yet.

    Runs after every migrate. A role's default permissions are applied only
    when the role is first created, so changes made in the admin are kept.
    """
    # Make sure the capability permissions exist before assigning them.
    create_permissions(app_config, verbosity=0, using=using, apps=apps)

    Unit = apps.get_model("accounts", "Unit")
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("auth", "Permission")

    units = {}
    for code, name in UNITS.items():
        units[code], _ = Unit.objects.using(using).get_or_create(code=code, defaults={"name": name})

    for unit_code, code, name, rank, capabilities in ROLES:
        role, created = Role.objects.using(using).get_or_create(
            unit=units[unit_code], code=code, defaults={"name": name, "rank": rank}
        )
        if created:
            perms = Permission.objects.using(using).filter(
                content_type__app_label="accounts", codename__in=capabilities
            )
            role.permissions.set(perms)
            if verbosity >= 2:
                print(f"  Created role {name} with {len(capabilities)} capabilities")
