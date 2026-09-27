"""Pay for the Academic Content Writing unit's staff.

Each person can have a monthly salary and, month by month, any number of
extras: word-count tasks, extra hours, a performance bonus or an effort bonus.
Every field is optional. Word and hour extras are priced by a rate such as
"6,000 words = NPR 1,000", so 3,000 words earns NPR 500.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

PAYROLL_UNIT = "content"

DEFAULT_WORDS_PER_RATE = 6000
DEFAULT_HOURS_PER_RATE = Decimal("8")
DEFAULT_RATE_AMOUNT = Decimal("1000")
MAX_HOURS_PER_DAY = Decimal("24")


def extra_amount(quantity, per_quantity, per_amount):
    """Pay for `quantity` at "per_quantity = per_amount", rounded to the paisa."""
    return (Decimal(quantity) * Decimal(per_amount) / Decimal(per_quantity)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


class StaffPay(models.Model):
    """A staff member's pay setup: salary and the rates their extras use by default."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="pay"
    )
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    words_per_rate = models.PositiveIntegerField(
        default=DEFAULT_WORDS_PER_RATE, help_text="Words that earn one rate amount, e.g. 6000."
    )
    words_rate_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=DEFAULT_RATE_AMOUNT, help_text="NPR paid per that many words."
    )
    hours_per_rate = models.DecimalField(
        max_digits=6, decimal_places=2, default=DEFAULT_HOURS_PER_RATE, help_text="Hours that earn one rate amount, e.g. 8."
    )
    hours_rate_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=DEFAULT_RATE_AMOUNT, help_text="NPR paid per that many hours."
    )
    daily_extra = models.BooleanField(
        default=False, help_text="This person earns extras day by day, so each extra is dated."
    )
    note = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "staff pay"
        verbose_name_plural = "staff pay"

    def __str__(self):
        return f"Pay for {self.user}"


class PayExtra(models.Model):
    """One extra payment for a month, optionally for a particular day."""

    class Kind(models.TextChoices):
        WORDS = "words", "Extra task (words)"
        HOURS = "hours", "Extra task (hours)"
        PERFORMANCE = "performance", "Performance"
        EFFORT = "effort", "Effort"

    MEASURED = {Kind.WORDS, Kind.HOURS}

    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pay_extras")
    month = models.DateField(help_text="The first day of the month this is paid in.")
    date = models.DateField(null=True, blank=True, help_text="The day the work was done, for daily extras.")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text="Words written or hours worked."
    )
    per_quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    per_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["month", "date", "created_at"]
        indexes = [models.Index(fields=["month", "staff"])]
        constraints = [
            # The daily log keeps one hours and one words entry per person per day.
            models.UniqueConstraint(
                fields=["staff", "date", "kind"],
                condition=models.Q(date__isnull=False, kind__in=["words", "hours"]),
                name="one_measured_extra_per_day",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.staff}: NPR {self.amount}"
