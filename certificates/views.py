"""Certificates API (PRD §3.12 — completion certificates, QR verification).

Certificates are issued automatically when an enrollment completes (see
``certificates.services.issue_for_enrollment`` called from the courses progress
recompute). This module exposes them: holders list/download their certificates,
admins revoke, and a public endpoint verifies a certificate by its code (QR).
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from certificates.models import Certificate, CertificateTemplate
from certificates.serializers import (
    CertificateClaimSerializer,
    CertificateSerializer,
    CertificateTemplateSerializer,
    CertificateVerifySerializer,
)
from certificates.services import issue_for_enrollment
from core.permissions import IsAdmin

ALL_ROLES = ("student", "trainer", "admin", "institution")


def _is_admin(user):
    return getattr(user, "role", None) == "admin"


class CertificateTemplateViewSet(viewsets.ModelViewSet):
    """Reusable certificate designs. Read for any authenticated user; admins
    and trainers manage them."""

    queryset = CertificateTemplate.objects.select_related("course")
    serializer_class = CertificateTemplateSerializer
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "create": ("trainer", "admin"),
        "update": ("trainer", "admin"),
        "partial_update": ("trainer", "admin"),
        "destroy": ("trainer", "admin"),
    }

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        role = getattr(self.request.user, "role", None)
        if role in ("trainer", "admin"):
            return [IsAuthenticated()]
        return [IsAdmin()]


class CertificateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Issued certificates. Students see their own; trainers see certificates
    for their courses; admins see all."""

    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ("student", "trainer", "admin")
    api_roles_by_action = {
        "claim": ("student",),
        "revoke": ("admin",),
        "download": ("student", "admin"),
    }

    def get_queryset(self):
        user = self.request.user
        qs = Certificate.objects.select_related("student", "course", "template")
        if _is_admin(user):
            return qs
        if getattr(user, "role", None) == "trainer":
            return qs.filter(course__trainer=user)
        return qs.filter(student=user)

    @action(detail=False, methods=["post"])
    def claim(self, request):
        """Issue (or fetch) the certificate for a course the student completed."""
        from courses.models import Enrollment

        serializer = CertificateClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = (
            Enrollment.objects.filter(
                student=request.user, course_id=serializer.validated_data["course"]
            )
            .select_related("course")
            .first()
        )
        if not enrollment:
            raise ValidationError("You are not enrolled in this course.")
        if enrollment.status != Enrollment.Status.COMPLETED:
            raise ValidationError(
                "Complete the course before claiming a certificate."
            )
        cert, created = issue_for_enrollment(enrollment)
        return Response(
            CertificateSerializer(cert, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsAdmin])
    def revoke(self, request, pk=None):
        """Admin revokes a certificate (PRD: revoke status)."""
        cert = get_object_or_404(Certificate, pk=pk)
        cert.status = Certificate.Status.REVOKED
        cert.save(update_fields=["status", "updated_at"])
        return Response(
            CertificateSerializer(cert, context={"request": request}).data
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Return a printable HTML certificate (browser → Save as PDF).

        Real PDF rendering (reportlab/weasyprint) can replace this later; the
        HTML keeps the module dependency-free for now.
        """
        cert = self.get_object()  # queryset-scoped: holder/trainer/admin only
        html = _render_certificate_html(cert, request)
        return HttpResponse(html, content_type="text/html")


class VerifyCertificateView(APIView):
    """GET /certificates/verify/{code}/ — public QR verification (PRD §3.12)."""

    permission_classes = [AllowAny]
    serializer_class = CertificateVerifySerializer
    api_roles = ("public",)

    def get(self, request, code):
        cert = Certificate.objects.select_related("student", "course").filter(
            verification_code=code
        ).first()
        if not cert:
            return Response(
                {"valid": False, "detail": "Certificate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CertificateVerifySerializer(cert).data)


_DEFAULT_CERT_HTML = """
<div style="font-family:Georgia,serif;text-align:center;padding:60px;
            border:8px double #b8860b;max-width:800px;margin:40px auto">
  <h1 style="letter-spacing:2px">Certificate of Completion</h1>
  <p>This certifies that</p>
  <h2>{{holder}}</h2>
  <p>has successfully completed</p>
  <h3>{{course}}</h3>
  <p>{{hours}} hours{{grade}}</p>
  <p style="margin-top:40px">Serial: <b>{{serial}}</b> &middot; Issued: {{date}}</p>
  <p style="font-size:12px;color:#666">Verify at {{verify}}</p>
</div>
"""


def _render_certificate_html(cert, request):
    """Render a certificate to HTML by substituting ``{{token}}`` placeholders.

    Works for both the built-in design and custom templates; uses literal token
    replacement (not ``str.format``) so arbitrary HTML/CSS braces are safe.
    """
    body = (cert.template.design if cert.template and cert.template.design
            else _DEFAULT_CERT_HTML)
    verify_url = request.build_absolute_uri(
        f"/api/v1/certificates/verify/{cert.verification_code}/"
    )
    tokens = {
        "{{holder}}": cert.student.full_name or cert.student.email,
        "{{course}}": cert.course.title,
        "{{hours}}": str(cert.total_hours),
        "{{grade}}": f" &middot; Grade: {cert.grade}" if cert.grade else "",
        "{{serial}}": cert.serial_number,
        "{{date}}": str(cert.issued_date or ""),
        "{{verify}}": verify_url,
    }
    for token, value in tokens.items():
        body = body.replace(token, value)
    return body
