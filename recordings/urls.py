"""Recording & storage routes (PRD §3.11). Mounted at ``/api/v1/``."""

from rest_framework.routers import DefaultRouter

from recordings import views

app_name = "recordings"

router = DefaultRouter()
router.register("recordings", views.RecordingViewSet, basename="recording")

urlpatterns = router.urls
