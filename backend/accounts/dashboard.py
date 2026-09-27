from .rbac import CAPABILITIES


def capabilities_for(user):
    """The app capability codenames this user has, in catalog order."""
    if user.is_superuser:
        return list(CAPABILITIES)
    granted = {perm.split(".", 1)[1] for perm in user.get_all_permissions() if perm.startswith("accounts.")}
    return [code for code in CAPABILITIES if code in granted]


def can_manage_users(user):
    """Super Admins manage everyone; unit roles with the capability manage their own unit."""
    if user.is_superuser:
        return True
    return (
        user.is_authenticated
        and user.unit is not None
        and user.has_perm("accounts.manage_unit_users")
    )


def dashboard_for(user):
    """The dashboard widgets to show, one per capability the user holds."""
    if user.is_superuser:
        return [
            {
                "key": "manage_users",
                "title": "Users",
                "description": "Create accounts, assign roles and deactivate users across all units.",
            },
            {
                "key": "manage_roles",
                "title": "Roles & permissions",
                "description": "See every unit's roles and change what each role can do.",
            },
            {
                "key": "manage_payroll",
                "title": CAPABILITIES["manage_payroll"][0],
                "description": CAPABILITIES["manage_payroll"][1],
            },
        ]
    return [
        {"key": code, "title": CAPABILITIES[code][0], "description": CAPABILITIES[code][1]}
        for code in capabilities_for(user)
    ]
