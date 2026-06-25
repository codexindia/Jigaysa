from django.contrib import admin

from certificates.models import Certificate, CertificateTemplate


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "course")
    search_fields = ("name",)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "serial_number",
        "student",
        "course",
        "status",
        "issued_date",
        "total_hours",
    )
    list_filter = ("status", "issued_date")
    search_fields = ("serial_number", "student__email", "course__title")
    readonly_fields = ("verification_code",)
