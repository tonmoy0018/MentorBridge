"""Account operations. Views stay thin; every write goes through here."""

import logging
from zoneinfo import available_timezones

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.models import record_audit
from apps.notifications.services import notify, unique_key

from .models import Role, User
from .tokens import decode_uid, email_verification_token, encode_uid

logger = logging.getLogger(__name__)

VALID_TIMEZONES = frozenset(available_timezones())


def validate_timezone(value: str) -> str:
    if value not in VALID_TIMEZONES:
        raise ValidationError("Choose a valid IANA time zone, e.g. Europe/London.")
    return value


@transaction.atomic
def register_user(*, email: str, password: str, first_name: str, last_name: str, role: str, tz: str) -> User:
    """Create a student or mentor account with its profile. Admins are never self-registered."""
    if role not in (Role.STUDENT, Role.MENTOR):
        raise ValidationError({"role": "Choose student or mentor."})
    user = User(
        email=User.objects.normalize_email_address(email),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role=role,
        timezone=tz,
    )
    password_validation.validate_password(password, user=user)
    user.set_password(password)
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as exc:  # a concurrent registration with the same email won the race
        raise ValidationError({"email": "An account with this email already exists."}) from exc

    if role == Role.MENTOR:
        from apps.mentors.services import create_mentor_profile

        create_mentor_profile(user)
    else:
        from apps.students.models import StudentProfile

        StudentProfile.objects.create(user=user)

    send_verification_email(user)
    return user


def send_verification_email(user: User) -> None:
    if user.email_verified:
        return
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={encode_uid(user)}&token={token}"
    notify("account_verification", user, {"link": link}, dedupe_key=unique_key(f"account.verify:{user.pk}"))


def verify_email(uid: str, token: str) -> User | None:
    user = _user_from_uid(uid)
    if user is None or not email_verification_token.check_token(user, token):
        return None
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at", "updated_at"])
    return user


def _user_from_uid(uid: str) -> User | None:
    pk = decode_uid(uid)
    if pk is None:
        return None
    try:
        return User.objects.get(pk=pk)
    except (User.DoesNotExist, ValueError, ValidationError):
        return None


def request_password_reset(email: str) -> None:
    """Always succeeds from the caller's point of view (no account enumeration)."""
    user = User.objects.filter(
        email__iexact=User.objects.normalize_email_address(email), is_active=True
    ).first()
    if user is None or not user.has_usable_password():
        return
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={encode_uid(user)}&token={token}"
    notify("password_reset", user, {"link": link}, dedupe_key=unique_key(f"password.reset:{user.pk}"))


def confirm_password_reset(uid: str, token: str, new_password: str) -> bool:
    """Returns False for an invalid/expired/used token. Changing the password invalidates the token."""
    user = _user_from_uid(uid)
    if user is None or not user.is_active or not default_token_generator.check_token(user, token):
        return False
    password_validation.validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    return True


def set_active(*, user: User, active: bool, actor: User, reason: str = "", request=None) -> User:
    """Suspend or reactivate an account. Inactive users can't log in and their sessions stop working."""
    user.is_active = active
    user.save(update_fields=["is_active", "updated_at"])
    if not active:
        # End existing sessions now, so reactivation doesn't revive a session that may have
        # been the reason for the suspension.
        end_sessions(user)
    record_audit(
        actor, "user.reactivated" if active else "user.suspended", user, {"reason": reason}, request=request
    )
    logger.info("User %s %s by %s", user.pk, "reactivated" if active else "suspended", actor.pk)
    return user


def end_sessions(user: User) -> int:
    """Delete every unexpired database session that belongs to `user`."""
    from django.contrib.sessions.models import Session

    ended = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()
            ended += 1
    return ended
