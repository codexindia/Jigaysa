"""In-app notifications, per-channel preferences and device tokens (PRD §3.12).

``NotificationPreference`` is the exact Settings matrix (category × channel).
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class NotificationCategory(models.TextChoices):
    """Shared category enum for notifications and preferences."""

    COURSE = "course", "Course"
    LIVE_CLASS = "live_class", "Live class"
    ASSESSMENT = "assessment", "Assessment"
    CERTIFICATE = "certificate", "Certificate"
    FORUM = "forum", "Forum"
    PAYMENT = "payment", "Payment"
    SYSTEM = "system", "System"


class Notification(TimeStampedModel):
    """An in-app notification (header bell)."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.SYSTEM,
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient} · {self.title}"


class NotificationPreference(TimeStampedModel):
    """Per-category channel preferences (Settings notification matrix)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    category = models.CharField(
        max_length=20, choices=NotificationCategory.choices
    )
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=True)
    sms = models.BooleanField(default=False)
    whatsapp = models.BooleanField(default=False)
    push = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"], name="unique_notification_pref"
            )
        ]

    def __str__(self):
        return f"{self.user} · {self.category} prefs"


class DeviceToken(TimeStampedModel):
    """A registered push token for a user device (PRD §3.12 push)."""

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    token = models.CharField(max_length=512)
    platform = models.CharField(
        max_length=20, choices=Platform.choices, default=Platform.WEB
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "token"], name="unique_device_token"
            )
        ]

    def __str__(self):
        return f"{self.user} · {self.platform}"
