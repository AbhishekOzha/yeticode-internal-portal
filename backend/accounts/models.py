import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models

from .rbac import CAPABILITIES, CROSS_UNIT_CAPABILITIES
from .uploads import avatar_upload_to, logo_upload_to, validate_image


class Unit(models.Model):
    """A branch of the company, e.g. Web App Development."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(models.Model):
    """A job role within one unit, or a company-wide role when unit is empty.

    Company-wide roles (such as Head HR) are the only roles that may hold
    capabilities reaching across units.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="roles",
        help_text="Leave empty only for a company-wide role such as Head HR.",
    )
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
            models.UniqueConstraint(
                fields=["code"], condition=models.Q(unit__isnull=True),
                name="unique_company_wide_role_code",
            ),
            models.UniqueConstraint(
                fields=["name"], condition=models.Q(unit__isnull=True),
                name="unique_company_wide_role_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.unit.name if self.unit else 'All units'})"

    @property
    def is_company_wide(self):
        return self.unit_id is None


class Capability(models.Model):
    """Holds the app's custom permissions; it has no table of its own."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [(code, label) for code, (label, _) in CAPABILITIES.items()]


def check_role_capabilities(unit, permissions):
    """Raise if a unit-scoped role would be given a cross-unit capability."""
    if unit is None:
        return
    blocked = sorted(
        perm.name for perm in permissions
        if perm.content_type.app_label == "accounts" and perm.codename in CROSS_UNIT_CAPABILITIES
    )
    if blocked:
        raise ValidationError(
            f"Only company-wide roles can have: {', '.join(blocked)}. "
            "Units are kept isolated from each other."
        )


class User(AbstractUser):
    """A staff member or student. Accounts are only ever created by a Super Admin.

    Every user except a Super Admin has exactly one role, and the role
    determines the user's unit, so a user can never be in one unit with a
    role from another. Users with a company-wide role have no unit.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        help_text="Required for everyone except Super Admins. The role decides the unit.",
    )
    secondary_email = models.EmailField(
        blank=True, help_text="An optional second address. People sign in with their primary email."
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_to, blank=True, validators=[validate_image],
        help_text="Profile photo: PNG, JPG or WebP, up to 2 MB.",
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


def email_in_use(email, exclude=None):
    """True when another account already uses this address as its primary or secondary email."""
    others = User.objects.all()
    if exclude is not None and exclude.pk:
        others = others.exclude(pk=exclude.pk)
    return others.filter(
        models.Q(email__iexact=email) | models.Q(secondary_email__iexact=email)
    ).exists()


# The one and only company settings row.
COMPANY_SETTINGS_ID = uuid.UUID(int=1)


class CompanySettings(models.Model):
    """The company's name, contact details and logo. There is only ever one row."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, default="Yeticode Innovations")
    tagline = models.CharField(max_length=120, blank=True, default="Staff portal")
    email = models.EmailField("contact email", blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(
        upload_to=logo_upload_to, blank=True, validators=[validate_image],
        help_text="PNG, JPG or WebP, up to 2 MB. A square image works best.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "company settings"
        verbose_name_plural = "company settings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = COMPANY_SETTINGS_ID
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=COMPANY_SETTINGS_ID)
        return settings
