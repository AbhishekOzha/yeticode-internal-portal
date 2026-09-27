from rest_framework import serializers

from .dashboard import capabilities_for, dashboard_for
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

    class Meta:
        model = User
        fields = [
            "id", "username", "full_name", "email", "unit", "role",
            "is_super_admin", "capabilities", "dashboard",
        ]

    def get_capabilities(self, obj):
        return capabilities_for(obj)

    def get_dashboard(self, obj):
        return dashboard_for(obj)


class MemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name")
    role = serializers.CharField(source="role.name")

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "role"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)
