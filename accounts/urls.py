from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts import views

app_name = "accounts"

urlpatterns = [
    # Phase 1 — implemented
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    # Scaffolded — return 501 until implemented in a later phase
    path("otp/request/", views.OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="otp-verify"),
    path("social/", views.SocialLoginView.as_view(), name="social-login"),
    path(
        "password-reset/", 
        views.PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
