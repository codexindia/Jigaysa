from unittest import mock

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from core import storage

pytestmark = pytest.mark.django_db

S3_ON = dict(
    AWS_STORAGE_BUCKET_NAME="jigaysa-media",
    AWS_S3_REGION_NAME="ap-south-1",
    AWS_S3_ENDPOINT_URL="",
    AWS_S3_CUSTOM_DOMAIN="",
)


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


@pytest.fixture
def api(student):
    client = APIClient()
    client.force_authenticate(student)
    return client


# --- key building (pure) ----------------------------------------------------


def test_build_object_key_namespaces_by_purpose_and_user():
    key = storage.build_object_key("library_video", "My Lecture.MP4", user_id=7)
    assert key.startswith("library/videos/7/")
    assert key.endswith(".mp4")
    assert "my-lecture" in key


def test_build_object_key_rejects_unknown_purpose():
    with pytest.raises(ValueError):
        storage.build_object_key("hack", "x.txt", user_id=1)


# --- presign upload endpoint ------------------------------------------------


@override_settings(**S3_ON)
def test_presign_upload_returns_put_url(api):
    signed = "https://codexindia.r2.example/library/videos/7/x.mp4?sig=abc"
    with mock.patch(
        "core.storage.generate_presigned_upload", return_value=signed
    ) as gen:
        resp = api.post(
            "/api/v1/uploads/presign/",
            {
                "filename": "intro.mp4",
                "content_type": "video/mp4",
                "purpose": "library_video",
            },
            format="json",
        )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["method"] == "PUT"
    assert resp.data["url"] == signed
    assert resp.data["headers"] == {"Content-Type": "video/mp4"}
    assert resp.data["key"].startswith("library/videos/")
    # The key we hand back is the same one the presign was cut for.
    gen.assert_called_once()
    assert gen.call_args.args[0] == resp.data["key"]


@override_settings(**S3_ON)
def test_presign_upload_rejects_bad_purpose(api):
    resp = api.post(
        "/api/v1/uploads/presign/",
        {"filename": "a.txt", "content_type": "text/plain", "purpose": "nope"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@override_settings(AWS_STORAGE_BUCKET_NAME="")
def test_presign_upload_503_when_unconfigured(api):
    resp = api.post(
        "/api/v1/uploads/presign/",
        {"filename": "a.mp4", "content_type": "video/mp4", "purpose": "library_video"},
        format="json",
    )
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_presign_requires_auth():
    resp = APIClient().post("/api/v1/uploads/presign/", {}, format="json")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# --- presign download endpoint ----------------------------------------------


@override_settings(**S3_ON)
def test_presign_download(api):
    with mock.patch(
        "core.storage.generate_presigned_download",
        return_value="https://signed.example/get",
    ):
        resp = api.get("/api/v1/uploads/download/?key=library/videos/7/x.mp4")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["download_url"] == "https://signed.example/get"
