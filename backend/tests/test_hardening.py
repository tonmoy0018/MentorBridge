"""
Regression tests for issues found in the production-readiness review (docs/DEVELOPMENT_ROADMAP.md,
"Production-readiness review"). Payment cases use the mocked provider from conftest.py.
"""

import io
import re
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib import admin
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingStatus
from apps.mentors.models import MentorProfile, VerificationStatus
from apps.mentors.selectors import search_mentors
from apps.mentors.services import update_profile
from apps.notifications import services as notifications
from apps.payments.models import PaymentStatus, Refund, RefundReason, RefundRecordStatus
from apps.reviews.models import Review
from apps.taxonomy.models import Skill
from apps.users.models import User

from .conftest import PASSWORD, client_for, error_code, make_mentor, make_user, open_slots, service_of
from .test_payments import authorize, checkout, deliver, hold, intent_ref, metadata, paid_request

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"


class TestSearchCannotExplode:
    def test_query_cost_grows_linearly_with_terms(self):
        mentor = make_mentor()
        mentor.skills.set(Skill.objects.all()[:10])

        def plan_cost(q):
            plan = search_mentors({"q": q}).explain()
            return float(re.search(r"cost=[\d.]+\.\.([\d.]+)", plan).group(1))

        # Before the fix: ~4e4 for one term, ~4e15 for four (joins multiplied per term).
        assert plan_cost("e e e e e e e e") < 20 * plan_cost("e")

    def test_terms_still_match_skills_and_categories(self, api):
        mentor = make_mentor(skills=("python",), categories=("technology",))
        skill = mentor.skills.first().name.split()[0]
        category = mentor.categories.first().name.split()[0]
        results = api.get("/api/v1/mentors/", {"q": f"{skill} {category}"}).json()["results"]
        assert [m["slug"] for m in results] == [mentor.slug]


class TestAuthHardening:
    def test_lookalike_emails_share_the_per_account_login_limit(self, api):
        make_user(email="sis@example.com")
        variants = [
            "sis@example.com",
            "ſis@example.com",
            "sıs@example.com",
            "SIS@example.com",
            "siſ@example.com",
        ]
        for i, email in enumerate(variants):
            # A different client IP each time, so only the per-account limit applies.
            assert api.post(
                LOGIN, {"email": email, "password": "wrong"}, format="json", REMOTE_ADDR=f"10.0.0.{i}"
            )
        blocked = api.post(
            LOGIN, {"email": "ſiſ@example.com", "password": "wrong"}, format="json", REMOTE_ADDR="10.0.0.99"
        )
        assert blocked.status_code == 429

    def test_suspension_ends_sessions_for_good(self, admin_user, mentor):
        session = client_for(mentor.user)
        assert session.get("/api/v1/auth/me/").status_code == 200
        admin = client_for(admin_user)
        admin.post(
            f"/api/v1/admin/users/{mentor.user.pk}/suspend/", {"reason": "Stolen account"}, format="json"
        )
        admin.post(f"/api/v1/admin/users/{mentor.user.pk}/reactivate/")
        assert session.get("/api/v1/auth/me/").status_code == 401  # the old session isn't revived

    def test_concurrent_duplicate_registration_is_a_validation_error(self, api):
        payload = {
            "email": "race@example.com",
            "password": PASSWORD,
            "first_name": "R",
            "last_name": "C",
            "role": "student",
            "timezone": "UTC",
        }
        with mock.patch.object(User, "save", side_effect=IntegrityError("duplicate key")):
            response = api.post("/api/v1/auth/register/", payload, format="json")
        assert response.status_code == 400

    def test_django_admin_login_is_throttled(self, client, admin_user):
        url = "/django-admin/login/"
        codes = [
            client.post(url, {"username": admin_user.email, "password": "wrong"}).status_code
            for _ in range(6)
        ]
        assert codes[:5] == [200] * 5  # the login form re-rendered with an error
        assert codes[5] == 429
        # Even the right password is refused while the account is throttled.
        assert client.post(url, {"username": admin_user.email, "password": PASSWORD}).status_code == 429


