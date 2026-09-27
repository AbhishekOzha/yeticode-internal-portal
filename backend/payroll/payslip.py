"""The monthly payslip for someone in Academic Content Writing.

It follows the company's salary sheet:

    Per day income    = monthly salary / 30, rounded up to the rupee   (25,000 -> 834)
    Total days        = 30 for every month (the sheet's basis, whatever the calendar says)
    Leave             = approved unpaid leave days in the month (half days count 0.5);
                        all leave types are unpaid for now (team.models.PAID_LEAVE_KINDS)
    Working days      = 30 - leave
    Salary amount     = working days x per day income                   (28 x 834 = 23,352),
                        never more than the monthly salary itself
    Deducted leave    = leave x per day income                          (2 x 834 = 1,668)
    Credits           = extra work in rate units, e.g. 6,000 words or 8 hours = 1 credit
    Credit amount     = what those extras pay                           (8.33 cr ~ 8,333)
    Gross amount      = salary amount + credit amount + performance + effort extras
"""

import datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from team.models import PAID_LEAVE_KINDS, LeaveRequest

from .models import PayExtra

DAYS_BASIS = 30
ZERO = Decimal("0")


def month_end(month):
    next_month = (month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return next_month - datetime.timedelta(days=1)


def leave_days(user, month):
    """Approved unpaid leave inside the month; leave that runs across months only counts its days in this one."""
    last = month_end(month)
    total = ZERO
    approved = LeaveRequest.objects.filter(
        user=user, status=LeaveRequest.Status.APPROVED, start_date__lte=last, end_date__gte=month
    ).exclude(kind__in=PAID_LEAVE_KINDS)
    for leave in approved:
        if leave.half_day:
            total += Decimal("0.5")
        else:
            start, end = max(leave.start_date, month), min(leave.end_date, last)
            total += Decimal((end - start).days + 1)
    return min(total, Decimal(DAYS_BASIS))


def days(value):
    """27.5 -> "27.5", 30 -> "30" (normalize() alone would give "3E+1")."""
    return format(value.normalize(), "f")


def money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def payslip(user, pay, extras, month):
    """The payslip figures. `pay` is the StaffPay (possibly unsaved); `extras` are this month's PayExtra rows."""
    salary = pay.monthly_salary or ZERO
    per_day = (salary / DAYS_BASIS).quantize(Decimal("1"), rounding=ROUND_CEILING) if salary else ZERO
    leave = leave_days(user, month)
    working = Decimal(DAYS_BASIS) - leave
    salary_amount = min(per_day * working, salary)

    credits = ZERO
    credit_amount = ZERO
    other = {PayExtra.Kind.PERFORMANCE: ZERO, PayExtra.Kind.EFFORT: ZERO}
    for extra in extras:
        if extra.kind in PayExtra.MEASURED:
            credits += extra.quantity / extra.per_quantity
            credit_amount += extra.amount
        else:
            other[extra.kind] += extra.amount

    gross = salary_amount + credit_amount + other[PayExtra.Kind.PERFORMANCE] + other[PayExtra.Kind.EFFORT]
    return {
        "month": month.strftime("%Y-%m"),
        "monthly_salary": str(money(salary)),
        "per_day": str(money(per_day)),
        "total_days": DAYS_BASIS,
        "leave_days": days(leave),
        "working_days": days(working),
        "salary_amount": str(money(salary_amount)),
        "leave_deduction": str(money(per_day * leave)),
        "credits": str(credits.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "credit_amount": str(money(credit_amount)),
        "performance": str(money(other[PayExtra.Kind.PERFORMANCE])),
        "effort": str(money(other[PayExtra.Kind.EFFORT])),
        "gross": str(money(gross)),
    }
