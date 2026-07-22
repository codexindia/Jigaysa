"""Live training, 1:1 and group sessions API (PRD §3.5, §3.6).

Student flows: browse/upcoming sessions, register (with automatic waitlisting
when the registration limit is reached), join, raise a doubt, and book a 1:1 slot
from a trainer's availability. Trainer flows: schedule/host sessions, publish
availability, see doubts and attendance. Session authoring is limited to the
owning trainer or an admin.
"""

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from live.models import (
    IndividualBooking,
    LiveSession,
    SessionDoubt,
    SessionRegistration,
    TrainerAvailability,
)
from live.serializers import (
    IndividualBookingSerializer,
    LiveSessionSerializer,
    LiveSessionWriteSerializer,
    SessionDoubtSerializer,
    SessionRegistrationSerializer,
    TrainerAvailabilitySerializer,
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


class LiveSessionViewSet(viewsets.ModelViewSet):
    """Live sessions. Filters: ``?course=<id>``, ``?batch=<id>``, ``?trainer=<id>``,
    ``?status=scheduled|live|completed|cancelled``, ``?upcoming=true``,
    ``?mine=true`` (trainer's own). Authoring is limited to the owning trainer or
    an admin; students register/join/raise doubts via custom actions."""

    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "create": TRAINER_WRITE,
        "update": TRAINER_WRITE,
        "partial_update": TRAINER_WRITE,
        "destroy": TRAINER_WRITE,
        "register": ("student",),
        "join": ("student", "trainer", "admin"),
        "raise_doubt": ("student",),
        "doubts": ("student", "trainer", "admin"),
    }

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LiveSessionWriteSerializer
        return LiveSessionSerializer

    def get_queryset(self):
        qs = LiveSession.objects.select_related("trainer", "course", "batch")
        params = self.request.query_params
        qs = _filter_by(qs, self.request, "course", "course_id")
        qs = _filter_by(qs, self.request, "batch", "batch_id")
        qs = _filter_by(qs, self.request, "trainer", "trainer_id")
        qs = _filter_by(qs, self.request, "status")
        if params.get("upcoming", "").lower() in ("1", "true", "yes"):
            qs = qs.filter(scheduled_start__gte=timezone.now())
        if params.get("mine", "").lower() in ("1", "true", "yes"):
            qs = qs.filter(trainer=self.request.user)
        return qs

    def perform_create(self, serializer):
        if not _is_trainer_role(self.request.user):
            raise PermissionDenied("Only trainers can schedule live sessions.")
        serializer.save(trainer=self.request.user)

    def _assert_owner(self, session):
        user = self.request.user
        if session.trainer_id != user.id and not _is_admin(user):
            raise PermissionDenied("You do not own this session.")

    def perform_update(self, serializer):
        self._assert_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owner(instance)
        instance.delete()

    # -- student actions ---------------------------------------------------- #

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        """Register the current user; auto-waitlists past the registration limit."""
        session = self.get_object()
        if session.status in (
            LiveSession.Status.COMPLETED,
            LiveSession.Status.CANCELLED,
        ):
            raise ValidationError("This session is not open for registration.")

        limit = session.registration_limit
        active = session.registrations.exclude(
            status=SessionRegistration.Status.CANCELLED
        ).count()
        reg_status = (
            SessionRegistration.Status.WAITLISTED
            if limit and active >= limit
            else SessionRegistration.Status.REGISTERED
        )
        try:
            registration, created = SessionRegistration.objects.get_or_create(
                session=session,
                student=request.user,
                defaults={"status": reg_status},
            )
        except IntegrityError:
            raise ValidationError("Already registered for this session.")
        if not created and registration.status == SessionRegistration.Status.CANCELLED:
            registration.status = reg_status
            registration.save(update_fields=["status", "updated_at"])
        return Response(
            SessionRegistrationSerializer(registration, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """Mark the current user as joined and return the join URL."""
        session = self.get_object()
        registration = session.registrations.filter(student=request.user).first()
        if registration is None and getattr(request.user, "role", None) == "student":
            raise ValidationError("Register for this session before joining.")
        if registration and not registration.joined_at:
            registration.joined_at = timezone.now()
            registration.attended = True
            registration.save(update_fields=["joined_at", "attended", "updated_at"])
        return Response(
            {"join_url": session.join_url, "meeting_id": session.meeting_id}
        )

    @action(detail=True, methods=["post"], url_path="raise-doubt")
    def raise_doubt(self, request, pk=None):
        """Raise a doubt / raised hand during the session (PRD §3.5)."""
        session = self.get_object()
        text = (request.data.get("text") or "").strip()
        if not text:
            raise ValidationError({"text": "This field is required."})
        doubt = SessionDoubt.objects.create(
            session=session, student=request.user, text=text
        )
        return Response(
            SessionDoubtSerializer(doubt).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def doubts(self, request, pk=None):
        """List doubts for this session (own doubts for students; all for the
        owning trainer/admin)."""
        session = self.get_object()
        qs = session.doubts.select_related("student")
        user = request.user
        if not (session.trainer_id == user.id or _is_admin(user)):
            qs = qs.filter(student=user)
        return Response(SessionDoubtSerializer(qs, many=True).data)


class SessionRegistrationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """The current user's session registrations. ``POST .../{id}/cancel/`` to
    cancel and promote the next waitlisted student."""

    serializer_class = SessionRegistrationSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return SessionRegistration.objects.select_related(
            "session", "session__trainer"
        ).filter(student=self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        registration = self.get_object()
        registration.status = SessionRegistration.Status.CANCELLED
        registration.save(update_fields=["status", "updated_at"])
        # Promote the earliest waitlisted registrant, if any.
        promoted = (
            SessionRegistration.objects.filter(
                session=registration.session,
                status=SessionRegistration.Status.WAITLISTED,
            )
            .order_by("registered_at")
            .first()
        )
        if promoted:
            promoted.status = SessionRegistration.Status.REGISTERED
            promoted.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(registration).data)


class SessionDoubtViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Doubts raised in sessions. Filter by ``?session=<id>``. Students see their
    own; the owning trainer/admin can see all and PATCH ``status`` to answered."""

    serializer_class = SessionDoubtSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "update": TRAINER_WRITE,
        "partial_update": TRAINER_WRITE,
    }

    def get_queryset(self):
        qs = SessionDoubt.objects.select_related("student", "session__trainer")
        user = self.request.user
        if not _is_trainer_role(user):
            qs = qs.filter(student=user)
        elif not _is_admin(user):
            # Trainers see doubts in their own sessions (and their own asked).
            qs = qs.filter(Q(session__trainer=user) | Q(student=user))
        return _filter_by(qs, self.request, "session", "session_id")

    def perform_update(self, serializer):
        doubt = serializer.instance
        user = self.request.user
        if doubt.session.trainer_id != user.id and not _is_admin(user):
            raise PermissionDenied("Only the session trainer can update a doubt.")
        serializer.save()


class TrainerAvailabilityViewSet(viewsets.ModelViewSet):
    """A trainer's bookable calendar slots (PRD §3.6). Students filter by
    ``?trainer=<id>`` and ``?available=true`` to find open slots; trainers manage
    their own slots."""

    serializer_class = TrainerAvailabilitySerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "create": TRAINER_WRITE,
        "update": TRAINER_WRITE,
        "partial_update": TRAINER_WRITE,
        "destroy": TRAINER_WRITE,
    }

    def get_queryset(self):
        qs = TrainerAvailability.objects.select_related("trainer")
        params = self.request.query_params
        qs = _filter_by(qs, self.request, "trainer", "trainer_id")
        if params.get("available", "").lower() in ("1", "true", "yes"):
            qs = qs.filter(is_booked=False, start__gte=timezone.now())
        if params.get("mine", "").lower() in ("1", "true", "yes"):
            qs = qs.filter(trainer=self.request.user)
        return qs

    def perform_create(self, serializer):
        if not _is_trainer_role(self.request.user):
            raise PermissionDenied("Only trainers can publish availability.")
        serializer.save(trainer=self.request.user)

    def _assert_owner(self, slot):
        user = self.request.user
        if slot.trainer_id != user.id and not _is_admin(user):
            raise PermissionDenied("You do not own this slot.")

    def perform_update(self, serializer):
        self._assert_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owner(instance)
        instance.delete()


class IndividualBookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """1:1 bookings (PRD §3.6). A student books a trainer's open slot; the slot is
    marked booked. Students see bookings they made; trainers see bookings
    received."""

    serializer_class = IndividualBookingSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES
    api_roles_by_action = {"create": ("student",)}

    def get_queryset(self):
        user = self.request.user
        qs = IndividualBooking.objects.select_related("trainer", "student")
        if _is_admin(user):
            return qs
        return qs.filter(Q(student=user) | Q(trainer=user))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trainer = serializer.validated_data["trainer"]
        start = serializer.validated_data.get("start")
        if trainer.id == request.user.id:
            raise ValidationError("You cannot book a session with yourself.")

        slot = None
        if start is not None:
            slot = TrainerAvailability.objects.filter(
                trainer=trainer, start=start, is_booked=False
            ).first()
            if slot is None:
                raise ValidationError(
                    "No open availability for this trainer at that time."
                )
        booking = serializer.save(
            student=request.user, status=IndividualBooking.Status.PENDING
        )
        if slot:
            slot.is_booked = True
            slot.save(update_fields=["is_booked", "updated_at"])
        return Response(
            self.get_serializer(booking).data, status=status.HTTP_201_CREATED
        )