class TestMentorProfileIntegrity:
    def test_profile_save_does_not_undo_a_concurrent_admin_decision(self, mentor):
        mentor.verification_status = VerificationStatus.PENDING
        mentor.save(update_fields=["verification_status"])
        stale = MentorProfile.objects.get(pk=mentor.pk)  # the mentor's request loaded this
        MentorProfile.objects.filter(pk=mentor.pk).update(
            verification_status=VerificationStatus.APPROVED, commission_bps=1000
        )
        update_profile(
            stale, {"bio": "An updated bio that is long enough to be valid here."}, actor=mentor.user
        )
        mentor.refresh_from_db()
        assert (mentor.verification_status, mentor.commission_bps) == (VerificationStatus.APPROVED, 1000)

    def test_decompression_bomb_avatar_is_rejected_not_a_500(self, mentor):
        buffer = io.BytesIO()
        Image.new("1", (20_000, 20_000)).save(buffer, format="PNG")  # tiny file, 400M pixels
        upload = SimpleUploadedFile("bomb.png", buffer.getvalue(), content_type="image/png")
        client = client_for(mentor.user)
        response = client.post("/api/v1/me/mentor/profile/avatar/", {"avatar": upload}, format="multipart")
        assert response.status_code == 400


class TestEmailAndAdmin:
    def test_email_subjects_are_not_html_escaped(self, after_commit, student):
        mentor = make_mentor(first_name="Sean", last_name="O'Brien", price_cents=0)
        service = service_of(mentor)
        service.title = "CV & Q&A"
        service.save(update_fields=["title"])
        with after_commit():
            booking = booking_services.create_booking(
                student=student, service_id=service.pk, start_at=open_slots(mentor)[0]
            )
            booking_services.accept_booking(booking, actor=mentor.user)
        subjects = " ".join(m.subject for m in mail.outbox)
        assert "&amp;" not in subjects and "&#x27;" not in subjects
        assert "CV & Q&A" in subjects

    def test_reviews_are_read_only_in_django_admin(self, rf, admin_user):
        model_admin = admin.site._registry[Review]
        request = rf.get("/")
        request.user = admin_user
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)


class TestPendingBookingLimits:
    @pytest.fixture(autouse=True)
    def _limits(self, settings):
        settings.MAX_PENDING_BOOKINGS_PER_STUDENT = 3
        settings.MAX_PENDING_BOOKINGS_PER_MENTOR_PAIR = 2

    def _book(self, student, mentor, slot):
        return booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[slot]
        )

    def test_one_student_cannot_hold_a_mentors_calendar(self, student):
        mentor = make_mentor(price_cents=0)
        self._book(student, mentor, 0)
        self._book(student, mentor, 8)
        response = client_for(student).post(
            "/api/v1/bookings/",
            {"service_id": str(service_of(mentor).pk), "start_at": open_slots(mentor)[16].isoformat()},
            format="json",
        )
        assert response.status_code == 409
        assert error_code(response) == "too_many_pending"

    def test_overall_pending_limit(self, student):
        mentors = [make_mentor(first_name=f"M{i}", price_cents=0) for i in range(4)]
        for i, mentor in enumerate(mentors[:3]):
            self._book(student, mentor, i * 8)  # different times: the student can't overlap
        with pytest.raises(Exception) as exc:
            self._book(student, mentors[3], 32)
        assert (
            getattr(exc.value, "default_code", "") == "too_many_pending"
            or "too many" in str(exc.value).lower()
        )

    def test_confirmed_bookings_dont_count(self, student):
        mentor = make_mentor(price_cents=0, auto_accept=True)
        for slot in (0, 8, 16):
            assert self._book(student, mentor, slot).status == BookingStatus.CONFIRMED


