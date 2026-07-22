import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(
        email="stu@example.com", password="OldPass123!", role=Role.STUDENT,
        phone="+919000000001",
    )


# --- password reset ---------------------------------------------------------


def test_password_reset_request_is_generic(user):
    api = APIClient()
    # Known and unknown emails both return 200 with the same message.
    r1 = api.post("/api/v1/auth/password-reset/", {"email": user.email}, format="json")
    r2 = api.post("/api/v1/auth/password-reset/", {"email": "nobody@x.com"}, format="json")
    assert r1.status_code == r2.status_code == status.HTTP_200_OK
    assert r1.data["detail"] == r2.data["detail"]


def test_password_reset_confirm_changes_password(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    api = APIClient()
    resp = api.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "BrandNew456!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("BrandNew456!")


def test_password_reset_confirm_rejects_bad_token(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    api = APIClient()
    resp = api.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": "not-a-valid-token", "new_password": "BrandNew456!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# --- mobile OTP -------------------------------------------------------------


def test_otp_request_then_verify_issues_tokens(user):
    api = APIClient()
    req = api.post("/api/v1/auth/otp/request/", {"phone": user.phone}, format="json")
    assert req.status_code == status.HTTP_200_OK
    code = cache.get(f"otp:{user.phone}")["code"]

    resp = api.post(
        "/api/v1/auth/otp/verify/",
        {"phone": user.phone, "code": code},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "access" in resp.data and "refresh" in resp.data
    user.refresh_from_db()
    assert user.phone_verified is True


def test_otp_verify_wrong_code(user):
    api = APIClient()
    api.post("/api/v1/auth/otp/request/", {"phone": user.phone}, format="json")
    resp = api.post(
        "/api/v1/auth/otp/verify/",
        {"phone": user.phone, "code": "000000"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_otp_verify_without_request(user):
    cache.delete(f"otp:{user.phone}")
    api = APIClient()
    resp = api.post(
        "/api/v1/auth/otp/verify/",
        {"phone": user.phone, "code": "123456"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
