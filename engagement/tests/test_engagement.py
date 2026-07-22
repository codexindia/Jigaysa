import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from engagement.models import DiscussionReply, DiscussionThread

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@example.com", password="StrongPass123!", role=Role.STUDENT
    )


@pytest.fixture
def other():
    return User.objects.create_user(
        email="o@example.com", password="StrongPass123!", role=Role.STUDENT
    )


def test_thread_create_reply_and_accept(student, other):
    api = APIClient()
    api.force_authenticate(student)
    thread_resp = api.post(
        "/api/v1/discussion-threads/",
        {"title": "loc vs iloc?", "body": "help", "scope": "community"},
        format="json",
    )
    assert thread_resp.status_code == status.HTTP_201_CREATED
    thread_id = thread_resp.data["id"]

    # Another student replies.
    api.force_authenticate(other)
    reply_resp = api.post(
        "/api/v1/discussion-replies/",
        {"thread": thread_id, "body": "loc is label-based"},
        format="json",
    )
    assert reply_resp.status_code == status.HTTP_201_CREATED
    reply_id = reply_resp.data["id"]
    assert DiscussionThread.objects.get(id=thread_id).reply_count == 1

    # The thread author accepts the answer → thread resolved.
    api.force_authenticate(student)
    accept = api.post(f"/api/v1/discussion-replies/{reply_id}/accept/")
    assert accept.status_code == status.HTTP_200_OK
    assert DiscussionReply.objects.get(id=reply_id).is_accepted_answer is True
    assert DiscussionThread.objects.get(id=thread_id).status == "resolved"


def test_non_author_cannot_accept(student, other):
    thread = DiscussionThread.objects.create(
        author=student, title="q", scope=DiscussionThread.Scope.COMMUNITY
    )
    reply = DiscussionReply.objects.create(thread=thread, author=other, body="a")
    api = APIClient()
    api.force_authenticate(other)
    resp = api.post(f"/api/v1/discussion-replies/{reply.id}/accept/")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_community_profile_me(student):
    api = APIClient()
    api.force_authenticate(student)
    resp = api.get("/api/v1/community-profile/me/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["points"] == 0
    assert resp.data["badges"] == []
