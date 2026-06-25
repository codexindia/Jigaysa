import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role
from certificates.models import Certificate
from certificates.services import issue_for_enrollment
from courses.models import Course, Enrollment, Lesson, Module

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def trainer(db):
    return User.objects.create_user(
        email="t@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email="s@example.com", password="StrongPass123!", full_name="Sam Student",
        role=Role.STUDENT,
    )


@pytest.fixture
def course(trainer):
    return Course.objects.create(
        title="Free Course", trainer=trainer, is_free=True,
        status=Course.Status.PUBLISHED, duration_minutes=120,
    )


def auth(api, user):
    api.force_authenticate(user=user)
    return api


# --- auto issuance on completion -------------------------------------------


def test_certificate_auto_issued_on_completion(api, course, student):
    module = Module.objects.create(course=course, title="M1")
    lesson = Lesson.objects.create(module=module, title="L1")
    enrollment = Enrollment.objects.create(student=student, course=course)

    auth(api, student)
    resp = api.post(
        "/api/v1/lesson-progress/",
        {"enrollment": enrollment.id, "lesson": lesson.id, "status": "completed"},
        format="json",
    )
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    cert = Certificate.objects.filter(student=student, course=course).first()
    assert cert is not None
    assert cert.status == Certificate.Status.ISSUED
    assert cert.serial_number.startswith("JGY-")
    assert cert.total_hours == 2  # 120 min


def test_issue_is_idempotent(course, student):
    enrollment = Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.COMPLETED
    )
    c1, created1 = issue_for_enrollment(enrollment)
    c2, created2 = issue_for_enrollment(enrollment)
    assert created1 is True and created2 is False
    assert c1.id == c2.id
    assert Certificate.objects.filter(student=student, course=course).count() == 1


def test_issue_skipped_when_not_completed(course, student):
    enrollment = Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.ACTIVE
    )
    cert, created = issue_for_enrollment(enrollment)
    assert cert is None and created is False


# --- claim ------------------------------------------------------------------


def test_claim_requires_completion(api, course, student):
    Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.ACTIVE
    )
    auth(api, student)
    resp = api.post("/api/v1/certificates/claim/", {"course": course.id}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_claim_issues_for_completed(api, course, student):
    Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.COMPLETED
    )
    auth(api, student)
    resp = api.post("/api/v1/certificates/claim/", {"course": course.id}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["serial_number"].startswith("JGY-")


# --- visibility & verification ---------------------------------------------


def test_student_sees_only_own_certificates(api, course, student, trainer):
    other = User.objects.create_user(
        email="o@example.com", password="StrongPass123!", role=Role.STUDENT
    )
    e1 = Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.COMPLETED
    )
    e2 = Enrollment.objects.create(
        student=other, course=course, status=Enrollment.Status.COMPLETED
    )
    issue_for_enrollment(e1)
    issue_for_enrollment(e2)

    auth(api, student)
    resp = api.get("/api/v1/certificates/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["count"] == 1


def test_public_verification(api, course, student):
    enrollment = Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.COMPLETED
    )
    cert, _ = issue_for_enrollment(enrollment)

    # no authentication
    resp = api.get(f"/api/v1/certificates/verify/{cert.verification_code}/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["valid"] is True
    assert resp.data["holder"] == "Sam Student"
    assert resp.data["course_title"] == "Free Course"


def test_verification_unknown_code_404(api):
    resp = api.get("/api/v1/certificates/verify/nope/")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.data["valid"] is False


def test_revoked_certificate_is_invalid(api, course, student):
    enrollment = Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.COMPLETED
    )
    cert, _ = issue_for_enrollment(enrollment)
    admin = User.objects.create_user(
        email="a@example.com", password="StrongPass123!", role=Role.ADMIN
    )
    auth(api, admin)
    rv = api.post(f"/api/v1/certificates/{cert.id}/revoke/")
    assert rv.status_code == status.HTTP_200_OK

    api.force_authenticate(user=None)
    resp = api.get(f"/api/v1/certificates/verify/{cert.verification_code}/")
    assert resp.data["valid"] is False
    assert resp.data["status"] == "revoked"


# --- download ---------------------------------------------------------------


def test_download_returns_html(api, course, student):
    enrollment = Enrollment.objects.create(
        student=student, course=course, status=Enrollment.Status.COMPLETED
    )
    cert, _ = issue_for_enrollment(enrollment)
    auth(api, student)
    resp = api.get(f"/api/v1/certificates/{cert.id}/download/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp["Content-Type"].startswith("text/html")
    assert cert.serial_number in resp.content.decode()
