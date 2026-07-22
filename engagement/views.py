"""Discussion forum, community feed and gamification API (PRD §3.12).

Students open threads and reply (peer learning); the thread author or the course
trainer/an admin can mark a reply as the accepted answer, which resolves the
thread. Community posts back the feed; badges/points back the dashboard's
community card. Writes are owner-scoped; reads are open to authenticated users.
"""

from django.db.models import F, Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from engagement.models import (
    Badge,
    CommunityPost,
    CommunityProfile,
    DiscussionReply,
    DiscussionThread,
    UserBadge,
)
from engagement.serializers import (
    BadgeSerializer,
    CommunityPostSerializer,
    CommunityProfileSerializer,
    DiscussionReplySerializer,
    DiscussionThreadDetailSerializer,
    DiscussionThreadSerializer,
    UserBadgeSerializer,
)

ALL_ROLES = ("student", "trainer", "admin", "institution")


def _is_admin(user):
    return getattr(user, "role", None) == "admin"


def _filter_by(qs, request, param, field=None):
    value = request.query_params.get(param)
    if value:
        qs = qs.filter(**{field or param: value})
    return qs


class DiscussionThreadViewSet(viewsets.ModelViewSet):
    """Forum threads. Filter by ``?course=<id>``, ``?scope=course|community``,
    ``?status=open|resolved``, ``?q=<search>``. Any authenticated user can open a
    thread; only the author or an admin can edit/delete it."""

    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DiscussionThreadDetailSerializer
        return DiscussionThreadSerializer

    def get_queryset(self):
        qs = DiscussionThread.objects.select_related("author", "course").prefetch_related(
            "replies__author"
        )
        params = self.request.query_params
        qs = _filter_by(qs, self.request, "course", "course_id")
        qs = _filter_by(qs, self.request, "scope")
        qs = _filter_by(qs, self.request, "status")
        if params.get("q"):
            qs = qs.filter(
                Q(title__icontains=params["q"]) | Q(body__icontains=params["q"])
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(
            author=self.request.user, last_activity_at=timezone.now()
        )

    def _assert_owner(self, thread):
        user = self.request.user
        if thread.author_id != user.id and not _is_admin(user):
            raise PermissionDenied("You can only modify your own thread.")

    def perform_update(self, serializer):
        self._assert_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owner(instance)
        instance.delete()


class DiscussionReplyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Replies to a thread. Filter by ``?thread=<id>``. Creating a reply bumps
    the thread's activity and reply count."""

    serializer_class = DiscussionReplySerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        qs = DiscussionReply.objects.select_related("author", "thread")
        return _filter_by(qs, self.request, "thread", "thread_id")

    def perform_create(self, serializer):
        reply = serializer.save(author=self.request.user)
        thread = reply.thread
        DiscussionThread.objects.filter(pk=thread.pk).update(
            reply_count=thread.replies.count(),
            last_activity_at=timezone.now(),
        )

    def _assert_owner(self, reply):
        user = self.request.user
        if reply.author_id != user.id and not _is_admin(user):
            raise PermissionDenied("You can only modify your own reply.")

    def perform_update(self, serializer):
        self._assert_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owner(instance)
        thread = instance.thread
        instance.delete()
        DiscussionThread.objects.filter(pk=thread.pk).update(
            reply_count=thread.replies.count()
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Mark this reply as the accepted answer (thread author, course trainer
        or admin only). Resolves the thread."""
        reply = self.get_object()
        thread = reply.thread
        user = request.user
        is_trainer_owner = (
            thread.course is not None and thread.course.trainer_id == user.id
        )
        if not (thread.author_id == user.id or is_trainer_owner or _is_admin(user)):
            raise PermissionDenied(
                "Only the thread author, course trainer or an admin can accept an answer."
            )
        thread.replies.update(is_accepted_answer=False)
        reply.is_accepted_answer = True
        reply.save(update_fields=["is_accepted_answer", "updated_at"])
        DiscussionThread.objects.filter(pk=thread.pk).update(
            status=DiscussionThread.Status.RESOLVED
        )
        return Response(self.get_serializer(reply).data)


class CommunityPostViewSet(viewsets.ModelViewSet):
    """The community feed. Any authenticated user can post; only the author or an
    admin can edit/delete. ``POST .../{id}/like/`` bumps the like count."""

    serializer_class = CommunityPostSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return CommunityPost.objects.select_related("author")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def _assert_owner(self, post):
        user = self.request.user
        if post.author_id != user.id and not _is_admin(user):
            raise PermissionDenied("You can only modify your own post.")

    def perform_update(self, serializer):
        self._assert_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_owner(instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        post = self.get_object()
        CommunityPost.objects.filter(pk=post.pk).update(likes_count=F("likes_count") + 1)
        post.refresh_from_db(fields=["likes_count"])
        return Response({"likes_count": post.likes_count})


class BadgeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The catalog of earnable badges (read-only)."""

    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES


class CommunityProfileViewSet(viewsets.GenericViewSet):
    """The current user's gamification card (points, level, earned badges)."""

    serializer_class = CommunityProfileSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    @action(detail=False, methods=["get"])
    def me(self, request):
        profile, _ = CommunityProfile.objects.get_or_create(user=request.user)
        return Response(self.get_serializer(profile).data)

    @action(detail=False, methods=["get"])
    def my_badges(self, request):
        earned = UserBadge.objects.select_related("badge").filter(user=request.user)
        return Response(UserBadgeSerializer(earned, many=True).data)
