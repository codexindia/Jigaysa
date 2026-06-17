"""Smart / physical / container classrooms and IoT devices (PRD §3.7-3.9).

DESIGN-READY: tables exist so the smart-classroom and Phase-2 container features
attach without schema churn. No API is exposed for these yet.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Room(TimeStampedModel):
    """A physical, smart or container classroom (PRD §3.8, §3.9)."""

    class RoomType(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        SMART = "smart", "Smart (IoT)"
        CONTAINER = "container", "Container / mobile"

    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    name = models.CharField(max_length=255)
    room_type = models.CharField(
        max_length=20, choices=RoomType.choices, default=RoomType.PHYSICAL
    )
    capacity = models.PositiveIntegerField(default=0)
    layout = models.JSONField(default=dict, blank=True)
    location = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Seat(TimeStampedModel):
    """A seat in a room (PRD §3.8 seat allocation)."""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="seats")
    label = models.CharField(max_length=20)  # e.g. A1
    row = models.PositiveIntegerField(default=0)
    col = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room", "label"], name="unique_room_seat"
            )
        ]

    def __str__(self):
        return f"{self.room} · {self.label}"


class Device(TimeStampedModel):
    """An IoT device: mic, camera, speaker, etc. (PRD §3.7 hardware)."""

    class DeviceType(models.TextChoices):
        MIC = "mic", "Microphone"
        CAMERA = "camera", "Camera"
        SPEAKER = "speaker", "Speaker"
        SMARTBOARD = "smartboard", "Smart board"
        DISPLAY = "display", "Display"

    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="devices",
    )
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    identifier = models.CharField(max_length=120)  # e.g. Mic ID 001
    status = models.CharField(max_length=40, blank=True)
    firmware = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f"{self.device_type}:{self.identifier}"


class SeatDeviceMapping(TimeStampedModel):
    """Maps a device to a seat (PRD §3.8 Seat A1 → Mic ID 001)."""

    seat = models.ForeignKey(
        Seat, on_delete=models.CASCADE, related_name="device_mappings"
    )
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="seat_mappings"
    )

    def __str__(self):
        return f"{self.seat} ↔ {self.device}"


class ClassroomSession(TimeStampedModel):
    """A class held in a room, optionally taught remotely (PRD §3.7)."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        COMPLETED = "completed", "Completed"

    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="sessions"
    )
    live_session = models.ForeignKey(
        "live.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classroom_sessions",
    )
    remote_trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remote_classroom_sessions",
    )
    date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )

    def __str__(self):
        return f"{self.room} @ {self.date}"


class SeatAttendance(TimeStampedModel):
    """Attendance by seat for a classroom session (PRD §3.8 attendance by seat)."""

    classroom_session = models.ForeignKey(
        ClassroomSession, on_delete=models.CASCADE, related_name="seat_attendance"
    )
    seat = models.ForeignKey(
        Seat, on_delete=models.CASCADE, related_name="attendance"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seat_attendance",
    )
    present = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.seat} · {'present' if self.present else 'absent'}"


class ContainerClassroom(TimeStampedModel):
    """Mobile / container classroom telemetry (PRD §3.9, Phase-2)."""

    room = models.OneToOneField(
        Room, on_delete=models.CASCADE, related_name="container"
    )
    gps = models.CharField(max_length=64, blank=True)
    connectivity_status = models.CharField(max_length=40, blank=True)
    power_status = models.CharField(max_length=40, blank=True)
    mobile_unit_id = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"Container<{self.room}>"


class SmartEvent(TimeStampedModel):
    """A motion/voice/raise-hand event in a smart classroom (PRD §3.7 AI)."""

    class EventType(models.TextChoices):
        VOICE = "voice", "Voice detected"
        MOTION = "motion", "Motion detected"
        RAISE_HAND = "raise_hand", "Raise hand"

    classroom_session = models.ForeignKey(
        ClassroomSession, on_delete=models.CASCADE, related_name="events"
    )
    seat = models.ForeignKey(
        Seat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.event_type} @ {self.seat}"
