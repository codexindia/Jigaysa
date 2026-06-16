from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import Role

User = get_user_model()

# Roles a self-service registrant may pick. Privileged roles are gated and
# can only be assigned by an admin (e.g. via the admin site / future API).
SELF_REGISTRABLE_ROLES = {Role.STUDENT, Role.TRAINER}


class UserSerializer(serializers.ModelSerializer):
    """Read/update the current user's profile. Role is read-only here."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "role",
            "phone",
            "phone_verified",
            "organization",
            "is_active",
            "date_joined",
        )
        read_only_fields = (
            "id",
            "email",
            "role",
            "phone_verified",
            "organization",
            "is_active",
            "date_joined",
        )

    date_joined = serializers.DateTimeField(source="created_at", read_only=True)


class RegisterSerializer(serializers.ModelSerializer):
    """Email/password registration with Django password validation."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(
        choices=[(r.value, r.label) for r in SELF_REGISTRABLE_ROLES],
        default=Role.STUDENT,
    )

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "phone", "password")

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class TokenPairSerializer(TokenObtainPairSerializer):
    """JWT login serializer that embeds role + id into the token claims."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    """Accepts a refresh token to blacklist on logout."""

    refresh = serializers.CharField()
