"""Usernames: just the name part (e.g. "abhishekojha"); the organisation's domain completes it.

With the domain "corecontent.com" in Company settings, the username "abhishekojha"
signs in as "abhishekojha@corecontent.com". People can also sign in with the bare
username or with their email.
"""

import re

from django.core.exceptions import ValidationError

# 2–30 characters: lowercase letters and digits, with ".", "_" or "-" in between.
USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,28}[a-z0-9])$")
SEPARATOR = "@"


def company_domain():
    from .models import CompanySettings

    return CompanySettings.load().domain.strip().lower()


def full_username(username, domain=None):
    """"abhishekojha" -> "abhishekojha@corecontent.com" (just the username if no domain is set)."""
    domain = company_domain() if domain is None else domain
    return f"{username}{SEPARATOR}{domain}" if domain and username else username


def clean_username(value):
    """Validate a username typed into the app, returning it lowercased."""
    value = (value or "").strip().lower()
    if SEPARATOR in value:
        raise ValidationError(
            "Type only the name part, e.g. abhishekojha. The organisation's domain is added automatically."
        )
    if not USERNAME_RE.match(value):
        raise ValidationError(
            "Use 2–30 lowercase letters or numbers; dots, dashes and underscores are allowed in between."
        )
    return value


def slugify_username(value):
    """Best-effort username from any text: "Abhishek Ojha" -> "abhishekojha", "a.b@x.com" -> "a.b"."""
    value = (value or "").strip().lower().split(SEPARATOR, 1)[0]
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^a-z0-9._-]", "", value)
    value = value.strip("._-")[:30].strip("._-")
    return value if len(value) >= 2 else ""


def unique_username(base, taken):
    """`base`, or base2, base3, … if it's in `taken` (a set of lowercase usernames)."""
    base = base or "user"
    candidate, n = base, 2
    while candidate in taken:
        suffix = str(n)
        candidate = f"{base[: 30 - len(suffix)].rstrip('._-')}{suffix}"
        n += 1
    return candidate


def username_from_login(value):
    """What someone typed at sign-in -> the username to look up, if it's one of ours.

    "abhishekojha" and "abhishekojha@<our domain>" both give "abhishekojha";
    anything else with an "@" is treated as an email (returns None).
    """
    value = (value or "").strip().lower()
    if SEPARATOR not in value:
        return value
    local, _, domain = value.partition(SEPARATOR)
    ours = company_domain()
    return local if ours and domain == ours else None
