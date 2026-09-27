from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import has_capability
from .serializers import CurrentUserSerializer, LoginSerializer, MemberSerializer


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
            return Response(
                {"detail": "Incorrect username or password."},
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
        return (
            User.objects.filter(is_active=True, role__unit=self.request.user.unit)
            .select_related("role")
            .order_by("role__rank", "first_name", "username")
        )
