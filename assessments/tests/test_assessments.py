import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from assessments.models import Assessment, Choice, Question, Submission
from courses.models import Category, Course

pytestmark = pytest.mark.django_db


@pytest.fixture
def trainer():
    return User.objects.create_user(
        email="trainer@example.com", password="StrongPass123!", role=Role.TRAINER
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


@pytest.fixture
def quiz(trainer):
    course = Course.objects.create(
        title="DS", trainer=trainer, category=Category.objects.create(name="Data")
    )
    assessment = Assessment.objects.create(
        course=course,
        trainer=trainer,
        title="Checkpoint",
        assessment_type=Assessment.AssessmentType.QUIZ,
        pass_percent=50,
        max_attempts=1,
        is_published=True,
    )
    q1 = Question.objects.create(
        assessment=assessment, text="2+2?", question_type=Question.QuestionType.MCQ, points=1
    )
    Choice.objects.create(question=q1, text="4", is_correct=True)
    Choice.objects.create(question=q1, text="5", is_correct=False)
    q2 = Question.objects.create(
        assessment=assessment, text="Sky?", question_type=Question.QuestionType.MCQ, points=1
    )
    Choice.objects.create(question=q2, text="Blue", is_correct=True)
    Choice.objects.create(question=q2, text="Green", is_correct=False)
    return assessment


def _correct_choice(question):
    return question.choices.get(is_correct=True).id


def test_choices_hide_answer_key_from_students(quiz, student):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.get(f"/api/v1/assessments/{quiz.id}/")
    assert resp.status_code == status.HTTP_200_OK
    first_choice = resp.data["questions"][0]["choices"][0]
    assert "is_correct" not in first_choice


def test_submit_autogrades_and_passes(quiz, student):
    api = APIClient()
    api.force_authenticate(student)
    questions = list(quiz.questions.all())
    payload = {
        "answers": [
            {"question": q.id, "selected_choices": [_correct_choice(q)]}
            for q in questions
        ]
    }
    resp = api.post(
        f"/api/v1/assessments/{quiz.id}/submit/", payload, format="json"
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["percent"] == 100
    assert resp.data["passed"] is True
    assert resp.data["status"] == Submission.Status.PASSED


def test_submit_partial_fails(quiz, student):
    api = APIClient()
    api.force_authenticate(student)
    questions = list(quiz.questions.all())
    wrong = questions[0].choices.get(is_correct=False).id
    payload = {
        "answers": [
            {"question": questions[0].id, "selected_choices": [wrong]},
            {"question": questions[1].id, "selected_choices": [_correct_choice(questions[1])]},
        ]
    }
    resp = api.post(f"/api/v1/assessments/{quiz.id}/submit/", payload, format="json")
    assert resp.data["percent"] == 50
    # pass_percent is 50, so exactly 50 passes
    assert resp.data["passed"] is True


def test_max_attempts_enforced(quiz, student):
    api = APIClient()
    api.force_authenticate(student)
    q = quiz.questions.first()
    payload = {"answers": [{"question": q.id, "selected_choices": [_correct_choice(q)]}]}
    first = api.post(f"/api/v1/assessments/{quiz.id}/submit/", payload, format="json")
    assert first.status_code == status.HTTP_201_CREATED
    second = api.post(f"/api/v1/assessments/{quiz.id}/submit/", payload, format="json")
    assert second.status_code == status.HTTP_400_BAD_REQUEST


def test_descriptive_holds_for_manual_grade(trainer, student):
    course = Course.objects.create(
        title="Writing", trainer=trainer,
        category=Category.objects.create(name="Lang"),
    )
    assessment = Assessment.objects.create(
        course=course, trainer=trainer, title="Essay",
        assessment_type=Assessment.AssessmentType.DESCRIPTIVE,
        grading_type=Assessment.GradingType.MANUAL,
        pass_percent=50, max_attempts=3, is_published=True,
    )
    q = Question.objects.create(
        assessment=assessment, text="Discuss.",
        question_type=Question.QuestionType.DESCRIPTIVE, points=10,
    )
    api = APIClient()
    api.force_authenticate(student)
    resp = api.post(
        f"/api/v1/assessments/{assessment.id}/submit/",
        {"answers": [{"question": q.id, "text_answer": "My essay."}]},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["status"] == Submission.Status.SUBMITTED
    submission_id = resp.data["id"]

    # Trainer grades it.
    api.force_authenticate(trainer)
    graded = api.post(
        f"/api/v1/submissions/{submission_id}/grade/",
        {"score": "8", "percent": 80, "feedback": "Good"},
        format="json",
    )
    assert graded.status_code == status.HTTP_200_OK
    assert graded.data["passed"] is True
    assert graded.data["status"] == Submission.Status.PASSED
