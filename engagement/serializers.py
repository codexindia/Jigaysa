"""Serializers for the discussion forum, community feed and gamification (§3.12)."""

from rest_framework import serializers

from engagement.models import (
    Badge,
    CommunityPost,
    CommunityProfile,
    DiscussionReply,
    DiscussionThread,
    UserBadge,
)


class AuthorMiniSerializer(serializers.Serializer):
    """Compact author card (works for any user)."""

    id = serializers.IntegerField()
    full_name = serializers.CharField()
    role = serializers.CharField()


class DiscussionReplySerializer(serializers.ModelSerializer):
    author = AuthorMiniSerializer(read_only=True)

    class Meta:
        model = DiscussionReply
        fields = (
            "id",
            "thread",
            "author",
            "parent",
            "body",
            "is_accepted_answer",
            "created_at",
        )
        read_only_fields = ("author", "is_accepted_answer", "created_at")


class DiscussionThreadSerializer(serializers.ModelSerializer):
    author = AuthorMiniSerializer(read_only=True)

    class Meta:
        model = DiscussionThread
        fields = (
            "id",
            "course",
            "batch",
            "author",
            "title",
            "body",
            "scope",
            "status",
            "is_pinned",
            "reply_count",
            "last_activity_at",
            "created_at",
        )
        read_only_fields = (
            "author",
            "status",
            "is_pinned",
            "reply_count",
            "last_activity_at",
            "created_at",
        )


class DiscussionThreadDetailSerializer(DiscussionThreadSerializer):
    replies = DiscussionReplySerializer(many=True, read_only=True)

    class Meta(DiscussionThreadSerializer.Meta):
        fields = DiscussionThreadSerializer.Meta.fields + ("replies",)


class CommunityPostSerializer(serializers.ModelSerializer):
    author = AuthorMiniSerializer(read_only=True)

    class Meta:
        model = CommunityPost
        fields = (
            "id",
            "author",
            "body",
            "post_type",
            "likes_count",
            "created_at",
        )
        read_only_fields = ("author", "likes_count", "created_at")


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("id", "name", "slug", "icon", "description")


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ("id", "badge", "earned_at")


class CommunityProfileSerializer(serializers.ModelSerializer):
    badges = serializers.SerializerMethodField()

    class Meta:
        model = CommunityProfile
        fields = ("points", "level", "badges_count", "badges")

    def get_badges(self, obj):
        earned = UserBadge.objects.select_related("badge").filter(user=obj.user)
        return UserBadgeSerializer(earned, many=True).data
