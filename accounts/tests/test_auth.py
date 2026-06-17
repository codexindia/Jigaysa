import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from accounts.models import LoginActivity, Role
from core.permissions import IsAdmin

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


# --- registration -----------------------------------------------------------


def test_register_creates_user(api):
    resp = api.post(
        reverse("accounts:register"),
        {"email": "new@example.com", "password": "StrongPass123!", "full_name": "New"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert User.objects.filter(email="new@example.com").exists()


def test_register_rejects_duplicate_email(api, student):
    resp = api.post(
        reverse("accounts:register"),
        {"email": "stu@example.com", "password": "StrongPass123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_register_rejects_weak_password(api):
    resp = api.post(
        reverse("accounts:register"),
        {"email": "weak@example.com", "password": "123"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# --- login / refresh / logout ----------------------------------------------


def test_login_returns_tokens_and_logs_activity(api, student):
    resp = api.post(
        reverse("accounts:login"),
        {"email": "stu@example.com", "password": "StrongPass123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "access" in resp.data and "refresh" in resp.data
    assert resp.data["user"]["role"] == Role.STUDENT
    assert LoginActivity.objects.filter(user=student, success=True).exists()


def test_login_failure_is_logged(api, student):
    resp = api.post(
        reverse("accounts:login"),
        {"email": "stu@example.com", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert LoginActivity.objects.filter(
        email_attempted="stu@example.com", success=False
    ).exists()


def test_token_refresh(api, student):
    login = api.post(
        reverse("accounts:login"),
        {"email": "stu@example.com", "password": "StrongPass123!"},
        format="json",
    )
    resp = api.post(
        reverse("accounts:token-refresh"),
        {"refresh": login.data["refresh"]},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "access" in resp.data


def test_logout_blacklists_refresh(api, student):
    login = api.post(
        reverse("accounts:login"),
        {"email": "stu@example.com", "password": "StrongPass123!"},
        format="json",
    )
    refresh = login.data["refresh"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    out = api.post(reverse("accounts:logout"), {"refresh": refresh}, format="json")
    assert out.status_code == status.HTTP_205_RESET_CONTENT

    # The blacklisted refresh token can no longer be used.
    again = api.post(
        reverse("accounts:token-refresh"), {"refresh": refresh}, format="json"
    )
    assert again.status_code == status.HTTP_401_UNAUTHORIZED


# --- me / auth requirement --------------------------------------------------


def test_me_requires_authentication(api):
    assert api.get(reverse("accounts:me")).status_code == status.HTTP_401_UNAUTHORIZED


def test_me_returns_profile(api, student):
    login = api.post(
        reverse("accounts:login"),
        {"email": "stu@example.com", "password": "StrongPass123!"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    resp = api.get(reverse("accounts:me"))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["email"] == "stu@example.com"


# --- RBAC -------------------------------------------------------------------


class _AdminOnlyView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({"ok": True})


def test_rbac_student_forbidden_from_admin_view(student):
    factory = APIRequestFactory()
    request = factory.get("/admin-only/")
    force_authenticate(request, user=student)
    response = _AdminOnlyView.as_view()(request)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_rbac_admin_allowed(db):
    admin = User.objects.create_user(
        email="admin@example.com", password="StrongPass123!", role=Role.ADMIN
    )
    factory = APIRequestFactory()
    request = factory.get("/admin-only/")
    force_authenticate(request, user=admin)
    response = _AdminOnlyView.as_view()(request)
    assert response.status_code == status.HTTP_200_OK


# --- scaffolded stubs -------------------------------------------------------


def test_otp_request_is_not_implemented(api):
    resp = api.post(reverse("accounts:otp-request"), {"phone": "+10000000000"}, format="json")
    assert resp.status_code == status.HTTP_501_NOT_IMPLEMENTED
