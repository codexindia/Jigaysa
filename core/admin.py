from django.contrib import admin

from core.models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "is_active", "created_at")
    list_filter = ("type", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
