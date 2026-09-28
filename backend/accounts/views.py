from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CompanySettings, User
from .usernames import username_from_login
from .permissions import IsCompanyWide, IsSuperAdmin, has_capability
from .serializers import (
    BrandingSerializer,
    CompanyMemberSerializer,
    CompanySettingsSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    MemberSerializer,
    ProfileSerializer,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie so the React app can make POST requests."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "ok"})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(APIView):
    """Who's signed in: {"user": {...}} or {"user": null}. Always 200, and sets the CSRF cookie.

    The app calls this on start-up, so the sign-in page doesn't log a failed request.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response({"user": CurrentUserSerializer(user).data if user else None})


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        typed = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]
        # "abhishekojha", "abhishekojha@<our domain>" or an email address all work.
        user = None
        username = username_from_login(typed)
        if username:
            match = User.objects.filter(username__iexact=username).first()
            if match:
                user = authenticate(request, username=match.username, password=password)
        if user is None and "@" in typed:
            # Deactivated accounts can't sign in, so they don't make an email ambiguous.
            match = User.objects.filter(email__iexact=typed, is_active=True).exclude(email="")
            if match.count() == 1:
                user = authenticate(request, username=match.get().username, password=password)
        if user is None:
            return Response(
                {"detail": "Incorrect username, email or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(CurrentUserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """The signed-in user with their unit, role, capabilities and dashboard."""

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class ProfileView(APIView):
    """People edit their own photo and secondary email. Returns the same shape as /auth/me/."""

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(CurrentUserSerializer(user).data)


class BrandingView(APIView):
    """Company name and logo. Public, because the sign-in page shows them."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(BrandingSerializer(CompanySettings.load()).data)


class CompanySettingsView(APIView):
    """Company details and logo, editable by Super Admins only."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response(CompanySettingsSerializer(CompanySettings.load()).data)

    def patch(self, request):
        serializer = CompanySettingsSerializer(CompanySettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UnitMembersView(generics.ListAPIView):
    """Everyone in the signed-in user's unit."""

    serializer_class = MemberSerializer
    permission_classes = [has_capability("view_unit_directory")]
    pagination_class = None

    def get_queryset(self):
        unit = self.request.user.unit
        if unit is None:
            return User.objects.none()
        return (
            User.objects.filter(is_active=True, role__unit=unit)
            .select_related("role")
            .order_by("role__rank", "first_name", "username")
        )


class CompanyMembersView(generics.ListAPIView):
    """Everyone employed across all units. For company-wide roles such as Head HR."""

    serializer_class = CompanyMemberSerializer
    permission_classes = [IsCompanyWide, has_capability("view_all_employee_records")]
    pagination_class = None

    def get_queryset(self):
        return (
            User.objects.filter(is_active=True, is_superuser=False)
            .select_related("role__unit")
            .order_by("role__unit__name", "role__rank", "first_name", "username")
        )