class TestStrandedCaptures:
    """The provider captured, but our record of the accept was lost (transaction rolled back)."""

    def _captured_event(self, payment):
        obj = {
            "id": intent_ref(payment),
            "object": "payment_intent",
            "amount_received": payment.amount_cents,
            "currency": "usd",
            "metadata": metadata(payment),
        }
        return deliver("payment_intent.succeeded", obj)

    def test_capture_webhook_confirms_a_request(self, fake_stripe, after_commit, student, mentor):
        booking, payment = paid_request(student, mentor)
        with after_commit():
            assert self._captured_event(payment) == "captured_confirmed"
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED and booking.meeting_url

    def test_retried_accept_after_capture_succeeds(self, fake_stripe, student, mentor):
        booking, payment = paid_request(student, mentor)
        payment.status = PaymentStatus.CAPTURED  # captured, but the booking is still `requested`
        payment.save(update_fields=["status"])
        booking = booking_services.accept_booking(booking, actor=mentor.user)
        assert booking.status == BookingStatus.CONFIRMED
        assert "capture" not in fake_stripe.names()

    def test_capture_for_a_closed_booking_is_refunded(self, fake_stripe, after_commit, student, mentor):
        booking, payment = paid_request(student, mentor)
        fake_stripe.failures["cancel"] = Exception("network")  # release failed, so it stayed authorised
        Booking.objects.filter(pk=booking.pk).update(respond_by=timezone.now() - timedelta(minutes=1))
        with mock.patch("apps.payments.services._release"):
            booking_services.expire_due()
        with after_commit():
            assert self._captured_event(payment) == "captured_refunding"
        refund = Refund.objects.get(payment=payment)
        assert (refund.reason, refund.amount_cents) == (RefundReason.SYSTEM, payment.amount_cents)

    def test_lost_dispute_with_a_pending_refund_stays_consistent(
        self, fake_stripe, admin_user, student, mentor
    ):
        booking, payment = paid_request(student, mentor)
        booking_services.accept_booking(booking, actor=mentor.user)
        client_for(admin_user).post(
            f"/api/v1/admin/payments/{payment.pk}/refund/",
            {"amount_cents": 2000, "note": "Partial"},
            format="json",
        )
        payment.refresh_from_db()
        obj = {
            "id": "dp_mock",
            "object": "dispute",
            "amount": payment.amount_cents,
            "currency": "usd",
            "status": "lost",
            "payment_intent": payment.provider_reference,
            "metadata": {},
        }
        assert deliver("charge.dispute.closed", obj) == "dispute_lost"
        pending = Refund.objects.get(payment=payment, reason=RefundReason.ADMIN)
        assert pending.status == RefundRecordStatus.PENDING
        refund_obj = {
            "id": pending.provider_reference,
            "object": "refund",
            "amount": pending.amount_cents,
            "currency": "usd",
            "status": "succeeded",
            "payment_intent": payment.provider_reference,
            "metadata": {"refund_id": str(pending.pk), "payment_id": str(payment.pk)},
        }
        assert deliver("refund.updated", refund_obj) == "refund_succeeded"  # no constraint violation
        payment.refresh_from_db()
        assert payment.refunded_amount_cents == payment.amount_cents


class TestBehindTheProxy:
    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_internal_server_side_calls_arent_redirected_when_forwarded_as_https(self):
        api = APIClient()
        assert api.get("/api/v1/health/").status_code == 301  # plain internal HTTP → redirect
        assert api.get("/api/v1/health/", HTTP_X_FORWARDED_PROTO="https").status_code == 200

    def test_rate_limits_follow_the_forwarded_client_ip(self, monkeypatch):
        from rest_framework.throttling import AnonRateThrottle

        monkeypatch.setattr(
            AnonRateThrottle, "THROTTLE_RATES", {**AnonRateThrottle.THROTTLE_RATES, "anon": "2/min"}
        )
        api = APIClient()
        # Same proxy address (the Next.js server), different visitors: separate buckets.
        for visitor in ("203.0.113.1", "203.0.113.2"):
            codes = [api.get("/api/v1/config/", HTTP_X_FORWARDED_FOR=visitor).status_code for _ in range(3)]
            assert codes == [200, 200, 429]


def test_notification_helpers_still_importable():
    # Guards the subject-rendering change above against import cycles.
    assert notifications.MAX_ATTEMPTS == 3
    assert hold and checkout and authorize  # helpers reused from test_payments
