import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from library.models import LibraryBookmark, LibraryResource

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


@pytest.fixture
def trainer():
    return User.objects.create_user(
        email="trainer@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def resource(trainer):
    return LibraryResource.objects.create(
        title="Intro to SQL", format=LibraryResource.Format.VIDEO, author=trainer
    )


def test_student_lists_and_searches_library(student, resource):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.get("/api/v1/library-resources/?q=sql")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["count"] == 1


def test_retrieve_increments_views(student, resource):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.get(f"/api/v1/library-resources/{resource.slug}/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["views_count"] == 1


def test_bookmark_toggle(student, resource):
    api = APIClient()
    api.force_authenticate(student)
    on = api.post(f"/api/v1/library-resources/{resource.slug}/bookmark/")
    assert on.data["bookmarked"] is True
    assert LibraryBookmark.objects.filter(user=student, resource=resource).exists()
    off = api.post(f"/api/v1/library-resources/{resource.slug}/bookmark/")
    assert off.data["bookmarked"] is False


def test_student_cannot_author_resource(student):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.post("/api/v1/library-resources/", {"title": "X"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
