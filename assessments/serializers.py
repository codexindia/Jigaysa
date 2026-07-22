"""Serializers for quizzes, assignments, submissions and grading (PRD §3.12).

Choice correctness is hidden from students: ``ChoiceSerializer`` never exposes
``is_correct``, and question payloads for the attempt flow omit answer keys.
"""

from rest_framework import serializers

from assessments.models import (
    Answer,
    Assessment,
    Choice,
    Question,
    Rubric,
    Submission,
)


class ChoiceSerializer(serializers.ModelSerializer):
    """Student-facing choice — never reveals the answer key."""

    class Meta:
        model = Choice
        fields = ("id", "text", "order")


class QuestionSerializer(serializers.ModelSerializer):
    """Student-facing question shape (no ``is_correct`` on choices)."""

    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "assessment",
            "question_type",
            "text",
            "points",
            "order",
            "choices",
        )


class RubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rubric
        fields = ("id", "assessment", "criteria")


class AssessmentSerializer(serializers.ModelSerializer):
    """List/detail card. Questions are embedded on retrieve via the view."""

    class Meta:
        model = Assessment
        fields = (
            "id",
            "course",
            "lesson",
            "trainer",
            "title",
            "assessment_type",
            "description",
            "time_limit_minutes",
            "pass_percent",
            "max_attempts",
            "available_from",
            "available_to",
            "grading_type",
            "is_published",
            "total_questions",
            "created_at",
        )
        read_only_fields = ("trainer", "total_questions")


class AssessmentDetailSerializer(AssessmentSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(AssessmentSerializer.Meta):
        fields = AssessmentSerializer.Meta.fields + ("questions",)


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = (
            "id",
            "question",
            "selected_choices",
            "text_answer",
            "code",
            "file_key",
            "is_correct",
            "points_awarded",
        )
        read_only_fields = ("is_correct", "points_awarded")


class SubmissionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = (
            "id",
            "assessment",
            "student",
            "enrollment",
            "attempt_no",
            "status",
            "started_at",
            "submitted_at",
            "score",
            "percent",
            "passed",
            "time_taken_seconds",
            "feedback",
            "graded_at",
            "answers",
        )
        read_only_fields = (
            "student",
            "attempt_no",
            "status",
            "started_at",
            "submitted_at",
            "score",
            "percent",
            "passed",
            "feedback",
            "graded_at",
        )


class AnswerInputSerializer(serializers.Serializer):
    """One answer within a submit payload."""

    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all())
    selected_choices = serializers.PrimaryKeyRelatedField(
        queryset=Choice.objects.all(), many=True, required=False
    )
    text_answer = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    # Object key from POST /api/v1/uploads/presign/ for assignment file answers.
    file_key = serializers.CharField(required=False, allow_blank=True, max_length=1024)


class SubmitSerializer(serializers.Serializer):
    """Payload to attempt an assessment: a list of per-question answers."""

    answers = AnswerInputSerializer(many=True)
    time_taken_seconds = serializers.IntegerField(required=False, min_value=0)


class GradeSerializer(serializers.Serializer):
    """Trainer manual-grade payload for descriptive/coding submissions."""

    score = serializers.DecimalField(max_digits=7, decimal_places=2)
    percent = serializers.IntegerField(min_value=0, max_value=100)
    feedback = serializers.CharField(required=False, allow_blank=True)
    passed = serializers.BooleanField(required=False)
