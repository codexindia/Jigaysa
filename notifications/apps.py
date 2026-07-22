from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'notifications'

    def ready(self):
        # Register the event → notification/gamification signal receivers.
        from notifications import handlers  # noqa: F401
