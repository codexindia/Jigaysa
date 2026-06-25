import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role
from courses.models import Course, Enrollment, Lesson, Module

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def trainer(db):
    return User.objects.create_user(
        email="trainer@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def other_trainer(db):
    return User.objects.create_user(
        email="t2@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


def auth(api, user):
    api.force_authenticate(user=user)
    return api


# --- authoring --------------------------------------------------------------


def test_trainer_creates_course(api, trainer):
    auth(api, trainer)
    resp = api.post(
        "/api/v1/courses/",
        {"title": "Python 101", "is_free": True, "course_type": "self_paced"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    course = Course.objects.get()
    assert course.trainer == trainer
    assert course.slug == "python-101"
    assert course.status == Course.Status.DRAFT


def test_student_cannot_create_course(api, student):
    auth(api, student)
    resp = api.post("/api/v1/courses/", {"title": "X"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_trainer_cannot_edit_others_course(api, trainer, other_trainer):
    course = Course.objects.create(title="A", trainer=trainer)
    auth(api, other_trainer)
    resp = api.patch(
        f"/api/v1/courses/{course.slug}/", {"title": "Hacked"}, format="json"
    )
    assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


# --- visibility -------------------------------------------------------------


def test_student_sees_only_published_courses(api, trainer, student):
    Course.objects.create(title="Draft", trainer=trainer)
    Course.objects.create(
        title="Live", trainer=trainer, status=Course.Status.PUBLISHED
    )
    auth(api, student)
    resp = api.get("/api/v1/courses/")
    assert resp.status_code == status.HTTP_200_OK
    titles = [c["title"] for c in resp.data["results"]]
    assert titles == ["Live"]


def test_publish_by_trainer_sets_pending(api, trainer):
    course = Course.objects.create(title="A", trainer=trainer)
    auth(api, trainer)
    resp = api.post(f"/api/v1/courses/{course.slug}/publish/")
    assert resp.status_code == status.HTTP_200_OK
    course.refresh_from_db()
    assert course.status == Course.Status.PENDING_REVIEW


# --- enrollment + progress --------------------------------------------------


def test_free_course_enrollment_and_progress(api, trainer, student):
    course = Course.objects.create(
        title="Free Course",
        trainer=trainer,
        is_free=True,
        status=Course.Status.PUBLISHED,
    )
    module = Module.objects.create(course=course, title="M1")
    l1 = Lesson.objects.create(module=module, title="L1")
    l2 = Lesson.objects.create(module=module, title="L2")

    auth(api, student)
    enroll = api.post(f"/api/v1/courses/{course.slug}/enroll/")
    assert enroll.status_code == status.HTTP_201_CREATED
    enrollment = Enrollment.objects.get(student=student, course=course)
    course.refresh_from_db()
    assert course.enrolled_count == 1

    # complete one of two lessons -> 50%
    api.post(
        "/api/v1/lesson-progress/",
        {"enrollment": enrollment.id, "lesson": l1.id, "status": "completed"},
        format="json",
    )
    enrollment.refresh_from_db()
    assert enrollment.progress_pct == 50

    # complete the second -> 100% and enrollment marked completed
    api.post(
        "/api/v1/lesson-progress/",
        {"enrollment": enrollment.id, "lesson": l2.id, "status": "completed"},
        format="json",
    )
    enrollment.refresh_from_db()
    assert enrollment.progress_pct == 100
    assert enrollment.status == Enrollment.Status.COMPLETED


def test_paid_course_enrollment_blocked(api, trainer, student):
    course = Course.objects.create(
        title="Paid", trainer=trainer, is_free=False, status=Course.Status.PUBLISHED
    )
    auth(api, student)
    resp = api.post(f"/api/v1/courses/{course.slug}/enroll/")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_duplicate_enrollment_rejected(api, trainer, student):
    course = Course.objects.create(
        title="Free", trainer=trainer, is_free=True, status=Course.Status.PUBLISHED
    )
    auth(api, student)
    assert api.post(f"/api/v1/courses/{course.slug}/enroll/").status_code == 201
    assert api.post(f"/api/v1/courses/{course.slug}/enroll/").status_code == 400


# --- reviews ----------------------------------------------------------------


def test_review_requires_enrollment(api, trainer, student):
    course = Course.objects.create(
        title="C", trainer=trainer, is_free=True, status=Course.Status.PUBLISHED
    )
    auth(api, student)
    resp = api.post(
        "/api/v1/reviews/",
        {"course": course.id, "rating": 5, "comment": "great"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_review_updates_course_rating(api, trainer, student):
    course = Course.objects.create(
        title="C", trainer=trainer, is_free=True, status=Course.Status.PUBLISHED
    )
    Enrollment.objects.create(student=student, course=course)
    auth(api, student)
    resp = api.post(
        "/api/v1/reviews/",
        {"course": course.id, "rating": 4, "comment": "good"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    course.refresh_from_db()
    assert course.rating_count == 1
    assert float(course.rating_avg) == 4.0
