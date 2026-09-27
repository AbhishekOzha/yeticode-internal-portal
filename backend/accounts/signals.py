from django.contrib.auth.models import Permission
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import Role, check_role_capabilities


@receiver(m2m_changed, sender=Role.permissions.through)
def block_cross_unit_capabilities(sender, instance, action, reverse, pk_set, **kwargs):
    """Stop cross-unit capabilities reaching a unit-scoped role, however they're added."""
    if action != "pre_add" or reverse:
        return
    check_role_capabilities(
        instance.unit, Permission.objects.filter(pk__in=pk_set).select_related("content_type")
    )
