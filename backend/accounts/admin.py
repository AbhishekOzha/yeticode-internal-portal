from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group

from .models import Role, Unit, User

# Access comes from roles, so groups would only be a second, confusing source.
admin.site.unregister(Group)


def super_admin_only(request):
    return request.user.is_active and request.user.is_superuser


# Only Super Admins may use the admin site at all.
admin.site.has_permission = super_admin_only


class RoleInline(admin.TabularInline):
    model = Role
    fields = ["name", "code", "rank"]
    extra = 0
    show_change_link = True


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "role_count", "member_count"]
    prepopulated_fields = {"code": ["name"]}
    search_fields = ["name"]
    inlines = [RoleInline]

    @admin.display(description="Roles")
    def role_count(self, obj):
        return obj.roles.count()

    @admin.display(description="Members")
    def member_count(self, obj):
        return User.objects.filter(role__unit=obj).count()


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "unit", "rank", "member_count"]
    list_filter = ["unit"]
    search_fields = ["name", "unit__name"]
    prepopulated_fields = {"code": ["name"]}
    filter_horizontal = ["permissions"]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "permissions":
            # Offer the app's capabilities rather than every model permission.
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                content_type__app_label="accounts", content_type__model="capability"
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.users.count()


class RoleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.unit.name} — {obj.name}"


class UserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "is_superuser"]
        field_classes = {**AdminUserCreationForm.Meta.field_classes, "role": RoleChoiceField}


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        field_classes = {**UserChangeForm.Meta.field_classes, "role": RoleChoiceField}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    list_display = ["username", "full_name", "unit_name", "role", "is_superuser", "is_active"]
    list_filter = ["role__unit", "role", "is_superuser", "is_active"]
    list_select_related = ["role__unit"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering = ["username"]
    fieldsets = [
        (None, {"fields": ["username", "password"]}),
        ("Personal info", {"fields": ["first_name", "last_name", "email"]}),
        (
            "Access",
            {
                "fields": ["role", "is_superuser", "is_active"],
                "description": "Pick one role; it decides the unit. Super Admins have no role.",
            },
        ),
        ("Important dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "username", "first_name", "last_name", "email",
                    "role", "is_superuser", "password1", "password2",
                ],
            },
        ),
    ]
    readonly_fields = ["last_login", "date_joined"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = Role.objects.select_related("unit")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.get_full_name()

    @admin.display(description="Unit", ordering="role__unit__name")
    def unit_name(self, obj):
        return obj.unit or "All units (Super Admin)"
