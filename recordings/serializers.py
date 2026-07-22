"""Serializers for recordings, chapters, transcripts and views (PRD §3.11)."""

from rest_framework import serializers

from recordings.models import (
    Recording,
    RecordingChapter,
    RecordingTranscript,
    RecordingView,
)


class RecordingChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingChapter
        fields = ("id", "title", "start_seconds", "order")


class RecordingTranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingTranscript
        fields = ("id", "segments", "language")


class RecordingListSerializer(serializers.ModelSerializer):
    trainer_name = serializers.CharField(source="trainer.full_name", read_only=True)

    class Meta:
        model = Recording
        fields = (
            "id", "title", "course", "session", "trainer", "trainer_name",
            "duration_seconds", "recorded_date", "views_count", "status",
            "ai_summary",
        )


class RecordingDetailSerializer(RecordingListSerializer):
    chapters = RecordingChapterSerializer(many=True, read_only=True)
    transcript = RecordingTranscriptSerializer(read_only=True)
    video_url = serializers.SerializerMethodField()
    cdn_url = serializers.SerializerMethodField()
    my_view = serializers.SerializerMethodField()

    class Meta(RecordingListSerializer.Meta):
        fields = RecordingListSerializer.Meta.fields + (
            "video_url", "cdn_url", "chapters", "transcript", "my_view",
        )

    def _has_access(self, obj):
        return bool(self.context.get("has_access"))

    def get_video_url(self, obj):
        return obj.video_url if self._has_access(obj) else ""

    def get_cdn_url(self, obj):
        return obj.cdn_url if self._has_access(obj) else ""

    def get_my_view(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        view = obj.views.filter(user=request.user).first()
        if not view:
            return None
        return {
            "watched_seconds": view.watched_seconds,
            "last_position": view.last_position,
            "completed": view.completed,
        }


class RecordingViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingView
        fields = ("id", "recording", "watched_seconds", "last_position", "completed")
        read_only_fields = ("id",)
