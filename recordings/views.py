"""Recording playback & storage API (PRD §3.11).

Students browse ready recordings and play them back with chapter markers and a
searchable transcript; playback position is tracked per user (resume, and the
Recordings "Attended/Missed" state). Video URLs are gated: a student must be
enrolled in the recording's course (or it must be an open/course-less recording)
to receive the playable URL. Trainers/admins manage recordings.
"""

from django.db.models import F, Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from courses.models import Enrollment
from recordings.models import Recording, RecordingView
from recordings.serializers import (
    RecordingDetailSerializer,
    RecordingListSerializer,
    RecordingViewSerializer,
)

ALL_ROLES = ("student", "trainer", "admin", "institution")
TRAINER_WRITE = ("trainer", "admin")


def _is_admin(user):
    return getattr(user, "role", None) == "admin"


def _is_trainer_role(user):
    return getattr(user, "role", None) in TRAINER_WRITE


def _filter_by(qs, request, param, field=None):
    value = request.query_params.get(param)
    if value:
        qs = qs.filter(**{field or param: value})
    return qs


class RecordingViewSet(viewsets.ModelViewSet):
    """Recordings. Filters: ``?course=<id>``, ``?session=<id>``, ``?trainer=<id>``,
    ``?q=<title search>``. Students only see ``ready`` recordings; trainers see
    their own (including processing). Authoring limited to owner/admin."""

    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "create": TRAINER_WRITE, "update": TRAINER_WRITE,
        "partial_update": TRAINER_WRITE, "destroy": TRAINER_WRITE,
    }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RecordingDetailSerializer
        return RecordingListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Recording.objects.select_related("trainer", "course", "session")
        if not _is_admin(user):
            if _is_trainer_role(user):
                qs = qs.filter(Q(status=Recording.Status.READY) | Q(trainer=user))
            else:
                qs = qs.filter(status=Recording.Status.READY)
        qs = _filter_by(qs, self.request, "course", "course_id")
        qs = _filter_by(qs, self.request, "session", "session_id")
        qs = _filter_by(qs, self.request, "trainer", "trainer_id")
        if self.request.query_params.get("q"):
            qs = qs.filter(title__icontains=self.request.query_params["q"])
        return qs

    def _has_access(self, recording, user):
        if _is_admin(user) or recording.trainer_id == user.id:
            return True
        if recording.course_id is None:
            return True  # open / library recording
        return Enrollment.objects.filter(
            student=user, course_id=recording.course_id
        ).exists()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.action == "retrieve":
            ctx["has_access"] = self._has_access(self.get_object(), self.request.user)
        return ctx

    def retrieve(self, request, *args, **kwargs):
        recording = self.get_object()
        if self._has_access(recording, request.user):
            Recording.objects.filter(pk=recording.pk).update(
                views_count=F("views_count") + 1
            )
            recording.refresh_from_db(fields=["views_count"])
        serializer = self.get_serializer(recording)
        return Response(serializer.data)

    def perform_create(self, serializer):
        if not _is_trainer_role(self.request.user):
            raise PermissionDenied("Only trainers can add recordings.")
        serializer.save(trainer=self.request.user)

    def _assert_owner(self, recording):
        user = self.request.user
        if recording.trainer_id != user.id and not _is_admin(user):
            raise PermissionDenied("You do not own this recording.")

    def perform_update(self, serializer):
        self._assert_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owner(instance)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="progress")
    def progress(self, request, pk=None):
        """Upsert the current user's watch progress (resume/complete)."""
        recording = self.get_object()
        if not self._has_access(recording, request.user):
            raise PermissionDenied("Enroll in the course to watch this recording.")
        view, _ = RecordingView.objects.get_or_create(
            recording=recording, user=request.user
        )
        data = request.data
        if "watched_seconds" in data:
            view.watched_seconds = int(data["watched_seconds"])
        if "last_position" in data:
            view.last_position = int(data["last_position"])
        if "completed" in data:
            view.completed = bool(data["completed"])
        elif recording.duration_seconds and view.last_position >= (
            recording.duration_seconds * 0.95
        ):
            view.completed = True
        view.save()
        return Response(RecordingViewSerializer(view).data)
