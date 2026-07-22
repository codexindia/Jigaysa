"""Media upload (direct-to-S3 presign) routes. Mounted at ``/api/v1/uploads/``."""

from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("presign/", views.PresignUploadView.as_view(), name="presign-upload"),
    path("download/", views.PresignDownloadView.as_view(), name="presign-download"),
]
