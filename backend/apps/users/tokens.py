from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes, force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    HMAC token bound to the user's email and verification state: it stops working once the
    email is verified (single use) or changed.
    """

    key_salt = "apps.users.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        verified = "" if user.email_verified_at is None else user.email_verified_at.isoformat()
        return f"{user.pk}{user.email}{verified}{timestamp}"

    def check_token(self, user, token):
        """Same checks as the parent, but with EMAIL_VERIFICATION_TIMEOUT instead of the
        password-reset timeout."""
        if not (user and token):
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        valid = any(
            constant_time_compare(self._make_token_with_timestamp(user, ts, secret), token)
            for secret in [self.secret, *self.secret_fallbacks]
        )
        if not valid:
            return False
        return (self._num_seconds(self._now()) - ts) <= settings.EMAIL_VERIFICATION_TIMEOUT


email_verification_token = EmailVerificationTokenGenerator()


def encode_uid(user) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def decode_uid(uid: str) -> str | None:
    try:
        return force_str(urlsafe_base64_decode(uid))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
