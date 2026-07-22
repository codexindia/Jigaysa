"""Checkout, pricing and fulfilment logic (PRD §3.3, §3.4, §3.13).

Kept out of the views so the money math (line items → discount → GST → total) and
the fulfilment side-effects (paid enrollment, subscription activation) live in one
auditable place. A real gateway (Razorpay/Stripe/UPI) slots into ``pay_order`` —
for now payment is confirmed synchronously (``mock`` gateway) so the rest of the
student flow works end to end.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from courses.models import Course
from payments.models import (
    Coupon,
    CoursePrice,
    Invoice,
    Order,
    OrderItem,
    Payment,
    PricingPlan,
    Subscription,
)

# GST rate applied to the discounted subtotal (PRD §3.3 Taxes/GST).
GST_PERCENT = Decimal("18")

_PERIOD_DAYS = {
    PricingPlan.BillingPeriod.MONTHLY: 30,
    PricingPlan.BillingPeriod.QUARTERLY: 90,
    PricingPlan.BillingPeriod.ANNUAL: 365,
}


def money(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resolve_line_item(item_type, object_id):
    """Resolve a requested line item to (title, amount, ref). Amount is taken
    from the server-side price, never the client."""
    if item_type == OrderItem.ItemType.COURSE:
        course = Course.objects.filter(pk=object_id).first()
        if course is None:
            raise ValidationError(f"Course {object_id} not found.")
        if course.is_free:
            raise ValidationError(f"'{course.title}' is free — just enroll.")
        price = (
            CoursePrice.objects.filter(
                course=course, pricing_type=CoursePrice.PricingType.ONE_TIME
            )
            .order_by("amount")
            .first()
        )
        if price is None:
            raise ValidationError(f"'{course.title}' is not purchasable yet.")
        amount = price.amount - price.discount_amount
        if price.discount_percent:
            amount -= amount * price.discount_percent / 100
        return course.title, money(max(amount, 0)), course
    if item_type == OrderItem.ItemType.PLAN:
        plan = PricingPlan.objects.filter(pk=object_id, is_active=True).first()
        if plan is None:
            raise ValidationError(f"Plan {object_id} not found or inactive.")
        return plan.name, money(plan.price), plan
    raise ValidationError(f"Unsupported item type: {item_type}.")


def validate_coupon(code, subtotal, item_types):
    """Return an applicable ``Coupon`` for this cart or raise. ``item_types`` is
    the set of item types in the order, used to enforce coupon scope."""
    coupon = Coupon.objects.filter(code=code, is_active=True).first()
    if coupon is None:
        raise ValidationError("Invalid or inactive coupon.")
    now = timezone.now()
    if coupon.valid_from and now < coupon.valid_from:
        raise ValidationError("This coupon is not active yet.")
    if coupon.valid_to and now > coupon.valid_to:
        raise ValidationError("This coupon has expired.")
    if coupon.max_redemptions and coupon.used_count >= coupon.max_redemptions:
        raise ValidationError("This coupon has been fully redeemed.")
    if subtotal < coupon.min_amount:
        raise ValidationError(
            f"Order must be at least {coupon.min_amount} to use this coupon."
        )
    if coupon.scope == Coupon.Scope.COURSE and OrderItem.ItemType.COURSE not in item_types:
        raise ValidationError("This coupon only applies to course purchases.")
    if coupon.scope == Coupon.Scope.PLAN and OrderItem.ItemType.PLAN not in item_types:
        raise ValidationError("This coupon only applies to plan purchases.")
    return coupon


def coupon_discount(coupon, subtotal) -> Decimal:
    if coupon is None:
        return money(0)
    if coupon.discount_type == Coupon.DiscountType.PERCENT:
        return money(min(subtotal, subtotal * coupon.value / 100))
    return money(min(subtotal, coupon.value))


def quote(items, coupon_code=None):
    """Price a cart without persisting: returns the resolved items + totals."""
    if not items:
        raise ValidationError("An order needs at least one item.")
    resolved = []
    subtotal = Decimal("0")
    item_types = set()
    for item in items:
        title, amount, ref = resolve_line_item(item["item_type"], item["object_id"])
        resolved.append(
            {"item_type": item["item_type"], "object_id": item["object_id"],
             "title": title, "amount": amount, "ref": ref}
        )
        subtotal += amount
        item_types.add(item["item_type"])

    coupon = None
    discount = money(0)
    if coupon_code:
        coupon = validate_coupon(coupon_code, subtotal, item_types)
        discount = coupon_discount(coupon, subtotal)

    taxable = subtotal - discount
    gst = money(taxable * GST_PERCENT / 100)
    total = money(taxable + gst)
    return {
        "items": resolved,
        "coupon": coupon,
        "subtotal": money(subtotal),
        "discount": discount,
        "tax_gst": gst,
        "total": total,
    }


@transaction.atomic
def create_order(user, items, coupon_code=None):
    q = quote(items, coupon_code)
    order = Order.objects.create(
        user=user,
        status=Order.Status.PENDING,
        subtotal=q["subtotal"],
        discount=q["discount"],
        tax_gst=q["tax_gst"],
        total=q["total"],
        coupon=q["coupon"],
    )
    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            item_type=it["item_type"],
            object_id=it["object_id"],
            title=it["title"],
            amount=it["amount"],
        )
        for it in q["items"]
    )
    return order


def _next_invoice_number():
    year = timezone.now().year
    seq = Invoice.objects.filter(number__startswith=f"JIG-{year}-").count() + 1
    return f"JIG-{year}-{seq:04d}"


@transaction.atomic
def pay_order(order, gateway="mock", payment_method=None, gateway_payment_id=""):
    """Confirm payment for an order, generate its invoice and fulfil it.

    Idempotent: paying an already-paid order returns the existing payment.
    """
    if order.status == Order.Status.PAID:
        return order.payments.filter(status=Payment.Status.SUCCESS).first()
    if order.status == Order.Status.REFUNDED:
        raise ValidationError("This order was refunded and cannot be paid.")

    payment = Payment.objects.create(
        order=order,
        gateway=gateway if gateway != "mock" else Payment.Gateway.RAZORPAY,
        gateway_payment_id=gateway_payment_id or f"mock_{order.pk}_{timezone.now():%H%M%S}",
        amount=order.total,
        method=(payment_method.type if payment_method else "mock"),
        status=Payment.Status.SUCCESS,
        paid_at=timezone.now(),
    )
    order.status = Order.Status.PAID
    order.save(update_fields=["status", "updated_at"])

    Invoice.objects.create(
        order=order,
        number=_next_invoice_number(),
        user=order.user,
        description=", ".join(i.title for i in order.items.all())[:255],
        amount=order.subtotal - order.discount,
        gst_amount=order.tax_gst,
        status=Invoice.Status.PAID,
        issued_date=timezone.now().date(),
    )
    if order.coupon_id:
        Coupon.objects.filter(pk=order.coupon_id).update(
            used_count=order.coupon.used_count + 1
        )
    _fulfil_order(order)
    return payment


def _fulfil_order(order):
    """Grant what the student paid for: enrollments and/or a subscription."""
    from courses.views import _create_enrollment  # lazy: avoid app-load cycle
    from courses.models import Enrollment

    for item in order.items.all():
        if item.item_type == OrderItem.ItemType.COURSE:
            course = Course.objects.filter(pk=item.object_id).first()
            if course and not Enrollment.objects.filter(
                student=order.user, course=course
            ).exists():
                enrollment = _create_enrollment(student=order.user, course=course)
                Enrollment.objects.filter(pk=enrollment.pk).update(
                    source=Enrollment.Source.PURCHASE, order=order
                )
        elif item.item_type == OrderItem.ItemType.PLAN:
            _activate_subscription(order, item.object_id)


def _activate_subscription(order, plan_id):
    plan = PricingPlan.objects.filter(pk=plan_id).first()
    if plan is None:
        return
    now = timezone.now()
    days = _PERIOD_DAYS.get(plan.billing_period, 30)
    Subscription.objects.update_or_create(
        user=order.user,
        plan=plan,
        defaults={
            "status": Subscription.Status.ACTIVE,
            "current_period_start": now,
            "current_period_end": now + timedelta(days=days),
        },
    )
