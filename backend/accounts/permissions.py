from rest_framework.permissions import BasePermission


def has_capability(codename):
    """DRF permission class that requires the "accounts.<codename>" capability."""

    class HasCapability(BasePermission):
        message = "Your role does not allow this."

        def has_permission(self, request, view):
            return request.user.has_perm(f"accounts.{codename}")

    HasCapability.__name__ = f"HasCapability_{codename}"
    return HasCapability


class IsCompanyWide(BasePermission):
    """Only Super Admins and users with a company-wide role may see across units."""

    message = "Your role only has access to your own unit."

    def has_permission(self, request, view):
        user = request.user
        return user.is_superuser or (user.role_id is not None and user.role.unit_id is None)
