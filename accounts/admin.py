from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from accounts.models import LoginActivity, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Email-based admin (no username field)."""

    ordering = ("-created_at",)
    list_display = ("email", "full_name", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name", "phone")
    readonly_fields = ("created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("full_name", "phone", "phone_verified")}),
        (_("Role & tenancy"), {"fields": ("role", "organization")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ("email_attempted", "user", "success", "ip_address", "created_at")
    list_filter = ("success",)
    search_fields = ("email_attempted", "ip_address")
    readonly_fields = (
        "user",
        "email_attempted",
        "ip_address",
        "user_agent",
        "success",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
