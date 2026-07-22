"""Serializers for live training, 1:1 and group sessions (PRD §3.5, §3.6)."""

from rest_framework import serializers

from live.models import (
    Attendance,
    IndividualBooking,
    LiveSession,
    SessionDoubt,
    SessionRegistration,
    TrainerAvailability,
)


class TrainerMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()


class LiveSessionSerializer(serializers.ModelSerializer):
    trainer = TrainerMiniSerializer(read_only=True)
    registrations_count = serializers.IntegerField(
        source="registrations.count", read_only=True
    )
    my_registration_status = serializers.SerializerMethodField()

    class Meta:
        model = LiveSession
        fields = (
            "id",
            "course",
            "batch",
            "trainer",
            "title",
            "description",
            "session_type",
            "scheduled_start",
            "duration_minutes",
            "capacity",
            "registration_limit",
            "status",
            "join_url",
            "meeting_id",
            "attendees_count",
            "registrations_count",
            "my_registration_status",
            "created_at",
        )
        read_only_fields = ("attendees_count",)

    def get_my_registration_status(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        reg = obj.registrations.filter(student=request.user).first()
        return reg.status if reg else None


class LiveSessionWriteSerializer(serializers.ModelSerializer):
    """Trainer create/update shape. ``trainer`` comes from the request."""

    class Meta:
        model = LiveSession
        fields = (
            "id",
            "course",
            "batch",
            "title",
            "description",
            "session_type",
            "scheduled_start",
            "duration_minutes",
            "capacity",
            "registration_limit",
            "status",
            "join_url",
            "meeting_id",
        )


class SessionRegistrationSerializer(serializers.ModelSerializer):
    session_detail = LiveSessionSerializer(source="session", read_only=True)

    class Meta:
        model = SessionRegistration
        fields = (
            "id",
            "session",
            "session_detail",
            "status",
            "registered_at",
            "joined_at",
            "attended",
        )
        read_only_fields = ("status", "registered_at", "joined_at", "attended")


class SessionDoubtSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = SessionDoubt
        fields = (
            "id",
            "session",
            "student",
            "student_name",
            "text",
            "status",
            "asked_at",
        )
        read_only_fields = ("student", "status", "asked_at")


class TrainerAvailabilitySerializer(serializers.ModelSerializer):
    trainer = TrainerMiniSerializer(read_only=True)

    class Meta:
        model = TrainerAvailability
        fields = (
            "id",
            "trainer",
            "start",
            "end",
            "slot_minutes",
            "is_booked",
        )
        read_only_fields = ("is_booked",)


class IndividualBookingSerializer(serializers.ModelSerializer):
    trainer_name = serializers.CharField(source="trainer.full_name", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = IndividualBooking
        fields = (
            "id",
            "trainer",
            "trainer_name",
            "student",
            "student_name",
            "start",
            "duration_minutes",
            "status",
            "meeting_url",
            "created_at",
        )
        read_only_fields = ("student", "status", "meeting_url")


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = (
            "id",
            "session",
            "student",
            "student_name",
            "joined_at",
            "left_at",
            "duration_seconds",
            "present",
        )
