from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from accounts.managers import UserManager
from core.models import TimeStampedModel


class Role(models.TextChoices):
    """Platform roles (PRD §2). Mirrored by core.permissions role classes."""

    ADMIN = "admin", "Admin"
    TRAINER = "trainer", "Trainer / Lecturer"
    STUDENT = "student", "Student / Learner"
    INSTITUTION = "institution", "Institution / Corporate Client"


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Email-first custom user (PRD §3.1).

    Deliberately has no ``username``. ``phone`` and ``organization`` are
    present now so future features (OTP login, institution multi-tenancy,
    social/biometric IDs) attach without a painful user-model migration.
    """

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STUDENT
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    phone_verified = models.BooleanField(default=False)
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # email + password are prompted by default

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class LoginActivity(TimeStampedModel):
    """Login audit trail (PRD §3.1 advanced: login activity logs)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="login_activities",
        null=True,
        blank=True,
    )
    email_attempted = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "login activities"

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.email_attempted or self.user} [{status}] @ {self.created_at}"
