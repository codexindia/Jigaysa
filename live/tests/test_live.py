import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from live.models import LiveSession, SessionRegistration

pytestmark = pytest.mark.django_db


@pytest.fixture
def trainer():
    return User.objects.create_user(
        email="trainer@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


@pytest.fixture
def session(trainer):
    return LiveSession.objects.create(
        trainer=trainer, title="Pandas workshop", registration_limit=1
    )


def test_student_cannot_schedule_session(student):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.post("/api/v1/live-sessions/", {"title": "x"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_register_join_and_raise_doubt(session, student):
    api = APIClient()
    api.force_authenticate(student)

    reg = api.post(f"/api/v1/live-sessions/{session.id}/register/")
    assert reg.status_code == status.HTTP_201_CREATED
    assert reg.data["status"] == SessionRegistration.Status.REGISTERED

    join = api.post(f"/api/v1/live-sessions/{session.id}/join/")
    assert join.status_code == status.HTTP_200_OK

    doubt = api.post(
        f"/api/v1/live-sessions/{session.id}/raise-doubt/",
        {"text": "reshape with melt?"},
        format="json",
    )
    assert doubt.status_code == status.HTTP_201_CREATED


def test_registration_waitlists_past_limit(session, student):
    other = User.objects.create_user(
        email="o@example.com", password="StrongPass123!", role=Role.STUDENT
    )
    # First registrant takes the single slot.
    SessionRegistration.objects.create(session=session, student=other)
    api = APIClient()
    api.force_authenticate(student)
    reg = api.post(f"/api/v1/live-sessions/{session.id}/register/")
    assert reg.data["status"] == SessionRegistration.Status.WAITLISTED


def test_join_requires_registration(session, student):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.post(f"/api/v1/live-sessions/{session.id}/join/")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
