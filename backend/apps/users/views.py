from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.authentication import EnforceCSRFMixin
from apps.common.exceptions import DomainError
from apps.common.schema import AUTHED, E400, E401, E429, errors
from apps.common.throttling import IPScopedThrottle, LoginEmailThrottle

from . import services
from .serializers import (
    CurrentUserSerializer,
    EmailVerifySerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UpdateMeSerializer,
)

TAG = ["Auth"]


def _password_errors(exc: DjangoValidationError, field: str):
    return ValidationError({field: exc.messages})


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Sets the `csrftoken` cookie. Call once before the first unsafe request."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=TAG, responses={204: None}, summary="Get a CSRF cookie")
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(EnforceCSRFMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "auth_register"

    @extend_schema(
        tags=TAG,
        summary="Register a student or mentor account and log in",
        request=RegisterSerializer,
        responses={201: CurrentUserSerializer, **errors(E400, E429)},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = services.register_user(
                email=data["email"],
                password=data["password"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role=data["role"],
                tz=data["timezone"],
            )
        except DjangoValidationError as exc:
            raise _password_errors(exc, "password") from exc
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(CurrentUserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(EnforceCSRFMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [IPScopedThrottle, LoginEmailThrottle]
    throttle_scope = "auth_login"

    @extend_schema(
        tags=TAG,
        summary="Log in with email and password",
        description="Starts a session (HttpOnly `sessionid` cookie). Wrong credentials and suspended "
        "accounts both return `invalid_credentials` so accounts can't be enumerated.",
        request=LoginSerializer,
        responses={200: CurrentUserSerializer, **errors(E400, E429)},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request, email=serializer.validated_data["email"], password=serializer.validated_data["password"]
        )
        if user is None:
            raise DomainError("invalid_credentials", "Email or password is incorrect.", status_code=400)
        login(request, user)  # rotates the session key and CSRF token
        return Response(CurrentUserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=TAG, summary="Log out", request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(tags=TAG, summary="Current user", responses={200: CurrentUserSerializer, **E401})
    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)

    @extend_schema(
        tags=TAG,
        summary="Update name and time zone",
        request=UpdateMeSerializer,
        responses={200: CurrentUserSerializer, **errors(E400, AUTHED)},
    )
    def patch(self, request):
        serializer = UpdateMeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CurrentUserSerializer(request.user).data)


class PasswordChangeView(APIView):
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "password_change"

    @extend_schema(
        tags=TAG,
        summary="Change password",
        request=PasswordChangeSerializer,
        responses={204: None, **errors(E400, AUTHED, E429)},
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        update_session_auth_hash(request, request.user)  # keep this session, end the others
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(EnforceCSRFMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=TAG,
        summary="Request a password reset email",
        description="Always returns 204, whether or not the account exists.",
        request=PasswordResetRequestSerializer,
        responses={204: None, **errors(E400, E429)},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(EnforceCSRFMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "password_reset_confirm"

    @extend_schema(
        tags=TAG,
        summary="Set a new password with a reset token",
        description="Tokens are single-use and expire after `PASSWORD_RESET_TIMEOUT`. "
        "An invalid token returns 400 with code `invalid_token`.",
        request=PasswordResetConfirmSerializer,
        responses={204: None, **errors(E400, E429)},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            ok = services.confirm_password_reset(data["uid"], data["token"], data["new_password"])
        except DjangoValidationError as exc:
            raise _password_errors(exc, "new_password") from exc
        if not ok:
            raise DomainError("invalid_token", "This reset link is invalid or has expired.", status_code=400)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailVerifyView(EnforceCSRFMixin, APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "email_verify"

    @extend_schema(
        tags=TAG,
        summary="Confirm an email address",
        request=EmailVerifySerializer,
        responses={204: None, **errors(E400, E429)},
    )
    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if (
            services.verify_email(serializer.validated_data["uid"], serializer.validated_data["token"])
            is None
        ):
            raise DomainError(
                "invalid_token", "This verification link is invalid or has expired.", status_code=400
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailVerifyResendView(APIView):
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "email_verify"

    @extend_schema(
        tags=TAG,
        summary="Resend the verification email",
        request=None,
        responses={204: OpenApiResponse(description="Sent, or already verified."), **errors(AUTHED, E429)},
    )
    def post(self, request):
        services.send_verification_email(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
