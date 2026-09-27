"""User and role management for the React app.

Super Admins manage every account and role. Unit Admins (the
`manage_unit_users` capability) manage accounts in their own unit only and
can only hand out roles from that unit.
"""

from django.contrib.auth import password_validation
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import BasePermission

from .dashboard import can_manage_users
from .models import Role, User, check_role_capabilities
from .rbac import CAPABILITIES, CROSS_UNIT_CAPABILITIES


class CanManageUsers(BasePermission):
    message = "Your role cannot manage users."

    def has_permission(self, request, view):
        return can_manage_users(request.user)


class IsSuperAdmin(BasePermission):
    message = "Only Super Admins can do this."

    def has_permission(self, request, view):
        return request.user.is_superuser


def unit_label(unit):
    return unit.name if unit else "All units"


class ManagedUserSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.select_related("unit"), allow_null=True, required=False
    )
    role_name = serializers.CharField(source="role.name", read_only=True, default=None)
    unit = serializers.SerializerMethodField()
    is_super_admin = serializers.BooleanField(source="is_superuser", required=False)
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=False, trim_whitespace=False
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "role_name", "unit", "is_super_admin", "is_active",
            "password", "last_login", "date_joined",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def get_unit(self, obj):
        if obj.is_superuser:
            return "All units (Super Admin)"
        return unit_label(obj.unit)

    def validate(self, attrs):
        actor = self.context["request"].user
        instance = self.instance
        is_super = attrs.get("is_superuser", instance.is_superuser if instance else False)
        role = attrs["role"] if "role" in attrs else (instance.role if instance else None)

        if not actor.is_superuser:
            if is_super:
                raise serializers.ValidationError({"is_super_admin": "Only Super Admins can do this."})
            if role is not None and role.unit_id != actor.unit.id:
                raise serializers.ValidationError({"role": "Pick a role from your own unit."})

        if is_super:
            # Super Admins work across all units and never hold a role.
            attrs["role"] = None
        elif role is None:
            raise serializers.ValidationError({"role": "Pick a role for this user."})

        if instance is not None and instance.pk == actor.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "You cannot deactivate yourself."})
            if "role" in attrs and attrs["role"] != instance.role or is_super != instance.is_superuser:
                raise serializers.ValidationError({"role": "You cannot change your own access."})

        password = attrs.get("password")
        if instance is None and not password:
            raise serializers.ValidationError({"password": "Set a password for the new account."})
        if password:
            candidate = instance or User(
                username=attrs.get("username", ""),
                email=attrs.get("email", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
            )
            try:
                password_validation.validate_password(password, candidate)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ManagedUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Accounts are deactivated rather than deleted, so there is no DELETE."""

    serializer_class = ManagedUserSerializer
    permission_classes = [CanManageUsers]
    pagination_class = None

    def get_queryset(self):
        users = User.objects.select_related("role__unit").order_by(
            "-is_superuser", "role__unit__name", "role__rank", "username"
        )
        actor = self.request.user
        if actor.is_superuser:
            return users
        return users.filter(is_superuser=False, role__unit=actor.unit)


class ManagedRoleSerializer(serializers.ModelSerializer):
    unit = serializers.SerializerMethodField()
    unit_id = serializers.IntegerField(read_only=True)
    capabilities = serializers.ListField(child=serializers.CharField(), required=False)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "code", "name", "rank", "unit", "unit_id", "capabilities", "member_count"]
        read_only_fields = ["code", "name", "rank"]

    def get_unit(self, obj):
        return unit_label(obj.unit)

    def get_member_count(self, obj):
        return obj.users.filter(is_active=True).count()

    def to_representation(self, obj):
        data = super().to_representation(obj)
        granted = {p.codename for p in obj.permissions.all() if p.content_type.app_label == "accounts"}
        data["capabilities"] = [code for code in CAPABILITIES if code in granted]
        return data

    def validate_capabilities(self, value):
        unknown = sorted(set(value) - set(CAPABILITIES))
        if unknown:
            raise serializers.ValidationError(f"Unknown capabilities: {', '.join(unknown)}")
        return value

    def update(self, instance, validated_data):
        if "capabilities" in validated_data:
            perms = list(
                Permission.objects.filter(
                    content_type__app_label="accounts",
                    codename__in=validated_data["capabilities"],
                ).select_related("content_type")
            )
            try:
                check_role_capabilities(instance.unit, perms)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"capabilities": list(exc.messages)})
            instance.permissions.set(perms)
        return instance


class ManagedRoleViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Unit Admins can list their unit's roles (to assign them); Super Admins can edit any."""

    serializer_class = ManagedRoleSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action == "list":
            return [CanManageUsers()]
        return [IsSuperAdmin()]

    def get_queryset(self):
        roles = Role.objects.select_related("unit").prefetch_related("permissions__content_type")
        actor = self.request.user
        if actor.is_superuser:
            return roles.order_by("unit__name", "rank", "name")
        return roles.filter(unit=actor.unit).order_by("rank", "name")


class CapabilityListView(viewsets.ViewSet):
    permission_classes = [IsSuperAdmin]

    def list(self, request):
        from rest_framework.response import Response

        return Response(
            [
                {
                    "code": code,
                    "label": label,
                    "description": description,
                    "cross_unit": code in CROSS_UNIT_CAPABILITIES,
                }
                for code, (label, description) in CAPABILITIES.items()
            ]
        )
