"""Role-aware OpenAPI schema (PRD §3.1 role-based access — docs layer).

Resource URLs stay role-agnostic (a course is one resource, read by several
roles). Instead, each view *declares* which roles may call each action and this
``AutoSchema`` stamps a ``[Role · Role]`` badge onto every operation's summary
in Swagger, plus a machine-readable ``x-roles`` extension. Because the badge is
derived from the view's own declaration, the docs cannot drift silently.

Declare on a view (ViewSet or APIView):

    api_roles = ("student", "trainer", "admin", "institution")  # default
    api_roles_by_action = {"create": ("trainer", "admin")}      # per-action

Use the literal ``"public"`` for unauthenticated endpoints.
"""

from drf_spectacular.openapi import AutoSchema

ROLE_LABELS = {
    "public": "Public",
    "admin": "Admin",
    "trainer": "Trainer",
    "student": "Student",
    "institution": "Institution",
}


class RoleAwareAutoSchema(AutoSchema):
    """Prefix each operation summary with the roles allowed to call it."""

    def get_operation(self, *args, **kwargs):
        operation = super().get_operation(*args, **kwargs)
        if not operation:
            return operation
        roles = self._roles_for_action()
        if roles:
            badge = " · ".join(ROLE_LABELS.get(r, r.title()) for r in roles)
            summary = operation.get("summary") or ""
            operation["summary"] = f"[{badge}] {summary}".rstrip()
            operation["x-roles"] = list(roles)
        return operation

    def _roles_for_action(self):
        view = self.view
        action = getattr(view, "action", None) or self.method.lower()
        by_action = getattr(view, "api_roles_by_action", None) or {}
        if action in by_action:
            return by_action[action]
        return getattr(view, "api_roles", None)
