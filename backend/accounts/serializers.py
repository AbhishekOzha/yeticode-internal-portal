from rest_framework import serializers

from .dashboard import can_manage_users, capabilities_for, dashboard_for
from .models import CompanySettings, Role, Unit, User, email_in_use
from .uploads import delete_replaced_file, validate_image


class ImageUrlField(serializers.ImageField):
    """An uploaded image, returned as a site-relative URL (or null) that works behind the Vite proxy."""

    def to_representation(self, value):
        return value.url if value else None


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
    avatar = ImageUrlField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "full_name", "first_name", "last_name", "email", "secondary_email",
            "avatar", "unit", "role", "is_super_admin", "last_login", "capabilities", "dashboard",
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
    avatar = ImageUrlField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "avatar", "role"]


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


class ProfileSerializer(serializers.ModelSerializer):
    """What people may change about themselves: their photo and secondary email.

    The primary email is the sign-in address, so only an administrator can change it.
    """

    avatar = ImageUrlField(required=False, allow_null=True, validators=[validate_image])

    class Meta:
        model = User
        fields = ["avatar", "secondary_email"]

    def validate(self, attrs):
        if "email" in self.initial_data:
            raise serializers.ValidationError(
                {"email": "Your primary email can only be changed by an administrator."}
            )
        return attrs

    def validate_secondary_email(self, value):
        value = value.strip()
        if not value:
            return ""
        if value.lower() == (self.instance.email or "").lower():
            raise serializers.ValidationError("This is already your primary email.")
        if email_in_use(value, exclude=self.instance):
            raise serializers.ValidationError("Another account already uses this email.")
        return value

    def update(self, instance, validated_data):
        old_avatar = instance.avatar.name
        instance = super().update(instance, validated_data)
        delete_replaced_file(old_avatar, instance.avatar)
        return instance


class BrandingSerializer(serializers.ModelSerializer):
    """The public part of the company settings, shown on the sign-in page."""

    logo = ImageUrlField(read_only=True)

    class Meta:
        model = CompanySettings
        fields = ["name", "tagline", "logo", "updated_at"]


class CompanySettingsSerializer(serializers.ModelSerializer):
    logo = ImageUrlField(required=False, allow_null=True, validators=[validate_image])

    class Meta:
        model = CompanySettings
        fields = ["name", "tagline", "email", "phone", "website", "address", "logo", "updated_at"]
        read_only_fields = ["updated_at"]

    def update(self, instance, validated_data):
        old_logo = instance.logo.name
        instance = super().update(instance, validated_data)
        delete_replaced_file(old_logo, instance.logo)
        return instance
