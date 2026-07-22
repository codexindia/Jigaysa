"""In-app notifications API (PRD §3.12 Notifications).

Every endpoint is scoped to the current user: you only ever see and mutate your
own notifications, channel preferences and registered device tokens. Delivery to
external channels (email/SMS/WhatsApp/push) is a later phase; this exposes the
in-app bell, the read state, and the Settings preference matrix.
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notifications.models import (
    DeviceToken,
    Notification,
    NotificationCategory,
    NotificationPreference,
)
from notifications.serializers import (
    DeviceTokenSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)

ALL_ROLES = ("student", "trainer", "admin", "institution")


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """The current user's notification bell. Filter with ``?is_read=true|false``
    and ``?category=<category>``. PATCH to toggle ``is_read``."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        params = self.request.query_params
        if "is_read" in params:
            qs = qs.filter(is_read=params["is_read"].lower() in ("1", "true", "yes"))
        if params.get("category"):
            qs = qs.filter(category=params["category"])
        return qs

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({"unread": count})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"marked_read": updated})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])
        return Response(self.get_serializer(notification).data)


class NotificationPreferenceViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """The Settings notification matrix (category × channel) for the current
    user. Rows are seeded on demand so every category is always present."""

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        # Ensure a full matrix exists for the user, then return it.
        existing = set(
            self.get_queryset().values_list("category", flat=True)
        )
        missing = [
            NotificationPreference(user=request.user, category=cat)
            for cat, _ in NotificationCategory.choices
            if cat not in existing
        ]
        if missing:
            NotificationPreference.objects.bulk_create(missing, ignore_conflicts=True)
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DeviceTokenViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Register/unregister the current user's push tokens (PRD §3.12 push)."""

    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, _ = DeviceToken.objects.update_or_create(
            user=request.user,
            token=serializer.validated_data["token"],
            defaults={
                "platform": serializer.validated_data.get(
                    "platform", DeviceToken.Platform.WEB
                )
            },
        )
        out = self.get_serializer(token)
        return Response(out.data, status=status.HTTP_201_CREATED)
