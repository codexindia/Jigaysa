"""Serializers for in-app notifications, preferences and device tokens (§3.12)."""

from rest_framework import serializers

from notifications.models import (
    DeviceToken,
    Notification,
    NotificationPreference,
)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "category",
            "title",
            "body",
            "link",
            "is_read",
            "created_at",
        )
        read_only_fields = ("category", "title", "body", "link", "created_at")


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "id",
            "category",
            "in_app",
            "email",
            "sms",
            "whatsapp",
            "push",
        )


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ("id", "token", "platform", "created_at")
        read_only_fields = ("created_at",)
