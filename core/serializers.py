"""Serializers for the media-upload presign endpoints."""

from rest_framework import serializers

from core.storage import UPLOAD_PURPOSES


class PresignUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=127)
    purpose = serializers.ChoiceField(choices=sorted(UPLOAD_PURPOSES))


class PresignDownloadSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=1024)
