"""Cheering writers on when they do extra work.

When extras are recorded for someone, they get a short notification (at most one a day):
  - the first time they cross EXTRA_GOAL_PERCENT of their monthly salary in extras, a goal message
    (e.g. 20% of NPR 20,000 = NPR 4,000), once a month;
  - otherwise "keep it up" when the extra work runs over two or more days in a row;
  - otherwise a congratulation for doing extra at all.
"""

import datetime
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from notifications.models import Notification, notify

from .models import PayExtra
from .payslip import money

DAILY_KINDS = (PayExtra.Kind.HOURS, PayExtra.Kind.WORDS)


def goal_percent():
    return Decimal(str(getattr(settings, "EXTRA_GOAL_PERCENT", 20)))


def nrs(value):
    return f"NPR {int(value):,}" if value == value.to_integral_value() else f"NPR {value:,.2f}"


def streak_days(extras):
    """How many days in a row, ending on the latest day with extra work."""
    days = sorted({e.date for e in extras if e.date and e.kind in DAILY_KINDS and e.quantity})
    if not days:
        return 0
    run = 1
    for earlier, later in zip(reversed(days[:-1]), reversed(days[1:])):
        if (later - earlier).days != 1:
            break
        run += 1
    return run


def cheer(staff, month):
    """Send the writer a message about this month's extras, if there is one to send. Returns it or None."""
    extras = list(PayExtra.objects.filter(staff=staff, month=month))
    total = sum((e.amount for e in extras), Decimal("0"))
    if not extras or total <= 0:
        return None

    today_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    mine = Notification.objects.filter(recipient=staff)
    if mine.filter(kind__startswith="extra_", created_at__gte=today_start).exists():
        return None

    salary = getattr(getattr(staff, "pay", None), "monthly_salary", None) or Decimal("0")
    goal = money(salary * goal_percent() / 100) if salary else Decimal("0")
    goal_kind = f"extra_goal_{month:%Y-%m}"
    run = streak_days(extras)

    if goal and total >= goal and not mine.filter(kind=goal_kind).exists():
        kind = goal_kind
        title = f"🏆 Amazing! Your extra work passed {goal_percent():g}% of your salary"
        body = f"That's {nrs(goal)}, and you're at {nrs(total)} in extras this month. Thank you for going the extra mile!"
    elif run >= 2:
        kind = "extra_streak"
        title = f"🔥 Keep it up! {run} days of extra work in a row"
        body = f"You've earned {nrs(total)} in extras this month. Your effort really shows."
    elif not mine.filter(kind="extra_start", created_at__gte=datetime.datetime.combine(month, datetime.time.min, tzinfo=today_start.tzinfo)).exists():
        kind = "extra_start"
        title = "🎉 Congrats! You've been doing extra work"
        body = f"{nrs(total)} in extras so far this month. If you keep going over several days, you'll be on a roll!"
    else:
        return None
    return notify([staff], kind, title, body)[0]
