from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import IsCompanyWide, has_capability
from .serializers import (
    CompanyMemberSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    MemberSerializer,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie so the React app can make POST requests."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "ok"})


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            # People may sign in with their email when it differs from their username.
            match = User.objects.filter(
                email__iexact=serializer.validated_data["username"].strip()
            ).exclude(email="")
            if match.count() == 1:
                user = authenticate(
                    request,
                    username=match.get().username,
                    password=serializer.validated_data["password"],
                )
        if user is None:
            return Response(
                {"detail": "Incorrect email or password."},
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
