"""Gamification: award points and badges for student activity (PRD §3.12).

Central so the point values and level curve live in one place. Called from the
notification/event signal handlers, not sprinkled through the viewsets.
"""

from engagement.models import Badge, CommunityProfile, UserBadge

# Points awarded per activity type.
POINTS = {
    "enroll": 10,
    "lesson_complete": 5,
    "assessment_pass": 25,
    "certificate": 50,
    "reply": 5,
    "accepted_answer": 20,
}

# 500 points per level.
POINTS_PER_LEVEL = 500


def award_points(user, activity):
    amount = POINTS.get(activity, 0)
    if not amount:
        return
    profile, _ = CommunityProfile.objects.get_or_create(user=user)
    profile.points += amount
    profile.level = 1 + profile.points // POINTS_PER_LEVEL
    profile.save(update_fields=["points", "level", "updated_at"])


def award_badge(user, slug):
    """Grant a badge by slug if it exists and the user doesn't have it yet."""
    badge = Badge.objects.filter(slug=slug).first()
    if badge is None:
        return
    _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
    if created:
        profile, _ = CommunityProfile.objects.get_or_create(user=user)
        profile.badges_count = UserBadge.objects.filter(user=user).count()
        profile.save(update_fields=["badges_count", "updated_at"])
