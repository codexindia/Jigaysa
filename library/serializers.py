"""Serializers for the Free / premium learning library (PRD §3.10)."""

from rest_framework import serializers

from library.models import LibraryBookmark, LibraryResource


class LibraryResourceSerializer(serializers.ModelSerializer):
    """Library card. ``author``/``category`` are shown by name; writes use ids."""

    author_name = serializers.CharField(source="author.full_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = LibraryResource
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "format",
            "category",
            "category_name",
            "author",
            "author_name",
            "course",
            "file_url",
            "video_url",
            "duration_minutes",
            "pages",
            "access_level",
            "views_count",
            "popularity_score",
            "thumbnail",
            "published_at",
            "is_bookmarked",
            "created_at",
        )
        read_only_fields = ("slug", "views_count", "popularity_score", "author")

    def get_is_bookmarked(self, obj):
        user = self.context.get("request").user if self.context.get("request") else None
        if not user or not user.is_authenticated:
            return False
        saved = getattr(obj, "_bookmarked_ids", None)
        if saved is not None:
            return obj.id in saved
        return obj.bookmarks.filter(user=user).exists()


class LibraryBookmarkSerializer(serializers.ModelSerializer):
    resource_detail = LibraryResourceSerializer(source="resource", read_only=True)

    class Meta:
        model = LibraryBookmark
        fields = ("id", "resource", "resource_detail", "saved_at")
        read_only_fields = ("saved_at",)
