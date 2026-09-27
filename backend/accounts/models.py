from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models

from .rbac import CAPABILITIES


class Unit(models.Model):
    """A branch of the company, e.g. Web App Development."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(models.Model):
    """A job role that exists within exactly one unit."""

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="roles")
    code = models.SlugField(max_length=60)
    name = models.CharField(max_length=100)
    rank = models.PositiveSmallIntegerField(
        default=1, help_text="Seniority within the unit; 1 is the most junior."
    )
    permissions = models.ManyToManyField(
        "auth.Permission",
        blank=True,
        related_name="roles",
        help_text="What people with this role are allowed to do.",
    )

    class Meta:
        ordering = ["unit__name", "rank", "name"]
        constraints = [
            models.UniqueConstraint(fields=["unit", "code"], name="unique_role_code_per_unit"),
            models.UniqueConstraint(fields=["unit", "name"], name="unique_role_name_per_unit"),
        ]

    def __str__(self):
        return f"{self.name} ({self.unit.name})"


class Capability(models.Model):
    """Holds the app's custom permissions; it has no table of its own."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [(code, label) for code, (label, _) in CAPABILITIES.items()]


class User(AbstractUser):
    """A staff member or student. Accounts are only ever created by a Super Admin.

    Every user except a Super Admin has exactly one role, and the role
    determines the user's unit, so a user can never be in one unit with a
    role from another.
    """

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        help_text="Required for everyone except Super Admins. The role decides the unit.",
    )

    objects = UserManager()

    class Meta:
        ordering = ["username"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_superuser=True, role__isnull=True)
                    | models.Q(is_superuser=False, role__isnull=False)
                ),
                name="user_is_super_admin_xor_has_role",
            ),
        ]

    @property
    def unit(self):
        return self.role.unit if self.role_id else None

    @property
    def is_super_admin(self):
        return self.is_superuser

    def clean(self):
        super().clean()
        if self.is_superuser and self.role_id:
            raise ValidationError({"role": "Super Admins work across all units and have no role."})
        if not self.is_superuser and not self.role_id:
            raise ValidationError({"role": "Every user except a Super Admin needs a role."})

    def save(self, *args, **kwargs):
        # Only Super Admins may sign in to the Django admin.
        self.is_staff = self.is_superuser
        super().save(*args, **kwargs)
