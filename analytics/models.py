"""Reports & analytics (PRD §3.14).

DESIGN-READY: most dashboard numbers are computed on read from the operational
tables. ``AnalyticsSnapshot`` exists to cache periodic admin/trainer metrics.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class AnalyticsSnapshot(TimeStampedModel):
    """A cached metrics snapshot for a scope + period (PRD §3.14 dashboards)."""

    class Scope(models.TextChoices):
        PLATFORM = "platform", "Platform (admin)"
        TRAINER = "trainer", "Trainer"
        COURSE = "course", "Course"
        ORGANIZATION = "organization", "Organization"

    scope = models.CharField(max_length=20, choices=Scope.choices)
    subject_id = models.PositiveIntegerField(null=True, blank=True)
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="analytics_snapshots",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_snapshots",
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]

    def __str__(self):
        return f"{self.scope} snapshot {self.period_start}–{self.period_end}"
