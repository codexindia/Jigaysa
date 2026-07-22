"""Serializers for pricing, checkout, invoices and subscriptions (§3.3/3.4/3.13)."""

from rest_framework import serializers

from payments.models import (
    Coupon,
    CoursePrice,
    Invoice,
    Order,
    OrderItem,
    Payment,
    PaymentMethod,
    PricingPlan,
    Subscription,
)


class PricingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingPlan
        fields = (
            "id", "name", "slug", "billing_period", "price", "currency",
            "features", "is_active",
        )


class CoursePriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoursePrice
        fields = (
            "id", "course", "pricing_type", "amount", "currency",
            "discount_percent", "discount_amount", "valid_from", "valid_to",
        )


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "id", "code", "discount_type", "value", "scope", "min_amount",
            "max_redemptions", "used_count", "valid_from", "valid_to", "is_active",
        )
        read_only_fields = ("used_count",)


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = (
            "id", "type", "brand", "last4", "expiry", "is_default", "created_at",
        )
        read_only_fields = ("created_at",)


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PricingPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id", "plan", "status", "current_period_start", "current_period_end",
            "cancel_at", "created_at",
        )
        read_only_fields = fields


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "item_type", "object_id", "title", "amount", "qty")


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id", "gateway", "gateway_payment_id", "amount", "method",
            "status", "paid_at",
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "status", "subtotal", "discount", "tax_gst", "total",
            "currency", "coupon_code", "items", "payments", "created_at",
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            "id", "number", "order", "description", "amount", "gst_amount",
            "status", "issued_date", "pdf_url",
        )
        read_only_fields = fields


# --- action payloads --------------------------------------------------------


class OrderItemInputSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=OrderItem.ItemType.choices)
    object_id = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    """Create an order. Amounts are computed server-side from the catalog."""

    items = OrderItemInputSerializer(many=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True)


class PaySerializer(serializers.Serializer):
    gateway = serializers.ChoiceField(
        choices=Payment.Gateway.choices, required=False
    )
    payment_method_id = serializers.IntegerField(required=False)
    gateway_payment_id = serializers.CharField(required=False, allow_blank=True)


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    items = OrderItemInputSerializer(many=True)
