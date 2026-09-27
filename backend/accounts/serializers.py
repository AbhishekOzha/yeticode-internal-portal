from rest_framework import serializers

from .dashboard import can_manage_users, capabilities_for, dashboard_for
from .models import Role, Unit, User


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "code", "name"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "rank"]


class CurrentUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name")
    unit = UnitSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    is_super_admin = serializers.BooleanField(read_only=True)
    capabilities = serializers.SerializerMethodField()
    dashboard = serializers.SerializerMethodField()
    can_manage_users = serializers.SerializerMethodField()
    can_manage_roles = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "full_name", "first_name", "last_name", "email", "unit", "role",
            "is_super_admin", "capabilities", "dashboard",
            "can_manage_users", "can_manage_roles",
        ]

    def get_capabilities(self, obj):
        return capabilities_for(obj)

    def get_dashboard(self, obj):
        return dashboard_for(obj)

    def get_can_manage_users(self, obj):
        return can_manage_users(obj)


class MemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name")
    role = serializers.CharField(source="role.name")

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "role"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)


class CompanyMemberSerializer(MemberSerializer):
    unit = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()

    class Meta(MemberSerializer.Meta):
        fields = MemberSerializer.Meta.fields + ["unit", "unit_code"]

    def get_unit(self, obj):
        return obj.unit.name if obj.unit else "All units"

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit else None
