"""Event → notification + gamification signal wiring (PRD §3.12)."""

import pytest

from accounts.models import Role, User
from courses.models import Category, Course, Enrollment
from engagement.models import CommunityProfile
from notifications.models import Notification, NotificationCategory

pytestmark = pytest.mark.django_db


@pytest.fixture
def trainer():
    return User.objects.create_user(
        email="t@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="s@example.com", password="StrongPass123!", role=Role.STUDENT
    )


@pytest.fixture
def course(trainer):
    return Course.objects.create(
        title="DS", trainer=trainer, is_free=True,
        category=Category.objects.create(name="Data"),
        status=Course.Status.PUBLISHED,
    )


def test_enrollment_creates_notification_and_awards_points(student, course):
    Enrollment.objects.create(
        student=student, course=course,
        status=Enrollment.Status.ACTIVE, source=Enrollment.Source.FREE,
    )
    note = Notification.objects.filter(
        recipient=student, category=NotificationCategory.COURSE
    ).first()
    assert note is not None
    assert "Enrolled" in note.title
    profile = CommunityProfile.objects.get(user=student)
    assert profile.points == 10  # POINTS["enroll"]


def test_notification_respects_in_app_off(student, course):
    from notifications.models import NotificationPreference

    NotificationPreference.objects.create(
        user=student, category=NotificationCategory.COURSE,
        in_app=False, email=False, sms=False, whatsapp=False, push=False,
    )
    Enrollment.objects.create(
        student=student, course=course,
        status=Enrollment.Status.ACTIVE, source=Enrollment.Source.FREE,
    )
    assert not Notification.objects.filter(recipient=student).exists()
    # Points are still awarded regardless of notification channel prefs.
    assert CommunityProfile.objects.get(user=student).points == 10
