"""Free / premium learning library and bookmarks (PRD §3.10)."""

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from core.models import TimeStampedModel


class LibraryResource(TimeStampedModel):
    """A library item: video, ebook, notes, webinar, etc. (PRD §3.10)."""

    class Format(models.TextChoices):
        VIDEO = "video", "Video"
        EBOOK = "ebook", "E-book"
        NOTES = "notes", "Notes"
        WEBINAR = "webinar", "Webinar"
        SAMPLE_LESSON = "sample_lesson", "Sample lesson"
        CERT_RESOURCE = "cert_resource", "Certification resource"

    class AccessLevel(models.TextChoices):
        FREE = "free", "Free"
        PREMIUM = "premium", "Premium"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)
    format = models.CharField(
        max_length=20, choices=Format.choices, default=Format.VIDEO
    )
    category = models.ForeignKey(
        "courses.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_resources",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_resources",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_resources",
    )
    file_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    pages = models.PositiveIntegerField(default=0)
    access_level = models.CharField(
        max_length=20, choices=AccessLevel.choices, default=AccessLevel.FREE
    )
    views_count = models.PositiveIntegerField(default=0)
    popularity_score = models.PositiveIntegerField(default=0)
    thumbnail = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-popularity_score", "-published_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class LibraryBookmark(TimeStampedModel):
    """A user's saved library item (Library "Saved" tab)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_bookmarks",
    )
    resource = models.ForeignKey(
        LibraryResource, on_delete=models.CASCADE, related_name="bookmarks"
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "resource"], name="unique_library_bookmark"
            )
        ]

    def __str__(self):
        return f"{self.user} ★ {self.resource}"
