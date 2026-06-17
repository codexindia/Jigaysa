"""Recording storage, chapters, transcripts and per-user views (PRD §3.11)."""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Recording(TimeStampedModel):
    """A stored recording of a live session or course content (PRD §3.11)."""

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"

    session = models.ForeignKey(
        "live.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordings",
    )
    title = models.CharField(max_length=255)
    video_url = models.URLField(blank=True)
    cdn_url = models.URLField(blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    recorded_date = models.DateField(null=True, blank=True)
    views_count = models.PositiveIntegerField(default=0)
    ai_summary = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROCESSING
    )

    class Meta:
        ordering = ["-recorded_date", "-created_at"]

    def __str__(self):
        return self.title


class RecordingChapter(TimeStampedModel):
    """A chapter marker within a recording (PRD §3.11 chapter markers)."""

    recording = models.ForeignKey(
        Recording, on_delete=models.CASCADE, related_name="chapters"
    )
    title = models.CharField(max_length=255)
    start_seconds = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "start_seconds"]

    def __str__(self):
        return f"{self.recording} · {self.title}"


class RecordingTranscript(TimeStampedModel):
    """Searchable transcript for a recording (PRD §3.11 transcript/timestamps)."""

    recording = models.OneToOneField(
        Recording, on_delete=models.CASCADE, related_name="transcript"
    )
    segments = models.JSONField(default=list, blank=True)  # [{start, end, text}]
    language = models.CharField(max_length=20, default="en")

    def __str__(self):
        return f"Transcript<{self.recording}>"


class RecordingView(TimeStampedModel):
    """Per-user watch state (Recordings "Attended/Missed", views count)."""

    recording = models.ForeignKey(
        Recording, on_delete=models.CASCADE, related_name="views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recording_views",
    )
    watched_seconds = models.PositiveIntegerField(default=0)
    last_position = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recording", "user"], name="unique_recording_view"
            )
        ]

    def __str__(self):
        return f"{self.user} watched {self.recording}"
