from rest_framework.permissions import BasePermission


def has_capability(codename):
    """DRF permission class that requires the "accounts.<codename>" capability."""

    class HasCapability(BasePermission):
        message = "Your role does not allow this."

        def has_permission(self, request, view):
            return request.user.has_perm(f"accounts.{codename}")

    HasCapability.__name__ = f"HasCapability_{codename}"
    return HasCapability
