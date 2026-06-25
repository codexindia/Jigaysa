"""Serializers for the Course Management Module (PRD §3.2, §3.12).

Read and write shapes are split where they diverge: catalog cards stay light
(``CourseListSerializer``), the detail/authoring view nests structure, and a
dedicated write serializer keeps trainer-controlled fields server-side.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from courses.models import (
    Batch,
    Category,
    Course,
    CourseReview,
    Enrollment,
    Lesson,
    LessonProgress,
    LessonResource,
    Module,
    Tag,
)

User = get_user_model()


class TrainerMiniSerializer(serializers.ModelSerializer):
    """Compact trainer card embedded in course payloads."""

    class Meta:
        model = User
        fields = ("id", "full_name", "email")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "icon")
        read_only_fields = ("slug",)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")
        read_only_fields = ("slug",)


class LessonResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonResource
        fields = ("id", "lesson", "title", "url", "file", "resource_type")


class LessonSerializer(serializers.ModelSerializer):
    """Full lesson shape used by trainers when authoring."""

    resources = LessonResourceSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "module",
            "title",
            "content_type",
            "order",
            "duration_minutes",
            "video_url",
            "content",
            "is_preview",
            "assessment",
            "live_session",
            "resources",
        )


class LessonPlayerSerializer(serializers.ModelSerializer):
    """Student-facing lesson shape. Gated content (video/body) is hidden unless
    the requester may access it (preview lesson, enrolled, owner or admin)."""

    locked = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    resources = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            "id",
            "module",
            "title",
            "content_type",
            "order",
            "duration_minutes",
            "is_preview",
            "locked",
            "video_url",
            "content",
            "resources",
        )

    def _accessible(self, obj):
        if obj.is_preview:
            return True
        return bool(self.context.get("has_access"))

    def get_locked(self, obj):
        return not self._accessible(obj)

    def get_video_url(self, obj):
        return obj.video_url if self._accessible(obj) else ""

    def get_content(self, obj):
        return obj.content if self._accessible(obj) else ""

    def get_resources(self, obj):
        if not self._accessible(obj):
            return []
        return LessonResourceSerializer(obj.resources.all(), many=True).data


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ("id", "course", "title", "summary", "order", "lessons")


class ModulePlayerSerializer(serializers.ModelSerializer):
    lessons = LessonPlayerSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ("id", "title", "summary", "order", "lessons")


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight catalog card."""

    trainer = TrainerMiniSerializer(read_only=True)
    category = serializers.StringRelatedField()

    class Meta:
        model = Course
        fields = (
            "id",
            "slug",
            "title",
            "subtitle",
            "trainer",
            "category",
            "course_type",
            "skill_level",
            "language",
            "duration_minutes",
            "thumbnail",
            "is_free",
            "status",
            "rating_avg",
            "rating_count",
            "enrolled_count",
            "published_at",
        )


class CourseDetailSerializer(serializers.ModelSerializer):
    """Full course read shape with embedded taxonomy and trainer."""

    trainer = TrainerMiniSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    module_count = serializers.IntegerField(
        source="modules.count", read_only=True
    )

    class Meta:
        model = Course
        fields = (
            "id",
            "slug",
            "title",
            "subtitle",
            "description",
            "trainer",
            "organization",
            "category",
            "tags",
            "course_type",
            "skill_level",
            "language",
            "duration_minutes",
            "thumbnail",
            "intro_video_url",
            "prerequisites",
            "status",
            "visibility",
            "is_free",
            "rating_avg",
            "rating_count",
            "enrolled_count",
            "module_count",
            "published_at",
            "created_at",
            "updated_at",
        )


class CourseWriteSerializer(serializers.ModelSerializer):
    """Create/update shape. ``trainer`` is taken from the request, not the body;
    ``status``/``published_at`` are controlled via the publish action."""

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "subtitle",
            "description",
            "organization",
            "category",
            "tags",
            "course_type",
            "skill_level",
            "language",
            "duration_minutes",
            "thumbnail",
            "intro_video_url",
            "prerequisites",
            "visibility",
            "is_free",
        )

    def create(self, validated_data):
        validated_data["trainer"] = self.context["request"].user
        return super().create(validated_data)


class BatchSerializer(serializers.ModelSerializer):
    trainer = TrainerMiniSerializer(read_only=True)
    trainer_id = serializers.PrimaryKeyRelatedField(
        source="trainer",
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Batch
        fields = (
            "id",
            "course",
            "name",
            "trainer",
            "trainer_id",
            "organization",
            "start_date",
            "end_date",
            "capacity",
            "enrolled_count",
            "schedule",
        )
        read_only_fields = ("enrolled_count",)


class EnrollmentSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = (
            "id",
            "student",
            "course",
            "batch",
            "status",
            "source",
            "order",
            "progress_pct",
            "enrolled_at",
            "completed_at",
        )
        read_only_fields = fields


class EnrollmentCreateSerializer(serializers.Serializer):
    """Self-enroll into a course. Paid courses require the payments module
    (pending) — only free courses can be enrolled directly for now."""

    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    batch = serializers.PrimaryKeyRelatedField(
        queryset=Batch.objects.all(), required=False, allow_null=True
    )

    def validate_course(self, course):
        if course.status != Course.Status.PUBLISHED:
            raise serializers.ValidationError("Course is not open for enrollment.")
        user = self.context["request"].user
        if Enrollment.objects.filter(student=user, course=course).exists():
            raise serializers.ValidationError("Already enrolled in this course.")
        if not course.is_free:
            raise serializers.ValidationError(
                "This is a paid course. Checkout via the payments module is "
                "required (not yet available)."
            )
        return course


class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = (
            "id",
            "enrollment",
            "lesson",
            "status",
            "watch_pct",
            "time_spent_seconds",
            "last_position_seconds",
            "completed_at",
        )
        read_only_fields = ("completed_at",)


class CourseReviewSerializer(serializers.ModelSerializer):
    student = TrainerMiniSerializer(read_only=True)

    class Meta:
        model = CourseReview
        fields = (
            "id",
            "course",
            "student",
            "rating",
            "comment",
            "created_at",
        )
        read_only_fields = ("student", "created_at")

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
