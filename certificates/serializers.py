"""Serializers for the Certificates module (PRD §3.12)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from certificates.models import Certificate, CertificateTemplate

User = get_user_model()


class StudentMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "full_name", "email")


class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = ("id", "name", "design", "course", "created_at")


class CertificateSerializer(serializers.ModelSerializer):
    """Full certificate read shape for the holder / admin."""

    student = StudentMiniSerializer(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.SlugField(source="course.slug", read_only=True)
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "id",
            "serial_number",
            "student",
            "course",
            "course_title",
            "course_slug",
            "enrollment",
            "template",
            "issued_date",
            "grade",
            "total_hours",
            "pdf_url",
            "verification_code",
            "verification_url",
            "status",
        )
        read_only_fields = fields

    def get_verification_url(self, obj):
        request = self.context.get("request")
        path = f"/api/v1/certificates/verify/{obj.verification_code}/"
        return request.build_absolute_uri(path) if request else path


class CertificateVerifySerializer(serializers.ModelSerializer):
    """Public verification payload (QR target) — no auth, minimal PII."""

    holder = serializers.CharField(source="student.full_name", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    valid = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "valid",
            "serial_number",
            "holder",
            "course_title",
            "issued_date",
            "total_hours",
            "grade",
            "status",
        )

    def get_valid(self, obj):
        return obj.status == Certificate.Status.ISSUED


class CertificateClaimSerializer(serializers.Serializer):
    """Claim the certificate for a course the requester has completed."""

    course = serializers.IntegerField()
