"""Completion certificates with public QR verification (PRD §3.12)."""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class CertificateTemplate(TimeStampedModel):
    """A reusable certificate design (admin/trainer config)."""

    name = models.CharField(max_length=255)
    design = models.TextField(blank=True)  # HTML or storage ref
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificate_templates",
    )

    def __str__(self):
        return self.name


class Certificate(TimeStampedModel):
    """An issued certificate (Certificates cards: serial, grade, hours, verify)."""

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        REVOKED = "revoked", "Revoked"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="certificates"
    )
    enrollment = models.ForeignKey(
        "courses.Enrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    serial_number = models.CharField(max_length=40, unique=True)  # JGY-YYYY-NNNNNN
    issued_date = models.DateField(null=True, blank=True)
    grade = models.CharField(max_length=40, blank=True)
    total_hours = models.PositiveIntegerField(default=0)
    pdf_url = models.URLField(blank=True)
    verification_code = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ISSUED
    )

    class Meta:
        ordering = ["-issued_date", "-created_at"]

    def __str__(self):
        return f"{self.serial_number} · {self.student}"
