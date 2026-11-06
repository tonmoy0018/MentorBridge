"""
Payment workflow tests (docs/PAYMENTS.md).

MOCKED PROVIDER RESPONSES: `FakeStripe` (tests/conftest.py) stands in for Stripe's API client.
No request leaves the test process and none of these payments are real. Webhooks, though, are
signed with HMAC-SHA256 exactly as Stripe signs them and verified by the real `stripe` library, so
signature checking runs the production code path.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import timedelta

import pytest
import stripe
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingEvent, BookingStatus, RefundOutcome
from apps.common.models import AuditLogEntry
from apps.notifications.models import EmailNotification
from apps.payments import commission
from apps.payments.models import (
    DisputeStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundReason,
    RefundRecordStatus,
    RefundStatus,
    WebhookEvent,
)

from .conftest import WEBHOOK_SECRET, client_for, error_code, make_mentor, open_slots, service_of

pytestmark = pytest.mark.django_db

WEBHOOK_URL = "/api/v1/payments/webhooks/stripe/"


# --- signed webhooks ------------------------------------------------------------------------------


def sign(payload: str, *, secret: str = WEBHOOK_SECRET, timestamp: float | None = None) -> str:
    t = int(timestamp or time.time())
    mac = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def event_payload(event_type: str, obj: dict, *, event_id: str | None = None, livemode=False) -> str:
    return json.dumps(
        {
            "id": event_id or f"evt_mock_{uuid.uuid4().hex}",
            "object": "event",
            "type": event_type,
            "livemode": livemode,
            "created": int(time.time()),
            "data": {"object": obj},
        }
    )


def post_webhook(payload: str, signature: str | None):
    headers = {"HTTP_STRIPE_SIGNATURE": signature} if signature else {}
    return APIClient().post(WEBHOOK_URL, data=payload, content_type="application/json", **headers)


def deliver(event_type: str, obj: dict, **kwargs):
    payload = event_payload(event_type, obj, **kwargs)
    response = post_webhook(payload, sign(payload))
    assert response.status_code == 200, response.content
    return response.json()["outcome"]


def intent_ref(payment) -> str:
    return f"pi_mock_{payment.pk.hex[:16]}"


def metadata(payment) -> dict:
    return {"payment_id": str(payment.pk), "booking_id": str(payment.booking_id)}


def authorize(payment, *, amount=None, currency="usd", **kwargs) -> str:
    obj = {
        "id": intent_ref(payment),
        "object": "payment_intent",
        "amount": payment.amount_cents,
        "amount_capturable": payment.amount_cents if amount is None else amount,
        "currency": currency,
        "status": "requires_capture",
        "metadata": metadata(payment),
    }
    return deliver("payment_intent.amount_capturable_updated", obj, **kwargs)


def refund_event(refund, status: str, *, event_type="refund.updated", **kwargs) -> str:
    obj = {
        "id": refund.provider_reference,
        "object": "refund",
        "amount": refund.amount_cents,
        "currency": "usd",
        "status": status,
        "payment_intent": refund.payment.provider_reference,
        "metadata": {"refund_id": str(refund.pk), "payment_id": str(refund.payment_id)},
    }
    return deliver(event_type, obj, **kwargs)


def dispute_event(payment, event_type: str, status: str) -> str:
    obj = {
        "id": "dp_mock",
        "object": "dispute",
        "amount": payment.amount_cents,
        "currency": "usd",
        "status": status,
        "payment_intent": payment.provider_reference,
        "metadata": {},
    }
    return deliver(event_type, obj)


# --- booking flow helpers -------------------------------------------------------------------------


def hold(student, mentor, *, days_ahead=2) -> Booking:
    """A paid booking holding a slot at least `days_ahead` days out (clear of the 24 h refund cut-off)."""
    earliest = timezone.now() + timedelta(days=days_ahead)
    start = next(s for s in open_slots(mentor, days=days_ahead + 5) if s >= earliest)
    return booking_services.create_booking(student=student, service_id=service_of(mentor).pk, start_at=start)


def checkout(student, booking) -> Payment:
    response = client_for(student).post(f"/api/v1/bookings/{booking.pk}/checkout/")
    assert response.status_code == 200, response.content
    return Payment.objects.get(pk=response.json()["payment_id"])


def paid_request(student, mentor) -> tuple[Booking, Payment]:
    booking = hold(student, mentor)
    payment = checkout(student, booking)
    assert authorize(payment) == "authorized"
    booking.refresh_from_db()
    payment.refresh_from_db()
    return booking, payment


def confirmed_paid(student, mentor) -> tuple[Booking, Payment]:
    booking, payment = paid_request(student, mentor)
    booking = booking_services.accept_booking(booking, actor=mentor.user)
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.CAPTURED
    return booking, payment


def templates_sent() -> list[str]:
    return list(EmailNotification.objects.order_by("created_at").values_list("template", flat=True))


# --- commission -----------------------------------------------------------------------------------


class TestCommission:
    def test_brief_example(self):
        split = commission.breakdown(4000, 1500)
        assert (split.commission_cents, split.mentor_share_cents) == (600, 3400)

    @pytest.mark.parametrize(
        ("gross", "bps", "fee"),
        [
            (999, 1500, 150),  # 149.85 → 150
            (10, 1500, 2),  # 1.5 → 2 (half up)
            (1, 1500, 0),  # 0.15 → 0
            (5000, 0, 0),
            (5000, 10_000, 5000),
            (3333, 1250, 417),  # 416.625 → 417
        ],
    )
    def test_rounding_and_breakdown_always_adds_up(self, gross, bps, fee):
        split = commission.breakdown(gross, bps)
        assert split.commission_cents == fee
        assert split.commission_cents + split.mentor_share_cents == gross

    def test_checkout_snapshots_the_mentors_rate(self, fake_stripe, student):
        mentor = make_mentor(price_cents=4000)
        mentor.commission_bps = 1000  # admin-set override
        mentor.save(update_fields=["commission_bps"])
        payment = checkout(student, hold(student, mentor))
        assert (payment.commission_bps, payment.platform_fee_cents, payment.mentor_share_cents) == (
            1000,
            400,
            3600,
        )

        mentor.commission_bps = 2000  # later changes don't touch existing payments
        mentor.save(update_fields=["commission_bps"])
        payment.refresh_from_db()
        assert payment.platform_fee_cents == 400


# --- checkout -------------------------------------------------------------------------------------


class TestCheckout:
    def test_creates_provider_checkout_with_server_side_amount(self, fake_stripe, student, mentor):
        booking = hold(student, mentor)
        response = client_for(student).post(f"/api/v1/bookings/{booking.pk}/checkout/")
        assert response.status_code == 200
        body = response.json()
        assert body["checkout_url"].startswith("https://checkout.stripe.test/")
        assert body["livemode"] is False

        payment = Payment.objects.get(pk=body["payment_id"])
        assert (payment.amount_cents, payment.platform_fee_cents, payment.mentor_share_cents) == (
            5000,
            750,
            4250,
        )
        assert (payment.status, payment.provider, payment.livemode) == (
            PaymentStatus.CREATED,
            "stripe",
            False,
        )

        _, kwargs = fake_stripe.last("checkout.create")
        params = kwargs["params"]
        assert params["payment_intent_data"]["capture_method"] == "manual"
        assert params["line_items"][0]["price_data"]["unit_amount"] == 5000
        assert params["metadata"]["payment_id"] == str(payment.pk)
        assert kwargs["options"]["idempotency_key"] == f"checkout-{payment.pk}"
        # Stripe requires ≥30 minutes; the slot stays held for the whole checkout.
        assert params["expires_at"] >= int((timezone.now() + timedelta(minutes=30)).timestamp())
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING_PAYMENT
        assert booking.hold_expires_at == payment.checkout_expires_at

    def test_repeated_clicks_reuse_the_open_checkout(self, fake_stripe, student, mentor):
        booking = hold(student, mentor)
        first, second = checkout(student, booking), checkout(student, booking)
        assert first.pk == second.pk
        assert fake_stripe.names().count("checkout.create") == 1

    def test_other_students_cannot_start_checkout(self, fake_stripe, student, other_student, mentor):
        booking = hold(student, mentor)
        assert client_for(other_student).post(f"/api/v1/bookings/{booking.pk}/checkout/").status_code == 404
        assert APIClient().post(f"/api/v1/bookings/{booking.pk}/checkout/").status_code == 401

    def test_provider_outage_creates_nothing(self, fake_stripe, student, mentor):
        fake_stripe.failures["checkout.create"] = stripe.APIConnectionError("network down")
        booking = hold(student, mentor)
        response = client_for(student).post(f"/api/v1/bookings/{booking.pk}/checkout/")
        assert response.status_code == 502
        assert error_code(response) == "payment_provider_error"
        assert not Payment.objects.exists()
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING_PAYMENT

    def test_unavailable_without_a_provider(self, fake_stripe, settings, student, mentor):
        booking = hold(student, mentor)
        settings.PAYMENTS_ENABLED = False
        response = client_for(student).post(f"/api/v1/bookings/{booking.pk}/checkout/")
        assert response.status_code == 503
        assert error_code(response) == "payments_unavailable"

    def test_client_cannot_mark_a_booking_paid(self, fake_stripe, student, mentor):
        """The browser returning from checkout, or a client sending a status, changes nothing."""
        booking = hold(student, mentor)
        payment = checkout(student, booking)
        client = client_for(student)
        client.get(f"/api/v1/bookings/{booking.pk}/?checkout={booking.pk}")
        client.patch(f"/api/v1/bookings/{booking.pk}/", {"status": "confirmed"}, format="json")
        client.post(WEBHOOK_URL, {"type": "payment_intent.succeeded"}, format="json")
        booking.refresh_from_db()
        payment.refresh_from_db()
        assert booking.status == BookingStatus.PENDING_PAYMENT
        assert payment.status == PaymentStatus.CREATED

    def test_no_card_data_or_payloads_are_stored(self):
        fields = {f.name for model in (Payment, Refund, WebhookEvent) for f in model._meta.get_fields()}
        assert not {
            name for name in fields if any(word in name for word in ("card", "cvc", "cvv", "payload"))
        }


# --- webhook verification -------------------------------------------------------------------------


class TestWebhookVerification:
    @pytest.fixture
    def payment(self, fake_stripe, student, mentor):
        return checkout(student, hold(student, mentor))

    def _authorize_payload(self, payment, **kwargs):
        obj = {
            "id": intent_ref(payment),
            "object": "payment_intent",
            "amount_capturable": payment.amount_cents,
            "currency": "usd",
            "metadata": metadata(payment),
        }
        return event_payload("payment_intent.amount_capturable_updated", obj, **kwargs)

    def _assert_untouched(self, payment):
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.CREATED
        assert payment.booking.status == BookingStatus.PENDING_PAYMENT
        assert not WebhookEvent.objects.exists()

    @pytest.mark.parametrize(
        "make_signature",
        [
            pytest.param(lambda payload: None, id="missing"),
            pytest.param(lambda payload: sign(payload, secret="whsec_attacker"), id="wrong-secret"),
            pytest.param(lambda payload: sign(payload, timestamp=time.time() - 600), id="stale-timestamp"),
            pytest.param(lambda payload: "t=1,v1=deadbeef", id="garbage"),
        ],
    )
    def test_rejects_bad_signatures(self, payment, make_signature):
        payload = self._authorize_payload(payment)
        response = post_webhook(payload, make_signature(payload))
        assert response.status_code == 400
        assert error_code(response) == "invalid_signature"
        self._assert_untouched(payment)

    def test_rejects_a_tampered_payload(self, payment):
        signed = self._authorize_payload(payment, event_id="evt_mock_original")
        tampered = signed.replace('"amount_capturable": 5000', '"amount_capturable": 1')
        assert tampered != signed
        assert post_webhook(tampered, sign(signed)).status_code == 400
        self._assert_untouched(payment)

    def test_unknown_provider_and_disabled_payments_are_404(self, payment, settings):
        assert APIClient().post("/api/v1/payments/webhooks/paypal/", {}, format="json").status_code == 404
        settings.PAYMENTS_ENABLED = False
        payload = self._authorize_payload(payment)
        assert post_webhook(payload, sign(payload)).status_code == 404

    def test_mode_mismatch_is_ignored(self, payment):
        assert authorize(payment, livemode=True) == "mode_mismatch"
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.CREATED

    def test_unrelated_events_are_acknowledged_and_ignored(self, payment):
        assert deliver("customer.created", {"id": "cus_mock", "object": "customer"}) == "ignored"


# --- authorisation --------------------------------------------------------------------------------


class TestAuthorization:
    def test_authorisation_sends_the_request_to_the_mentor(self, fake_stripe, after_commit, student, mentor):
        booking = hold(student, mentor)
        payment = checkout(student, booking)
        with after_commit():
            assert authorize(payment) == "authorized"

        payment.refresh_from_db()
        booking.refresh_from_db()
        assert payment.status == PaymentStatus.AUTHORIZED
        assert payment.provider_reference == intent_ref(payment)
        assert booking.status == BookingStatus.REQUESTED
        assert booking.respond_by is not None and booking.hold_expires_at is None
        assert "booking_requested_mentor" in templates_sent()
        assert [m.to for m in mail.outbox] == [[mentor.user.email]]

    def test_duplicate_webhook_changes_nothing(self, fake_stripe, after_commit, student, mentor):
        booking = hold(student, mentor)
        payment = checkout(student, booking)
        with after_commit():
            assert authorize(payment, event_id="evt_mock_dup") == "authorized"
            assert authorize(payment, event_id="evt_mock_dup") == "duplicate"
            assert authorize(payment) == "noop"  # same state, new event id

        assert WebhookEvent.objects.count() == 2
        assert BookingEvent.objects.filter(booking=booking, to_status=BookingStatus.REQUESTED).count() == 1
        assert templates_sent().count("booking_requested_mentor") == 1
        assert len(mail.outbox) == 1

    @pytest.mark.parametrize(("amount", "currency"), [(100, "usd"), (5000, "eur")])
    def test_amount_or_currency_mismatch_is_released(self, fake_stripe, student, mentor, amount, currency):
        payment = checkout(student, hold(student, mentor))
        assert authorize(payment, amount=amount, currency=currency) == "amount_mismatch_released"
        payment.refresh_from_db()
        assert (payment.status, payment.failure_code) == (PaymentStatus.CANCELLED, "amount_mismatch")
        assert fake_stripe.last("cancel")[0] == (intent_ref(payment),)
        assert payment.booking.status == BookingStatus.PENDING_PAYMENT

    def test_failed_attempt_notifies_student_and_allows_retry(
        self, fake_stripe, after_commit, student, mentor
    ):
        payment = checkout(student, hold(student, mentor))
        obj = {
            "id": intent_ref(payment),
            "object": "payment_intent",
            "amount": 5000,
            "currency": "usd",
            "metadata": metadata(payment),
            "last_payment_error": {"code": "card_declined", "decline_code": "insufficient_funds"},
        }
        with after_commit():
            assert deliver("payment_intent.payment_failed", obj, event_id="evt_mock_fail") == "failed"
            assert deliver("payment_intent.payment_failed", obj, event_id="evt_mock_fail") == "duplicate"
        payment.refresh_from_db()
        assert (payment.status, payment.failure_code) == (PaymentStatus.FAILED, "insufficient_funds")
        assert payment.booking.status == BookingStatus.PENDING_PAYMENT
        assert templates_sent() == ["payment_failed"]
        assert [m.to for m in mail.outbox] == [[student.email]]

        assert authorize(payment) == "authorized"  # the student retried on the same checkout

    def test_expired_checkout_ends_the_hold(self, fake_stripe, student, mentor):
        payment = checkout(student, hold(student, mentor))
        obj = {
            "id": payment.checkout_reference,
            "object": "checkout.session",
            "amount_total": 5000,
            "currency": "usd",
            "metadata": metadata(payment),
            "status": "expired",
        }
        assert deliver("checkout.session.expired", obj) == "checkout_expired"
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.CANCELLED
        assert payment.booking.status == BookingStatus.EXPIRED

    def test_payment_after_the_hold_expired_is_released(self, fake_stripe, after_commit, student, mentor):
        booking = hold(student, mentor)
        payment = checkout(student, booking)
        Booking.objects.filter(pk=booking.pk).update(hold_expires_at=timezone.now() - timedelta(minutes=10))
        assert booking_services.expire_due() == 1
        assert "checkout.expire" in fake_stripe.names()

        with after_commit():
            assert authorize(payment) == "released_late_payment"
        payment.refresh_from_db()
        booking.refresh_from_db()
        assert payment.status == PaymentStatus.CANCELLED
        assert fake_stripe.last("cancel")[0] == (intent_ref(payment),)
        assert booking.status == BookingStatus.EXPIRED
        assert templates_sent() == ["payment_released"]


# --- capture and release --------------------------------------------------------------------------


class TestCaptureAndRelease:
    def test_mentor_acceptance_captures(self, fake_stripe, after_commit, student, mentor):
        booking, payment = paid_request(student, mentor)
        with after_commit():
            response = client_for(mentor.user).post(f"/api/v1/bookings/{booking.pk}/accept/")
        assert response.status_code == 200
        assert response.json()["status"] == BookingStatus.CONFIRMED

        args, kwargs = fake_stripe.last("capture")
        assert args == (intent_ref(payment),)
        assert kwargs["options"]["idempotency_key"] == f"capture-{payment.pk}"
        payment.refresh_from_db()
        assert (payment.status, payment.provider_fee_cents) == (PaymentStatus.CAPTURED, 175)
        assert {"booking_confirmed_student", "booking_confirmed_mentor"} <= set(templates_sent())

        captured = {
            "id": intent_ref(payment),
            "object": "payment_intent",
            "amount_received": 5000,
            "currency": "usd",
            "metadata": metadata(payment),
        }
        assert deliver("payment_intent.succeeded", captured) == "noop"

    def test_failed_capture_leaves_the_request_open(self, fake_stripe, student, mentor):
        fake_stripe.failures["capture"] = stripe.InvalidRequestError(
            "expired", param=None, code="charge_expired_for_capture"
        )
        booking, payment = paid_request(student, mentor)
        response = client_for(mentor.user).post(f"/api/v1/bookings/{booking.pk}/accept/")
        assert response.status_code == 502
        assert error_code(response) == "payment_provider_error"
        booking.refresh_from_db()
        payment.refresh_from_db()
        assert (booking.status, payment.status) == (BookingStatus.REQUESTED, PaymentStatus.AUTHORIZED)

    def test_auto_accept_captures_on_authorisation(self, fake_stripe, student):
        mentor = make_mentor(auto_accept=True)
        booking, payment = paid_request(student, mentor)
        assert (booking.status, payment.status) == (BookingStatus.CONFIRMED, PaymentStatus.CAPTURED)

    def test_auto_accept_capture_failure_falls_back_to_a_request(self, fake_stripe, student):
        fake_stripe.failures["capture"] = stripe.APIConnectionError("network down")
        mentor = make_mentor(auto_accept=True)
        booking, payment = paid_request(student, mentor)
        assert (booking.status, payment.status) == (BookingStatus.REQUESTED, PaymentStatus.AUTHORIZED)

    def test_decline_releases_the_authorisation(self, fake_stripe, student, mentor):
        booking, payment = paid_request(student, mentor)
        response = client_for(mentor.user).post(
            f"/api/v1/bookings/{booking.pk}/decline/", {"reason": "Not available"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["refund_outcome"] == RefundOutcome.NOT_CHARGED
        payment.refresh_from_db()
        assert (payment.status, payment.failure_code) == (PaymentStatus.CANCELLED, "declined")
        assert "capture" not in fake_stripe.names()

    def test_release_failure_is_recorded_and_settled_by_the_provider_event(
        self, fake_stripe, student, mentor
    ):
        booking, payment = paid_request(student, mentor)
        fake_stripe.failures["cancel"] = stripe.APIConnectionError("network down")
        booking_services.decline_booking(booking, actor=mentor.user, reason="Busy")
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.AUTHORIZED
        assert payment.failure_code.startswith("release_failed:")

        cancelled = {
            "id": intent_ref(payment),
            "object": "payment_intent",
            "amount": 5000,
            "currency": "usd",
            "metadata": metadata(payment),
        }
        assert deliver("payment_intent.canceled", cancelled) == "cancelled"
        payment.refresh_from_db()
        booking.refresh_from_db()
        assert (payment.status, booking.status) == (PaymentStatus.CANCELLED, BookingStatus.DECLINED)


# --- refunds --------------------------------------------------------------------------------------


class TestRefunds:
    def test_early_student_cancellation_refunds_in_full(self, fake_stripe, after_commit, student, mentor):
        booking, payment = confirmed_paid(student, mentor)
        with after_commit():
            response = client_for(student).post(f"/api/v1/bookings/{booking.pk}/cancel/", {}, format="json")
        assert response.status_code == 200
        assert response.json()["refund_outcome"] == RefundOutcome.FULL_REFUND

        refund = Refund.objects.get(payment=payment)
        assert (
            refund.amount_cents,
            refund.commission_reversed_cents,
            refund.mentor_share_reversed_cents,
        ) == (
            5000,
            750,
            4250,
        )
        assert (refund.reason, refund.status) == (
            RefundReason.STUDENT_CANCELLATION,
            RefundRecordStatus.PENDING,
        )
        _, kwargs = fake_stripe.last("refund")
        assert kwargs["params"]["amount"] == 5000
        assert kwargs["params"]["payment_intent"] == intent_ref(payment)
        assert kwargs["options"]["idempotency_key"] == f"refund-{refund.pk}"
        payment.refresh_from_db()
        assert (payment.refund_status, payment.refunded_amount_cents) == (RefundStatus.PENDING, 0)

        with after_commit():
            assert refund_event(refund, "succeeded", event_id="evt_mock_refund") == "refund_succeeded"
            assert refund_event(refund, "succeeded", event_id="evt_mock_refund") == "duplicate"
        payment.refresh_from_db()
        assert (payment.refund_status, payment.refunded_amount_cents) == (RefundStatus.FULL, 5000)
        sent = templates_sent()
        assert sent.count("refund_initiated") == 1 and sent.count("refund_succeeded") == 1
        assert "booking_cancelled" in sent

    def test_late_student_cancellation_is_not_refunded(self, fake_stripe, after_commit, student, mentor):
        booking, payment = confirmed_paid(student, mentor)
        with after_commit():
            booking = booking_services.cancel_booking(
                booking, actor=student, now=booking.start_at - timedelta(hours=2)
            )
        assert booking.refund_outcome == RefundOutcome.NO_REFUND
        assert "refund" not in fake_stripe.names()
        payment.refresh_from_db()
        assert payment.refund_status == RefundStatus.NONE

    def test_mentor_cancellation_refunds_in_full(self, fake_stripe, after_commit, student, mentor):
        booking, payment = confirmed_paid(student, mentor)
        with after_commit():
            response = client_for(mentor.user).post(
                f"/api/v1/bookings/{booking.pk}/cancel/", {"reason": "Ill"}, format="json"
            )
        assert response.json()["refund_outcome"] == RefundOutcome.FULL_REFUND
        assert Refund.objects.get(payment=payment).reason == RefundReason.MENTOR_CANCELLATION

    def test_cancelling_an_unaccepted_request_releases_instead_of_refunding(
        self, fake_stripe, student, mentor
    ):
        booking, payment = paid_request(student, mentor)
        client_for(student).post(f"/api/v1/bookings/{booking.pk}/cancel/", {}, format="json")
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.CANCELLED
        assert "refund" not in fake_stripe.names()

    def test_refund_failure_is_reported(self, fake_stripe, after_commit, student, mentor):
        booking, payment = confirmed_paid(student, mentor)
        with after_commit():
            client_for(student).post(f"/api/v1/bookings/{booking.pk}/cancel/", {}, format="json")
        refund = Refund.objects.get(payment=payment)
        with after_commit():
            assert refund_event(refund, "failed", event_type="refund.failed") == "refund_failed"
        payment.refresh_from_db()
        refund.refresh_from_db()
        assert (refund.status, payment.refund_status) == (RefundRecordStatus.FAILED, RefundStatus.FAILED)
        assert payment.refunded_amount_cents == 0
        assert "refund_failed" in templates_sent()
        assert AuditLogEntry.objects.filter(action="payment.refund.failed").exists()

    def test_provider_error_marks_the_refund_failed(self, fake_stripe, after_commit, student, mentor):
        booking, payment = confirmed_paid(student, mentor)
        fake_stripe.failures["refund"] = stripe.APIConnectionError("network down")
        with after_commit():
            response = client_for(student).post(f"/api/v1/bookings/{booking.pk}/cancel/", {}, format="json")
        assert response.status_code == 200  # the cancellation stands
        assert Refund.objects.get(payment=payment).status == RefundRecordStatus.FAILED

    def test_admin_partial_refunds_split_proportionally(self, fake_stripe, admin_user, student, mentor):
        _, payment = confirmed_paid(student, mentor)
        fake_stripe.refund_status = "succeeded"
        admin = client_for(admin_user)
        url = f"/api/v1/admin/payments/{payment.pk}/refund/"

        assert admin.post(url, {"amount_cents": 1000}, format="json").status_code == 400  # note required
        first = admin.post(url, {"amount_cents": 1000, "note": "Started late"}, format="json")
        assert first.status_code == 201
        assert (first.json()["commission_reversed"]["amount_cents"], first.json()["status"]) == (
            150,
            "succeeded",
        )

        too_much = admin.post(url, {"amount_cents": 4001, "note": "Too much"}, format="json")
        assert too_much.status_code == 409
        assert error_code(too_much) == "refund_too_large"

        rest = admin.post(url, {"note": "Refund the rest"}, format="json").json()
        assert rest["amount"]["amount_cents"] == 4000
        assert rest["commission_reversed"]["amount_cents"] == 600  # 150 + 600 = the original 750
        payment.refresh_from_db()
        assert (payment.refunded_amount_cents, payment.refund_status) == (5000, RefundStatus.FULL)
        assert AuditLogEntry.objects.filter(action="payment.refund.created", actor=admin_user).count() == 2

    def test_only_captured_payments_can_be_refunded(self, fake_stripe, admin_user, student, mentor):
        _, payment = paid_request(student, mentor)
        response = client_for(admin_user).post(
            f"/api/v1/admin/payments/{payment.pk}/refund/", {"note": "x"}, format="json"
        )
        assert response.status_code == 409
        assert error_code(response) == "not_refundable"

    def test_refunds_need_an_admin(self, fake_stripe, student, mentor):
        _, payment = confirmed_paid(student, mentor)
        url = f"/api/v1/admin/payments/{payment.pk}/refund/"
        assert APIClient().post(url, {"note": "x"}, format="json").status_code == 401
        for user in (student, mentor.user):
            assert client_for(user).post(url, {"note": "x"}, format="json").status_code == 403
        assert not Refund.objects.exists()

    def test_refund_made_in_the_provider_dashboard_is_recorded(self, fake_stripe, student, mentor):
        _, payment = confirmed_paid(student, mentor)
        obj = {
            "id": "re_mock_dashboard",
            "object": "refund",
            "amount": 2000,
            "currency": "usd",
            "status": "succeeded",
            "payment_intent": payment.provider_reference,
            "metadata": {},
        }
        assert deliver("refund.updated", obj) == "refund_succeeded"
        payment.refresh_from_db()
        assert (payment.refunded_amount_cents, payment.refund_status) == (2000, RefundStatus.PARTIAL)


# --- disputes -------------------------------------------------------------------------------------


class TestDisputes:
    def test_lost_dispute_reverses_the_payment(self, fake_stripe, student, mentor):
        _, payment = confirmed_paid(student, mentor)
        assert dispute_event(payment, "charge.dispute.created", "needs_response") == "dispute_open"
        assert dispute_event(payment, "charge.dispute.closed", "lost") == "dispute_lost"
        payment.refresh_from_db()
        assert (payment.dispute_status, payment.refund_status) == (DisputeStatus.LOST, RefundStatus.FULL)
        refund = Refund.objects.get(payment=payment)
        assert (refund.reason, refund.mentor_share_reversed_cents) == (RefundReason.DISPUTE_LOST, 4250)
        assert AuditLogEntry.objects.filter(action="payment.dispute.lost").exists()

    def test_won_dispute_keeps_the_payment(self, fake_stripe, student, mentor):
        _, payment = confirmed_paid(student, mentor)
        dispute_event(payment, "charge.dispute.created", "needs_response")
        assert dispute_event(payment, "charge.dispute.closed", "won") == "dispute_won"
        payment.refresh_from_db()
        assert (payment.dispute_status, payment.refunded_amount_cents) == (DisputeStatus.WON, 0)


# --- accounting -----------------------------------------------------------------------------------


class TestAccounting:
    def test_mentor_earnings_net_of_refunds(self, fake_stripe, admin_user, student, mentor):
        booking, payment = confirmed_paid(student, mentor)
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.COMPLETED)
        fake_stripe.refund_status = "succeeded"
        client_for(admin_user).post(
            f"/api/v1/admin/payments/{payment.pk}/refund/",
            {"amount_cents": 1000, "note": "Late"},
            format="json",
        )
        client = client_for(mentor.user)
        summary = client.get("/api/v1/me/mentor/earnings/summary/").json()
        assert summary["available"]["amount_cents"] == 4250 - 850
        assert summary["lifetime"]["amount_cents"] == 3400
        kinds = sorted(e["kind"] for e in client.get("/api/v1/me/mentor/earnings/ledger/").json()["results"])
        assert kinds == ["earning", "refund_reversal"]

    def test_test_mode_payments_are_never_live_revenue(self, fake_stripe, admin_user, student, mentor):
        confirmed_paid(student, mentor)  # sk_test_ key → livemode=False
        stats = client_for(admin_user).get("/api/v1/admin/stats/").json()
        assert stats["gross_booking_value"]["amount_cents"] == 0
        assert stats["platform_fees"]["amount_cents"] == 0
        assert stats["period"]["live"]["gross_booking_value"]["amount_cents"] == 0
        test_finance = stats["period"]["test"]
        assert test_finance["gross_booking_value"]["amount_cents"] == 5000
        assert test_finance["platform_commission"]["amount_cents"] == 750
        assert test_finance["provider_fees"]["amount_cents"] == 175
        assert test_finance["captured_payments"] == 1
