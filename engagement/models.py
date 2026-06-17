"""Discussion forum, community feed and gamification (PRD §3.12, dashboard).

Forum threads are scoped to a course (or community-wide). Community profile,
points and badges back the dashboard's community card.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class DiscussionThread(TimeStampedModel):
    """A question/discussion scoped to a course or the community (PRD §3.12)."""

    class Scope(models.TextChoices):
        COURSE = "course", "Course"
        COMMUNITY = "community", "Community"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="threads",
    )
    batch = models.ForeignKey(
        "courses.Batch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="threads",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="threads",
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    scope = models.CharField(
        max_length=20, choices=Scope.choices, default=Scope.COURSE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    is_pinned = models.BooleanField(default=False)
    reply_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-is_pinned", "-last_activity_at", "-created_at"]

    def __str__(self):
        return self.title


class DiscussionReply(TimeStampedModel):
    """A reply to a thread; self-nesting for threaded replies (PRD §3.12)."""

    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    body = models.TextField()
    is_accepted_answer = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "discussion replies"

    def __str__(self):
        return f"Reply by {self.author} on {self.thread}"


class CommunityProfile(TimeStampedModel):
    """Gamification state per user (dashboard "1,240 pts", level)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_profile",
    )
    points = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    badges_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user} · {self.points} pts"


class Badge(TimeStampedModel):
    """A badge that can be earned (dashboard medals)."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    icon = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    criteria = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class UserBadge(TimeStampedModel):
    """A badge earned by a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
    )
    badge = models.ForeignKey(
        Badge, on_delete=models.CASCADE, related_name="awarded_to"
    )
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-earned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "badge"], name="unique_user_badge"
            )
        ]

    def __str__(self):
        return f"{self.user} earned {self.badge}"


class CommunityPost(TimeStampedModel):
    """A community feed post (PRD community support)."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    body = models.TextField()
    post_type = models.CharField(max_length=40, blank=True)
    likes_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Post by {self.author}"
