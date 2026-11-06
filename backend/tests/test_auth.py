import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.mentors.models import MentorProfile, VerificationStatus
from apps.students.models import StudentProfile
from apps.users.models import User

from .conftest import PASSWORD, client_for, error_code, make_user

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"


def register(client, **overrides):
    payload = {
        "email": "Jordan@Example.com",
        "password": PASSWORD,
        "first_name": "Jordan",
        "last_name": "Lee",
        "role": "student",
        "timezone": "Europe/London",
        **overrides,
    }
    return client.post(REGISTER, payload, format="json")


def _link_parts(body: str) -> tuple[str, str]:
    match = re.search(r"uid=([\w-]+)&token=([\w-]+)", body)
    assert match, body
    return match.group(1), match.group(2)


class TestRegistration:
    def test_student_registration_creates_profile_and_logs_in(self, api):
        response = register(api)
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "jordan@example.com"  # normalised
        assert body["role"] == "student"
        assert body["email_verified"] is False
        assert "sessionid" in response.cookies
        assert StudentProfile.objects.filter(user__email="jordan@example.com").exists()
        assert api.get(ME).status_code == 200

    def test_mentor_registration_creates_draft_profile(self, api):
        response = register(api, email="mentor@example.com", role="mentor")
        assert response.status_code == 201
        profile = MentorProfile.objects.get(user__email="mentor@example.com")
        assert profile.verification_status == VerificationStatus.DRAFT
        assert profile.slug == "jordan-lee"

    def test_sends_verification_email_after_commit(self, api, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            register(api)
        assert len(mail.outbox) == 1
        assert "/verify-email?uid=" in mail.outbox[0].body

    def test_mail_server_outage_does_not_break_registration(self, api, django_capture_on_commit_callbacks):
        from unittest import mock

        with (
            mock.patch("apps.notifications.services.send_mail", side_effect=OSError("SMTP down")),
            django_capture_on_commit_callbacks(execute=True),
        ):
            response = register(api)
        assert response.status_code == 201
        assert api.get(ME).status_code == 200  # logged in, account usable

    def test_cannot_self_register_as_admin(self, api):
        response = register(api, role="admin")
        assert response.status_code == 400
        assert "role" in response.json()["error"]["details"]["fields"]

    def test_duplicate_email_is_case_insensitive(self, api):
        make_user(email="jordan@example.com")
        response = register(api, email="JORDAN@example.com")
        assert response.status_code == 400
        assert "email" in response.json()["error"]["details"]["fields"]

    @pytest.mark.parametrize("password", ["password", "12345678", "short"])
    def test_weak_passwords_rejected(self, api, password):
        response = register(api, password=password)
        assert response.status_code == 400
        assert "password" in response.json()["error"]["details"]["fields"]
        assert not User.objects.exists()

    def test_invalid_timezone_rejected(self, api):
        assert register(api, timezone="Mars/Olympus").status_code == 400


class TestLogin:
    def test_login_and_logout(self, api):
        user = make_user(email="amy@example.com")
        response = api.post(LOGIN, {"email": "AMY@example.com", "password": PASSWORD}, format="json")
        assert response.status_code == 200
        assert response.json()["id"] == str(user.pk)
        assert api.post("/api/v1/auth/logout/").status_code == 204
        assert api.get(ME).status_code == 401

    @pytest.mark.parametrize(
        "email,password", [("amy@example.com", "wrong-pass-123"), ("nobody@example.com", PASSWORD)]
    )
    def test_bad_credentials_give_one_generic_error(self, api, email, password):
        make_user(email="amy@example.com")
        response = api.post(LOGIN, {"email": email, "password": password}, format="json")
        assert response.status_code == 400
        assert error_code(response) == "invalid_credentials"

    def test_suspended_user_cannot_log_in(self, api):
        make_user(email="amy@example.com", is_active=False)
        response = api.post(LOGIN, {"email": "amy@example.com", "password": PASSWORD}, format="json")
        assert error_code(response) == "invalid_credentials"

    def test_me_requires_authentication(self, api):
        response = api.get(ME)
        assert response.status_code == 401
        assert error_code(response) == "not_authenticated"

    def test_update_me(self):
        user = make_user()
        response = client_for(user).patch(ME, {"timezone": "Asia/Tokyo", "role": "admin"}, format="json")
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.timezone == "Asia/Tokyo"
        assert user.role == "student"  # role is not writable


class TestCsrf:
    def test_login_requires_csrf_token(self):
        make_user(email="amy@example.com")
        client = APIClient(enforce_csrf_checks=True)
        rejected = client.post(LOGIN, {"email": "amy@example.com", "password": PASSWORD}, format="json")
        assert rejected.status_code == 403
        assert error_code(rejected) == "csrf_failed"

        client.get("/api/v1/auth/csrf/")
        token = client.cookies["csrftoken"].value
        accepted = client.post(
            LOGIN, {"email": "amy@example.com", "password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token
        )
        assert accepted.status_code == 200

    def test_authenticated_writes_require_csrf_token(self):
        user = make_user()
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        response = client.patch(ME, {"first_name": "X"}, format="json")
        assert response.status_code == 403
        assert error_code(response) == "csrf_failed"


class TestPasswordReset:
    def test_full_reset_flow_and_single_use_token(self, api, django_capture_on_commit_callbacks):
        make_user(email="amy@example.com")
        with django_capture_on_commit_callbacks(execute=True):
            response = api.post("/api/v1/auth/password/reset/", {"email": "amy@example.com"}, format="json")
        assert response.status_code == 204
        uid, token = _link_parts(mail.outbox[-1].body)

        payload = {"uid": uid, "token": token, "new_password": "Brand-New-Pass-42"}
        assert api.post("/api/v1/auth/password/reset/confirm/", payload, format="json").status_code == 204
        login = api.post(LOGIN, {"email": "amy@example.com", "password": "Brand-New-Pass-42"}, format="json")
        assert login.status_code == 200

        reused = api.post("/api/v1/auth/password/reset/confirm/", payload, format="json")
        assert reused.status_code == 400
        assert error_code(reused) == "invalid_token"

    def test_unknown_email_gives_same_response_and_sends_nothing(
        self, api, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = api.post("/api/v1/auth/password/reset/", {"email": "ghost@example.com"}, format="json")
        assert response.status_code == 204
        assert mail.outbox == []

    def test_tampered_token_rejected(self, api, django_capture_on_commit_callbacks):
        make_user(email="amy@example.com")
        with django_capture_on_commit_callbacks(execute=True):
            api.post("/api/v1/auth/password/reset/", {"email": "amy@example.com"}, format="json")
        uid, _ = _link_parts(mail.outbox[-1].body)
        response = api.post(
            "/api/v1/auth/password/reset/confirm/",
            {"uid": uid, "token": "abc-123", "new_password": "Brand-New-Pass-42"},
            format="json",
        )
        assert error_code(response) == "invalid_token"

    def test_password_change(self):
        user = make_user()
        client = client_for(user)
        wrong = client.post(
            "/api/v1/auth/password/change/",
            {"current_password": "nope", "new_password": "Another-Pass-77"},
            format="json",
        )
        assert wrong.status_code == 400
        ok = client.post(
            "/api/v1/auth/password/change/",
            {"current_password": PASSWORD, "new_password": "Another-Pass-77"},
            format="json",
        )
        assert ok.status_code == 204
        assert client.get(ME).status_code == 200  # current session survives


class TestEmailVerification:
    def test_links_are_not_html_escaped(self, api, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            register(api)
        assert "&token=" in mail.outbox[-1].body
        assert "&amp;" not in mail.outbox[-1].body

    def test_verify_once(self, api, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            register(api)
        uid, token = _link_parts(mail.outbox[-1].body)
        assert (
            api.post("/api/v1/auth/email/verify/", {"uid": uid, "token": token}, format="json").status_code
            == 204
        )
        assert api.get(ME).json()["email_verified"] is True
        again = api.post("/api/v1/auth/email/verify/", {"uid": uid, "token": token}, format="json")
        assert error_code(again) == "invalid_token"


class TestRateLimits:
    def test_login_attempts_per_account_are_limited(self, api):
        make_user(email="amy@example.com")
        codes = [
            api.post(LOGIN, {"email": "amy@example.com", "password": "wrong"}, format="json").status_code
            for _ in range(6)
        ]
        assert codes[:5] == [400] * 5
        assert codes[5] == 429

    def test_login_attempts_per_ip_are_limited(self, api):
        codes = [
            api.post(LOGIN, {"email": f"u{i}@example.com", "password": "wrong"}, format="json").status_code
            for i in range(11)
        ]
        assert codes[-1] == 429
        assert (
            "retry_after_seconds"
            in api.post(LOGIN, {"email": "x@example.com", "password": "x"}, format="json").json()["error"][
                "details"
            ]
        )
