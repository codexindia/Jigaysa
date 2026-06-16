from django.db import models
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    """Abstract base giving every model audit timestamps.

    All future LMS models (courses, payments, live sessions, etc.) should
    inherit from this so created/updated tracking is uniform platform-wide.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    """A tenant: institution or corporate client (PRD §2.4).

    Users optionally belong to an Organization, giving us a multi-tenant
    seam (NFR: multi-tenant architecture) without re-modeling later. Bulk
    enrollments, custom batches and training analytics will hang off this.
    """

    class OrgType(models.TextChoices):
        INSTITUTION = "institution", "Institution"
        CORPORATE = "corporate", "Corporate"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    type = models.CharField(
        max_length=20, choices=OrgType.choices, default=OrgType.INSTITUTION
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
