from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import LoginActivity
from accounts.serializers import (
    LogoutSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    UserSerializer,
)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RegisterView(generics.CreateAPIView):
    """POST /auth/register/ — email/password signup."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    api_roles = ("public",)


class LoginView(TokenObtainPairView):
    """POST /auth/login/ — JWT obtain; records a LoginActivity row."""

    serializer_class = TokenPairSerializer
    permission_classes = [AllowAny]
    api_roles = ("public",)

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", "")
        common = {
            "email_attempted": email,
            "ip_address": _client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            LoginActivity.objects.create(success=False, **common)
            raise

        from accounts.models import User

        user = User.objects.filter(email=email).first()
        LoginActivity.objects.create(user=user, success=True, **common)
        return response


class LogoutView(APIView):
    """POST /auth/logout/ — blacklist the supplied refresh token."""

    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer
    api_roles = ("student", "trainer", "admin", "institution")

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /auth/me/ — the authenticated user's profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ("student", "trainer", "admin", "institution")

    def get_object(self):
        return self.request.user


# --- Scaffolded endpoints (Phase 2+). Contracts exist; logic is pending. ---


class _NotImplementedView(APIView):
    """Base for scaffolded auth flows: returns 501 with a clear message.

    Provider hooks live in accounts/providers.py. Replace these with real
    implementations in a later phase.
    """

    permission_classes = [AllowAny]
    api_roles = ("public",)
    feature = "This endpoint"

    def post(self, request, *args, **kwargs):
        return Response(
            {"detail": f"{self.feature} is not implemented yet (planned for a later phase)."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class OTPRequestView(_NotImplementedView):
    feature = "Mobile OTP request"


class OTPVerifyView(_NotImplementedView):
    feature = "Mobile OTP verification"


class SocialLoginView(_NotImplementedView):
    feature = "Social / SSO login"


class PasswordResetRequestView(_NotImplementedView):
    feature = "Password reset request"


class PasswordResetConfirmView(_NotImplementedView):
    feature = "Password reset confirmation"
