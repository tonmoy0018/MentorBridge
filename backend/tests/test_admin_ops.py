"""Admin operations: permissions on every admin endpoint, moderation, booking oversight, audit, stats."""

import re
import uuid

import pytest
from django.urls import URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingStatus, RefundOutcome
from apps.common.models import AuditLogEntry
from apps.notifications.models import EmailNotification
from apps.payments.models import Refund, RefundReason
from apps.reviews.models import ReviewStatus
from apps.reviews.services import create_review

from .conftest import client_for, error_code, make_mentor, open_slots, service_of
from .test_payments import confirmed_paid

pytestmark = pytest.mark.django_db


def _admin_api_paths() -> list[str]:
    """Every route under /api/v1/admin/, with sample path parameters."""

    def walk(patterns, prefix):
        for pattern in patterns:
            route = prefix + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                yield from walk(pattern.url_patterns, route)
            else:
                yield route

    paths = []
    for route in walk(get_resolver().url_patterns, ""):
        if route.startswith("api/v1/admin/"):
            route = re.sub(r"<uuid:\w+>", str(uuid.uuid4()), route)
            route = re.sub(r"<int:\w+>", "1", route)
            paths.append("/" + re.sub(r"<(?:slug|str):\w+>", "x", route))
    return paths


ADMIN_PATHS = _admin_api_paths()


class TestAdminPermissions:
    def test_route_discovery_found_the_admin_api(self):
        assert len(ADMIN_PATHS) >= 20
        assert any("/refund/" in p for p in ADMIN_PATHS) and any("audit-log" in p for p in ADMIN_PATHS)

    @pytest.mark.parametrize("path", ADMIN_PATHS)
    @pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
    def test_every_admin_operation_requires_an_admin(self, path, method, student, mentor):
        assert getattr(APIClient(), method)(path, {}, format="json").status_code == 401
        for user in (student, mentor.user):
            assert getattr(client_for(user), method)(path, {}, format="json").status_code == 403


class TestReviewModeration:
    @pytest.fixture
    def review(self, student):
        mentor = make_mentor(price_cents=0)
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.COMPLETED)
        booking.refresh_from_db()
        return create_review(booking=booking, student=student, rating=2, comment="Didn't show up on time")

    def test_hide_and_publish_recalculate_the_rating(self, api, admin_user, review):
        admin = client_for(admin_user)
        mentor = review.mentor
        assert admin.post(f"/api/v1/admin/reviews/{review.pk}/hide/", {}, format="json").status_code == 400

        hidden = admin.post(f"/api/v1/admin/reviews/{review.pk}/hide/", {"reason": "Abusive"}, format="json")
        assert hidden.status_code == 200 and hidden.json()["status"] == ReviewStatus.HIDDEN
        mentor.refresh_from_db()
        assert mentor.rating_count == 0
        assert api.get(f"/api/v1/mentors/{mentor.slug}/reviews/").json()["count"] == 0
        assert admin.get("/api/v1/admin/reviews/?status=hidden").json()["count"] == 1

        assert admin.post(f"/api/v1/admin/reviews/{review.pk}/publish/", {}, format="json").status_code == 200
        mentor.refresh_from_db()
        assert mentor.rating_count == 1
        actions = set(AuditLogEntry.objects.filter(actor=admin_user).values_list("action", flat=True))
        assert {"review.hidden", "review.published"} <= actions


class TestBookingOversight:
    def test_admin_cancel_refunds_and_tells_both_parties(
        self, fake_stripe, after_commit, admin_user, student, mentor
    ):
        booking, payment = confirmed_paid(student, mentor)
        admin = client_for(admin_user)
        url = f"/api/v1/admin/bookings/{booking.pk}/cancel/"
        assert admin.post(url, {}, format="json").status_code == 400  # reason required

        with after_commit():
            response = admin.post(url, {"reason": "Mentor account compromised"}, format="json")
        assert response.status_code == 200
        assert (response.json()["status"], response.json()["refund_outcome"]) == (
            BookingStatus.CANCELLED,
            RefundOutcome.FULL_REFUND,
        )
        assert Refund.objects.get(payment=payment).reason == RefundReason.ADMIN
        assert EmailNotification.objects.filter(template="booking_cancelled").count() == 2
        entry = AuditLogEntry.objects.get(action="booking.cancelled_by_admin")
        assert entry.actor == admin_user

    def test_admin_cancel_without_refund(self, fake_stripe, after_commit, admin_user, student, mentor):
        booking, _ = confirmed_paid(student, mentor)
        with after_commit():
            response = client_for(admin_user).post(
                f"/api/v1/admin/bookings/{booking.pk}/cancel/",
                {"reason": "Session held outside the platform", "refund": False},
                format="json",
            )
        assert response.json()["refund_outcome"] == RefundOutcome.NO_REFUND
        assert "refund" not in fake_stripe.names()

    def test_finished_bookings_cannot_be_cancelled(self, admin_user, student):
        mentor = make_mentor(price_cents=0, auto_accept=True)
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.COMPLETED)
        response = client_for(admin_user).post(
            f"/api/v1/admin/bookings/{booking.pk}/cancel/", {"reason": "x"}, format="json"
        )
        assert response.status_code == 409
        assert error_code(response) == "invalid_state"


class TestAuditLogAndStats:
    def test_audit_log_is_filterable(self, admin_user, mentor):
        admin = client_for(admin_user)
        admin.post(f"/api/v1/admin/users/{mentor.user.pk}/suspend/", {"reason": "Spam"}, format="json")
        entries = admin.get("/api/v1/admin/audit-log/?action=user.").json()["results"]
        assert [e["action"] for e in entries] == ["user.suspended"]
        assert entries[0]["actor_name"] == admin_user.full_name

    def test_stats_period(self, admin_user, student):
        mentor = make_mentor(price_cents=0)
        booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        admin = client_for(admin_user)
        period = admin.get("/api/v1/admin/stats/").json()["period"]
        assert period["bookings_created"] == 1
        assert period["new_users"] >= 3
        assert (
            admin.get("/api/v1/admin/stats/?from=2020-01-01&to=2020-01-31").json()["period"][
                "bookings_created"
            ]
            == 0
        )
        assert admin.get("/api/v1/admin/stats/?from=2020-02-01&to=2020-01-01").status_code == 400
        assert admin.get("/api/v1/admin/stats/?from=not-a-date").status_code == 400
