import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import (
    Notification,
    NotificationCategory,
    NotificationPreference,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


def test_preferences_matrix_is_seeded_on_list(student):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.get("/api/v1/notification-preferences/")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.data) == len(NotificationCategory.choices)
    assert NotificationPreference.objects.filter(user=student).count() == len(
        NotificationCategory.choices
    )


def test_unread_count_and_mark_all_read(student):
    Notification.objects.create(recipient=student, title="A")
    Notification.objects.create(recipient=student, title="B")
    api = APIClient()
    api.force_authenticate(student)
    assert api.get("/api/v1/notifications/unread_count/").data["unread"] == 2
    api.post("/api/v1/notifications/mark_all_read/")
    assert api.get("/api/v1/notifications/unread_count/").data["unread"] == 0


def test_user_only_sees_own_notifications(student):
    other = User.objects.create_user(
        email="o@example.com", password="StrongPass123!", role=Role.STUDENT
    )
    Notification.objects.create(recipient=other, title="not yours")
    api = APIClient()
    api.force_authenticate(student)
    resp = api.get("/api/v1/notifications/")
    assert resp.data["count"] == 0
