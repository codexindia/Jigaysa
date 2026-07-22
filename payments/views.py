"""Payments API: pricing, checkout, invoices and subscriptions (§3.3/3.4/3.13).

Student flow: read plans/prices → ``POST /orders/`` (server prices the cart) →
``POST /orders/{id}/pay/`` (confirms payment, issues the invoice and grants the
paid course/subscription). Coupons can be previewed before checkout. Every
read is scoped to the current user; plans/prices/coupons are admin-authored.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Shown on every payments operation in Swagger so integrators aren't misled.
_MOCK_GATEWAY_NOTE = (
    "⚠️ MOCK gateway: payment is confirmed synchronously with a stub — no real "
    "Razorpay/Stripe/PayPal/UPI integration and no money moves yet. Checkout, "
    "GST invoicing, coupons and access-granting are fully functional."
)

from core.permissions import IsAdmin
from payments import services
from payments.models import (
    Coupon,
    CoursePrice,
    Invoice,
    Order,
    PaymentMethod,
    PricingPlan,
    Subscription,
)
from payments.serializers import (
    CheckoutSerializer,
    CouponSerializer,
    CouponValidateSerializer,
    CoursePriceSerializer,
    InvoiceSerializer,
    OrderSerializer,
    PaymentMethodSerializer,
    PaySerializer,
    PricingPlanSerializer,
    SubscriptionSerializer,
)

ALL_ROLES = ("student", "trainer", "admin", "institution")
ADMIN_ONLY = ("admin",)


def _filter_by(qs, request, param, field=None):
    value = request.query_params.get(param)
    if value:
        qs = qs.filter(**{field or param: value})
    return qs


class PricingPlanViewSet(viewsets.ModelViewSet):
    """Platform-access plans (PRD §3.4). Anyone reads; admins author."""

    queryset = PricingPlan.objects.all()
    serializer_class = PricingPlanSerializer
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "create": ADMIN_ONLY, "update": ADMIN_ONLY,
        "partial_update": ADMIN_ONLY, "destroy": ADMIN_ONLY,
    }

    def get_queryset(self):
        qs = PricingPlan.objects.all()
        if self.action == "list" and self.request.query_params.get("active") != "all":
            qs = qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdmin()]


class CoursePriceViewSet(viewsets.ModelViewSet):
    """Course price options (PRD §3.3). Filter by ``?course=<id>``."""

    serializer_class = CoursePriceSerializer
    api_roles = ALL_ROLES
    api_roles_by_action = {
        "create": ("trainer", "admin"), "update": ("trainer", "admin"),
        "partial_update": ("trainer", "admin"), "destroy": ("trainer", "admin"),
    }

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = CoursePrice.objects.select_related("course")
        return _filter_by(qs, self.request, "course", "course_id")


class CouponViewSet(viewsets.ModelViewSet):
    """Coupons (PRD §3.3). Admin-managed; students use ``validate`` to preview a
    discount for their cart before checkout."""

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    api_roles = ADMIN_ONLY
    api_roles_by_action = {"validate": ALL_ROLES}

    def get_permissions(self):
        if self.action == "validate":
            return [IsAuthenticated()]
        return [IsAdmin()]

    @action(detail=False, methods=["post"])
    def validate(self, request):
        payload = CouponValidateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        q = services.quote(payload.validated_data["items"], payload.validated_data["code"])
        return Response(
            {
                "code": q["coupon"].code,
                "subtotal": q["subtotal"],
                "discount": q["discount"],
                "tax_gst": q["tax_gst"],
                "total": q["total"],
            }
        )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """The current user's saved payment methods."""

    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        method = serializer.save(user=self.request.user)
        if method.is_default:
            PaymentMethod.objects.filter(user=self.request.user).exclude(
                pk=method.pk
            ).update(is_default=False)


@extend_schema(description=_MOCK_GATEWAY_NOTE)
class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Checkout orders. ``POST`` prices the cart server-side; ``pay/`` confirms
    payment and grants access. Students see only their own orders.

    Note: payment is confirmed via a MOCK gateway for now (no real money moves).
    """

    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_serializer_class(self):
        if self.action == "create":
            return CheckoutSerializer
        return OrderSerializer

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items", "payments")
            .select_related("coupon")
        )

    def create(self, request, *args, **kwargs):
        payload = CheckoutSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = services.create_order(
            user=request.user,
            items=payload.validated_data["items"],
            coupon_code=payload.validated_data.get("coupon_code") or None,
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Pay an order (MOCK gateway)",
        description=(
            "Confirms payment for the order, issues its GST invoice and grants "
            "access (paid enrollment / subscription activation). Idempotent.\n\n"
            + _MOCK_GATEWAY_NOTE
        ),
    )
    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        order = self.get_object()
        payload = PaySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        method = None
        if payload.validated_data.get("payment_method_id"):
            method = PaymentMethod.objects.filter(
                pk=payload.validated_data["payment_method_id"], user=request.user
            ).first()
        services.pay_order(
            order,
            gateway=payload.validated_data.get("gateway", "mock"),
            payment_method=method,
            gateway_payment_id=payload.validated_data.get("gateway_payment_id", ""),
        )
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class InvoiceViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """The current user's GST invoices (PRD §3.13)."""

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user).select_related("order")


class SubscriptionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """The current user's platform subscriptions. ``cancel/`` ends auto-renew."""

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    api_roles = ALL_ROLES

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related("plan")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        subscription = self.get_object()
        subscription.status = Subscription.Status.CANCELLED
        subscription.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(subscription).data)
