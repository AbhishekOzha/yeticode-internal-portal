from django.contrib.auth.backends import ModelBackend


class RolePermissionBackend(ModelBackend):
    """Grants each user the permissions of their role.

    Super Admins already pass every check through ModelBackend. Per-user and
    group permissions are ignored so that the role stays the one place where
    access is decided.
    """

    def get_user_permissions(self, user_obj, obj=None):
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        if not hasattr(user_obj, "_role_perm_cache"):
            if user_obj.role_id is None:
                perms = set()
            else:
                perms = {
                    f"{app_label}.{codename}"
                    for app_label, codename in user_obj.role.permissions.values_list(
                        "content_type__app_label", "codename"
                    )
                }
            user_obj._role_perm_cache = perms
        return user_obj._role_perm_cache
