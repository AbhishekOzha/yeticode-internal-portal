from django.urls import path
from rest_framework.routers import SimpleRouter

from . import manage, views

router = SimpleRouter()
router.register("manage/users", manage.ManagedUserViewSet, basename="manage-users")
router.register("manage/roles", manage.ManagedRoleViewSet, basename="manage-roles")
router.register("manage/capabilities", manage.CapabilityListView, basename="manage-capabilities")

# There is deliberately no public sign-up endpoint. Accounts are created only by
# Super Admins and Unit Admins, through /api/manage/users/ (or the Django admin).
urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("unit/members/", views.UnitMembersView.as_view(), name="unit-members"),
    path("company/members/", views.CompanyMembersView.as_view(), name="company-members"),
] + router.urls
