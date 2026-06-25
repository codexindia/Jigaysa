"""Certificates routes (PRD §3.12). Mounted at ``/api/v1/``."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from certificates import views

app_name = "certificates"

router = DefaultRouter()
router.register(
    "certificate-templates",
    views.CertificateTemplateViewSet,
    basename="certificate-template",
)
router.register("certificates", views.CertificateViewSet, basename="certificate")

urlpatterns = [
    # Public QR verification — declared before the router so the literal
    # "verify" path is not shadowed by the certificate detail route.
    path(
        "certificates/verify/<str:code>/",
        views.VerifyCertificateView.as_view(),
        name="certificate-verify",
    ),
    *router.urls,
]
