"""Notifications routes (PRD §3.12). Mounted at ``/api/v1/``."""

from rest_framework.routers import DefaultRouter

from notifications import views

app_name = "notifications"

router = DefaultRouter()
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register(
    "notification-preferences",
    views.NotificationPreferenceViewSet,
    basename="notification-preference",
)
router.register("device-tokens", views.DeviceTokenViewSet, basename="device-token")

urlpatterns = router.urls
