"""Transactional email: templates, de-duplication, failures and log hygiene (docs/NOTIFICATIONS.md)."""

import logging
from datetime import timedelta
from smtplib import SMTPException
from unittest import mock

import pytest
from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingStatus
from apps.notifications import services as notifications
from apps.notifications.models import EmailNotification, NotificationStatus

from .conftest import client_for, make_mentor, open_slots, service_of

pytestmark = pytest.mark.django_db

SEND_MAIL = "apps.notifications.services.send_mail"


def _book(student, mentor, slot=0) -> Booking:
    return booking_services.create_booking(
        student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[slot]
    )


def _sent(template: str) -> list[list[str]]:
    rows = EmailNotification.objects.filter(template=template, status=NotificationStatus.SENT)
    return [[row.recipient.email] for row in rows]


class TestDelivery:
    def test_same_event_is_sent_once(self, after_commit, student):
        with after_commit():
            first = notifications.notify("payment_failed", student, {}, dedupe_key="payment.failed:evt_1")
            again = notifications.notify("payment_failed", student, {}, dedupe_key="payment.failed:evt_1")
        assert first is not None and again is None
        assert EmailNotification.objects.count() == 1
        assert len(mail.outbox) == 1

    def test_rolled_back_change_sends_nothing(self, after_commit, student):
        with after_commit(), pytest.raises(RuntimeError), transaction.atomic():
            notifications.notify("payment_failed", student, {}, dedupe_key="k")
            raise RuntimeError("the change failed")
        assert not EmailNotification.objects.exists()
        assert mail.outbox == []

    def test_secret_links_are_not_kept_after_sending(self, after_commit, student):
        with after_commit():
            notification = notifications.notify(
                "password_reset", student, {"link": "https://example.test/reset?t=secret"}, dedupe_key="k"
            )
        assert "t=secret" in mail.outbox[0].body
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.SENT
        assert "link" not in notification.context

    def test_unknown_template_is_a_programming_error(self, student):
        with pytest.raises(ValueError):
            notifications.notify("nope", student, {}, dedupe_key="k")

    def test_suspended_users_get_nothing(self, student):
        student.is_active = False
        student.save(update_fields=["is_active"])
        assert notifications.notify("payment_failed", student, {}, dedupe_key="k") is None

    def test_failures_are_recorded_and_retried(self, after_commit, student):
        with mock.patch(SEND_MAIL, side_effect=SMTPException(f"550 rejected {student.email}")):
            with after_commit():
                notification = notifications.notify("payment_failed", student, {}, dedupe_key="k")
            notification.refresh_from_db()
            assert (notification.status, notification.attempts) == (NotificationStatus.FAILED, 1)
            assert notification.last_error == "SMTPException"  # type only: no address or server text

            for _ in range(5):  # retries stop at MAX_ATTEMPTS
                notifications.retry_failed()
            notification.refresh_from_db()
            assert notification.attempts == notifications.MAX_ATTEMPTS

        notification.attempts = 1
        notification.save(update_fields=["attempts"])
        call_command("send_notifications")
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.SENT
        assert len(mail.outbox) == 1

    def test_logs_never_contain_addresses_names_or_content(self, after_commit, caplog, student):
        mentor = make_mentor(price_cents=0)
        caplog.set_level(logging.DEBUG)
        with after_commit():
            booking = _book(student, mentor)
            booking_services.accept_booking(booking, actor=mentor.user)
        with mock.patch(SEND_MAIL, side_effect=SMTPException(f"550 {student.email}")), after_commit():
            booking_services.cancel_booking(booking, actor=student)
        assert mail.outbox  # something was sent (and logged)
        for secret in (
            student.email,
            mentor.user.email,
            student.last_name,
            mentor.user.last_name,
            "Career chat",
        ):
            assert secret not in caplog.text


class TestBookingEmails:
    def test_request_accept_and_cancel(self, after_commit, student):
        mentor = make_mentor(price_cents=0)
        with after_commit():
            booking = _book(student, mentor)
        assert _sent("booking_requested_mentor") == [[mentor.user.email]]
        assert "Career chat" in mail.outbox[0].body

        with after_commit():
            booking_services.accept_booking(booking, actor=mentor.user)
        assert _sent("booking_confirmed_student") == [[student.email]]
        assert _sent("booking_confirmed_mentor") == [[mentor.user.email]]

        with after_commit():
            booking_services.cancel_booking(booking, actor=student, reason="Clash")
        assert _sent("booking_cancelled") == [[mentor.user.email]]  # not to the person who cancelled

    def test_decline_and_expiry_tell_the_student(self, after_commit, student):
        mentor = make_mentor(price_cents=0)
        with after_commit():
            declined = _book(student, mentor, slot=0)
            booking_services.decline_booking(declined, actor=mentor.user, reason="Away that week")
            expiring = _book(student, mentor, slot=3)
            Booking.objects.filter(pk=expiring.pk).update(respond_by=timezone.now() - timedelta(minutes=1))
            booking_services.expire_due()
        assert _sent("booking_declined_student") == [[student.email]]
        assert _sent("booking_expired_student") == [[student.email]]

    def test_session_reminders_are_sent_once(self, after_commit, student):
        mentor = make_mentor(price_cents=0, auto_accept=True, min_notice=1)
        booking = _book(student, mentor)
        assert booking.status == BookingStatus.CONFIRMED and booking.start_at < timezone.now() + timedelta(
            hours=24
        )
        mail.outbox.clear()

        with after_commit():
            call_command("send_session_reminders")
            call_command("send_session_reminders")
        assert sorted(m.to[0] for m in mail.outbox) == sorted([student.email, mentor.user.email])
        assert EmailNotification.objects.filter(template="session_reminder").count() == 2


class TestAdminNotificationLog:
    def test_admins_see_delivery_status_without_addresses(self, after_commit, admin_user, student):
        with after_commit():
            notifications.notify("payment_failed", student, {}, dedupe_key="k")
        response = client_for(admin_user).get("/api/v1/admin/notifications/")
        assert response.status_code == 200
        assert response.json()["results"][0]["status"] == NotificationStatus.SENT
        assert student.email not in response.content.decode()

    def test_non_admins_are_refused(self, student, mentor):
        for user in (student, mentor.user):
            assert client_for(user).get("/api/v1/admin/notifications/").status_code == 403
