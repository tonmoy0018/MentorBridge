from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Role, User
from .services import validate_timezone


class CurrentUserSerializer(serializers.ModelSerializer):
    email_verified = serializers.BooleanField(read_only=True)
    is_admin = serializers.SerializerMethodField(
        help_text="True when the account may use admin endpoints (role=admin and staff)."
    )

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "timezone", "email_verified", "is_admin"]
        read_only_fields = fields

    def get_is_admin(self, obj) -> bool:
        return obj.role == Role.ADMIN and obj.is_staff and obj.is_active


class UpdateMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "timezone"]
        extra_kwargs = {"first_name": {"allow_blank": False}, "last_name": {"allow_blank": False}}

    def validate_timezone(self, value):
        try:
            return validate_timezone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    role = serializers.ChoiceField(choices=[Role.STUDENT, Role.MENTOR])
    timezone = serializers.CharField(max_length=64, default="UTC")

    def validate_email(self, value):
        value = User.objects.normalize_email_address(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_timezone(self, value):
        try:
            return validate_timezone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate(self, attrs):
        try:
            password_validation.validate_password(attrs["new_password"], user=self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages}) from exc
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class EmailVerifySerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)


class AdminUserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="full_name", read_only=True)
    date_joined = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "role", "is_active", "date_joined", "last_login"]
        read_only_fields = fields
