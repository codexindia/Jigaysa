"""Reusable role-based DRF permissions (PRD §3.1 role-based access).

Usage:
    permission_classes = [IsTrainer]
    permission_classes = [HasRole("admin", "trainer")]
"""

from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    """Factory-style permission: allow only the given role(s).

    Instantiate with the roles you want to allow, e.g.
    ``HasRole("admin", "trainer")``. The user's ``role`` field is checked.
    """

    def __init__(self, *roles):
        self.roles = roles

    def __call__(self):
        # DRF instantiates permission classes; allow this instance to be
        # used directly in a permission_classes list.
        return self

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and getattr(user, "role", None) in self.roles
        )


def _role_permission(role):
    """Build a simple single-role BasePermission subclass."""

    class _RolePermission(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            return bool(
                user
                and user.is_authenticated
                and getattr(user, "role", None) == role
            )

    _RolePermission.__name__ = f"Is{role.capitalize()}"
    return _RolePermission


# Single-role convenience classes. Role strings mirror accounts.models.Role.
IsAdmin = _role_permission("admin")
IsTrainer = _role_permission("trainer")
IsStudent = _role_permission("student")
IsInstitution = _role_permission("institution")
