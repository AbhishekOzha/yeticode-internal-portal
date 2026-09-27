from django.urls import path

from . import views

# There is deliberately no sign-up endpoint: Super Admins create accounts in the admin.
urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="csrf"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("unit/members/", views.UnitMembersView.as_view(), name="unit-members"),
    path("company/members/", views.CompanyMembersView.as_view(), name="company-members"),
]
