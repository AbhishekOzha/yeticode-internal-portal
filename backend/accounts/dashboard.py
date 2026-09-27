from .rbac import CAPABILITIES


def capabilities_for(user):
    """The app capability codenames this user has, in catalog order."""
    if user.is_superuser:
        return list(CAPABILITIES)
    granted = {perm.split(".", 1)[1] for perm in user.get_all_permissions() if perm.startswith("accounts.")}
    return [code for code in CAPABILITIES if code in granted]


def dashboard_for(user):
    """The dashboard widgets to show, one per capability the user holds."""
    if user.is_superuser:
        return [
            {
                "key": "admin_panel",
                "title": "Administration",
                "description": "Create accounts and manage units, roles and permissions.",
            }
        ]
    return [
        {"key": code, "title": CAPABILITIES[code][0], "description": CAPABILITIES[code][1]}
        for code in capabilities_for(user)
    ]
