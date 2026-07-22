"""Assessments & assignments routes (PRD §3.12). Mounted at ``/api/v1/``."""

from rest_framework.routers import DefaultRouter

from assessments import views

app_name = "assessments"

router = DefaultRouter()
router.register("assessments", views.AssessmentViewSet, basename="assessment")
router.register("submissions", views.SubmissionViewSet, basename="submission")

urlpatterns = router.urls
