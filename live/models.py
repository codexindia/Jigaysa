"""Live training, 1:1 and group sessions (PRD §3.5, §3.6).

Same models serve the student (register/join/raise-doubt) and the trainer
(schedule/host). Realtime artefacts (chat, polls) are out of scope for the DB
layer; persisted doubts are kept so they can later feed the smart-classroom
module.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class LiveSession(TimeStampedModel):
    """A scheduled live class / workshop / 1:1 (PRD §3.5 features)."""

    class SessionType(models.TextChoices):
        GROUP = "group", "Group"
        INDIVIDUAL = "individual", "Individual"
        WORKSHOP = "workshop", "Workshop"
        QA = "qa", "Q&A"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="live_sessions",
    )
    batch = models.ForeignKey(
        "courses.Batch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="live_sessions",
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="live_sessions",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    session_type = models.CharField(
        max_length=20, choices=SessionType.choices, default=SessionType.GROUP
    )
    scheduled_start = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    capacity = models.PositiveIntegerField(default=0)
    registration_limit = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    join_url = models.URLField(blank=True)
    meeting_id = models.CharField(max_length=255, blank=True)
    recording = models.ForeignKey(
        "recordings.Recording",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    attendees_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["scheduled_start"]

    def __str__(self):
        return self.title


class SessionRegistration(TimeStampedModel):
    """A student's registration for a session; waitlist via status (PRD §3.5)."""

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        WAITLISTED = "waitlisted", "Waitlisted"
        CANCELLED = "cancelled", "Cancelled"

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name="registrations"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_registrations",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REGISTERED
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    attended = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"], name="unique_session_registration"
            )
        ]

    def __str__(self):
        return f"{self.student} → {self.session} [{self.status}]"


class Attendance(TimeStampedModel):
    """Attendance record for a session (PRD §3.5 attendance tracking)."""

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name="attendance"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_attendance",
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    present = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student} @ {self.session} ({'present' if self.present else 'absent'})"


class TrainerAvailability(TimeStampedModel):
    """A bookable slot in a trainer's calendar (PRD §3.6 individual sessions)."""

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    slot_minutes = models.PositiveIntegerField(default=60)
    is_booked = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "trainer availability"
        ordering = ["start"]

    def __str__(self):
        return f"{self.trainer} {self.start:%Y-%m-%d %H:%M}"


class IndividualBooking(TimeStampedModel):
    """A 1:1 booking, pay-per-hour (PRD §3.6 individual sessions)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings_received",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings_made",
    )
    start = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    order = models.ForeignKey(
        "payments.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    meeting_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-start"]

    def __str__(self):
        return f"{self.student} ↔ {self.trainer} [{self.status}]"


class SessionDoubt(TimeStampedModel):
    """A doubt / raised hand during a session (PRD §3.5; links to §3.7 later)."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ANSWERED = "answered", "Answered"

    session = models.ForeignKey(
        LiveSession, on_delete=models.CASCADE, related_name="doubts"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_doubts",
    )
    text = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    asked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["asked_at"]

    def __str__(self):
        return f"Doubt by {self.student} @ {self.session}"
