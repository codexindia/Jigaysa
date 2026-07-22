from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from courses.models import Category, Course, Enrollment
from payments.models import Coupon, CoursePrice, Invoice, PricingPlan, Subscription

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
def paid_course(trainer):
    course = Course.objects.create(
        title="React Pro", trainer=trainer, is_free=False,
        category=Category.objects.create(name="Web"),
        status=Course.Status.PUBLISHED,
    )
    CoursePrice.objects.create(
        course=course, pricing_type=CoursePrice.PricingType.ONE_TIME, amount=1000
    )
    return course


@pytest.fixture
def plan():
    return PricingPlan.objects.create(
        name="Pro", slug="pro", price=499,
        billing_period=PricingPlan.BillingPeriod.MONTHLY,
    )


def _api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_checkout_computes_gst_and_total(student, paid_course):
    api = _api(student)
    resp = api.post(
        "/api/v1/orders/",
        {"items": [{"item_type": "course", "object_id": paid_course.id}]},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert Decimal(resp.data["subtotal"]) == Decimal("1000.00")
    assert Decimal(resp.data["tax_gst"]) == Decimal("180.00")  # 18%
    assert Decimal(resp.data["total"]) == Decimal("1180.00")
    assert resp.data["status"] == "pending"


def test_pay_order_enrolls_and_invoices(student, paid_course):
    api = _api(student)
    order = api.post(
        "/api/v1/orders/",
        {"items": [{"item_type": "course", "object_id": paid_course.id}]},
        format="json",
    ).data
    pay = api.post(f"/api/v1/orders/{order['id']}/pay/", {}, format="json")
    assert pay.status_code == status.HTTP_200_OK
    assert pay.data["status"] == "paid"
    enrollment = Enrollment.objects.get(student=student, course=paid_course)
    assert enrollment.source == Enrollment.Source.PURCHASE
    assert Invoice.objects.filter(user=student, status="paid").exists()


def test_pay_is_idempotent(student, paid_course):
    api = _api(student)
    order = api.post(
        "/api/v1/orders/",
        {"items": [{"item_type": "course", "object_id": paid_course.id}]},
        format="json",
    ).data
    api.post(f"/api/v1/orders/{order['id']}/pay/", {}, format="json")
    api.post(f"/api/v1/orders/{order['id']}/pay/", {}, format="json")
    assert Enrollment.objects.filter(student=student, course=paid_course).count() == 1


def test_coupon_validate_applies_discount(student, paid_course):
    Coupon.objects.create(
        code="SAVE10", discount_type=Coupon.DiscountType.PERCENT, value=10,
        scope=Coupon.Scope.ALL, is_active=True,
    )
    api = _api(student)
    resp = api.post(
        "/api/v1/coupons/validate/",
        {"code": "SAVE10", "items": [{"item_type": "course", "object_id": paid_course.id}]},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert Decimal(resp.data["discount"]) == Decimal("100.00")
    # (1000 - 100) * 1.18 = 1062.00
    assert Decimal(resp.data["total"]) == Decimal("1062.00")


def test_plan_checkout_activates_subscription(student, plan):
    api = _api(student)
    order = api.post(
        "/api/v1/orders/",
        {"items": [{"item_type": "plan", "object_id": plan.id}]},
        format="json",
    ).data
    api.post(f"/api/v1/orders/{order['id']}/pay/", {}, format="json")
    sub = Subscription.objects.get(user=student, plan=plan)
    assert sub.status == Subscription.Status.ACTIVE
    assert sub.current_period_end is not None


def test_free_course_checkout_rejected(student, trainer):
    free = Course.objects.create(
        title="Free 101", trainer=trainer, is_free=True,
        category=Category.objects.create(name="Free"),
        status=Course.Status.PUBLISHED,
    )
    api = _api(student)
    resp = api.post(
        "/api/v1/orders/",
        {"items": [{"item_type": "course", "object_id": free.id}]},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_orders_are_user_scoped(student, paid_course):
    other = User.objects.create_user(
        email="o@example.com", password="StrongPass123!", role=Role.STUDENT
    )
    _api(other).post(
        "/api/v1/orders/",
        {"items": [{"item_type": "course", "object_id": paid_course.id}]},
        format="json",
    )
    resp = _api(student).get("/api/v1/orders/")
    assert resp.data["count"] == 0
