"""Notification emission (PRD §3.12).

``notify()`` is the one entry point the rest of the app calls to alert a user.
It honours the user's per-category channel preferences: an in-app row is created
when ``in_app`` is on (the default), and enabled external channels (email/SMS/
WhatsApp/push) are dispatched through a pluggable sender — a console stub for now,
swap for real providers later.
"""

from notifications.models import (
    Notification,
    NotificationCategory,
    NotificationPreference,
)


def _preference(user, category):
    pref = NotificationPreference.objects.filter(user=user, category=category).first()
    if pref is not None:
        return pref
    # Sensible default when the user hasn't customised: in-app + email on.
    return NotificationPreference(
        user=user, category=category, in_app=True, email=True,
        sms=False, whatsapp=False, push=False,
    )


def _dispatch_external(channel, user, title, body):
    # Placeholder for real email/SMS/WhatsApp/push providers.
    print(f"[notify:{channel}] → {user}: {title} — {body}")


def notify(user, category, title, body="", link=""):
    """Create an in-app notification (if enabled) and fan out to other channels
    the user has turned on. Returns the created Notification or ``None``."""
    if category not in dict(NotificationCategory.choices):
        category = NotificationCategory.SYSTEM
    pref = _preference(user, category)

    notification = None
    if pref.in_app:
        notification = Notification.objects.create(
            recipient=user, category=category, title=title, body=body, link=link
        )
    for channel in ("email", "sms", "whatsapp", "push"):
        if getattr(pref, channel):
            _dispatch_external(channel, user, title, body)
    return notification
