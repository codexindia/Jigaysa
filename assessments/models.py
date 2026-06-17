"""Quizzes, assignments, submissions and grading (PRD §3.12).

Quiz and assignment are unified under ``Assessment`` + ``Submission`` so both the
student attempt flow and the trainer authoring/grading flow share one schema.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Assessment(TimeStampedModel):
    """A quiz or assignment attached to a course/lesson (PRD §3.12)."""

    class AssessmentType(models.TextChoices):
        QUIZ = "quiz", "Quiz"
        ASSIGNMENT = "assignment", "Assignment"
        CODING = "coding", "Coding test"
        DESCRIPTIVE = "descriptive", "Descriptive"

    class GradingType(models.TextChoices):
        AUTO = "auto", "Automated"
        MANUAL = "manual", "Manual"
        RUBRIC = "rubric", "Rubric"

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="assessments"
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lesson_assessments",
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessments_authored",
    )
    title = models.CharField(max_length=255)
    assessment_type = models.CharField(
        max_length=20, choices=AssessmentType.choices, default=AssessmentType.QUIZ
    )
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=0)
    pass_percent = models.PositiveIntegerField(default=0)  # 0-100
    max_attempts = models.PositiveIntegerField(default=1)
    available_from = models.DateTimeField(null=True, blank=True)
    available_to = models.DateTimeField(null=True, blank=True)
    grading_type = models.CharField(
        max_length=20, choices=GradingType.choices, default=GradingType.AUTO
    )
    is_published = models.BooleanField(default=False)
    total_questions = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Question(TimeStampedModel):
    """A question in an assessment (PRD §3.12 MCQ/coding/descriptive)."""

    class QuestionType(models.TextChoices):
        MCQ = "mcq", "Single choice"
        MULTI = "multi", "Multiple choice"
        DESCRIPTIVE = "descriptive", "Descriptive"
        CODING = "coding", "Coding"
        FILE = "file", "File upload"

    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="questions"
    )
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ
    )
    text = models.TextField()
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)  # e.g. coding test-cases

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.assessment} · Q{self.order}"


class Choice(TimeStampedModel):
    """An option for an MCQ/multi question."""

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class Submission(TimeStampedModel):
    """A student's attempt at an assessment (Assessments To-do/Passed/Review)."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    enrollment = models.ForeignKey(
        "courses.Enrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    attempt_no = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    percent = models.PositiveIntegerField(default=0)  # 0-100
    passed = models.BooleanField(default=False)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    # Trainer review (manual/rubric grading)
    grader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "student", "attempt_no"],
                name="unique_assessment_attempt",
            )
        ]

    def __str__(self):
        return f"{self.student} · {self.assessment} #{self.attempt_no}"


class Answer(TimeStampedModel):
    """A student's answer to one question within a submission."""

    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    selected_choices = models.ManyToManyField(
        Choice, blank=True, related_name="answers"
    )
    text_answer = models.TextField(blank=True)
    file = models.FileField(upload_to="submissions/", blank=True)
    code = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    points_awarded = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    def __str__(self):
        return f"Answer to {self.question} in {self.submission}"


class Rubric(TimeStampedModel):
    """A grading rubric for an assessment (PRD §3.12 grading rubric)."""

    assessment = models.OneToOneField(
        Assessment, on_delete=models.CASCADE, related_name="rubric"
    )
    criteria = models.JSONField(default=list, blank=True)  # [{name, max_points}]

    def __str__(self):
        return f"Rubric<{self.assessment}>"
