from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingStatus
from apps.common.models import AuditLogEntry
from apps.moderation.models import Report
from apps.payments.models import PaymentStatus, Payout, PayoutStatus
from apps.reviews.models import ReviewStatus
from apps.reviews.services import create_review
from apps.users.models import Role, User

from .conftest import (
    PASSWORD,
    captured_payment,
    client_for,
    error_code,
    make_mentor,
    make_user,
    open_slots,
    service_of,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("payments_enabled")]

ADMIN_ENDPOINTS = [
    "/api/v1/admin/stats/",
    "/api/v1/admin/users/",
    "/api/v1/admin/verification-requests/",
    "/api/v1/admin/bookings/",
    "/api/v1/admin/payments/",
    "/api/v1/admin/reports/",
]


class TestRoleBoundaries:
    @pytest.mark.parametrize("url", ADMIN_ENDPOINTS)
    def test_admin_endpoints_require_admin(self, api, student, mentor, admin_user, url):
        assert api.get(url).status_code == 401
        assert client_for(student).get(url).status_code == 403
        assert client_for(mentor.user).get(url).status_code == 403
        assert client_for(admin_user).get(url).status_code == 200

    def test_admin_role_without_staff_flag_is_not_enough(self, db):
        fake_admin = make_user(Role.ADMIN)
        User.objects.filter(pk=fake_admin.pk).update(is_staff=False)
        fake_admin.refresh_from_db()
        assert client_for(fake_admin).get("/api/v1/admin/users/").status_code == 403

    @pytest.mark.parametrize(
        "url",
        ["/api/v1/me/mentor/profile/", "/api/v1/me/mentor/services/", "/api/v1/me/mentor/earnings/summary/"],
    )
    def test_mentor_area(self, api, student, mentor, url):
        assert api.get(url).status_code == 401
        assert client_for(student).get(url).status_code == 403
        assert client_for(mentor.user).get(url).status_code == 200

    @pytest.mark.parametrize("url", ["/api/v1/me/student/goals/", "/api/v1/me/student/saved-mentors/"])
    def test_student_area(self, student, mentor, url):
        assert client_for(mentor.user).get(url).status_code == 403
        assert client_for(student).get(url).status_code == 200

    def test_mentor_profile_endpoint_only_ever_edits_your_own(self, mentor):
        other = make_mentor(first_name="Other")
        client_for(mentor.user).patch(
            "/api/v1/me/mentor/profile/", {"headline": "Changed headline"}, format="json"
        )
        other.refresh_from_db()
        assert other.headline != "Changed headline"

    def test_mentor_sees_student_names_but_no_contact_details(self, student, mentor):
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        body = client_for(mentor.user).get(f"/api/v1/bookings/{booking.pk}/").json()
        assert body["student"]["display_name"] == "Jordan Lee"
        assert "email" not in str(body).lower()


class TestPayments:
    def _captured(self, student, mentor, *, completed: bool):
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        if completed:
            past = timezone.now() - timedelta(days=2)
            Booking.objects.filter(pk=booking.pk).update(
                status=BookingStatus.COMPLETED,
                start_at=past,
                end_at=past + timedelta(hours=1),
                blocked_until=past + timedelta(hours=1),
                completed_at=past + timedelta(hours=1),
            )
        else:
            Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.CONFIRMED)
        return captured_payment(booking, provider_reference=f"pi_{booking.pk.hex}")

    def test_no_api_can_modify_payments(self, admin_user, student, mentor):
        payment = self._captured(student, mentor, completed=False)
        admin = client_for(admin_user)
        url = f"/api/v1/admin/payments/{payment.pk}/"
        assert admin.get(url).status_code == 200
        for method in ("patch", "put", "delete"):
            assert getattr(admin, method)(url, {"status": "refunded"}, format="json").status_code == 405
        assert admin.post("/api/v1/admin/payments/", {"amount_cents": 1}, format="json").status_code == 405
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.CAPTURED

    def test_earnings_are_derived_from_real_records(self, student, other_student, mentor):
        self._captured(student, mentor, completed=True)
        other_mentor_slot = open_slots(mentor)[4]
        pending_booking = booking_services.create_booking(
            student=other_student, service_id=service_of(mentor).pk, start_at=other_mentor_slot
        )
        Booking.objects.filter(pk=pending_booking.pk).update(status=BookingStatus.CONFIRMED)
        captured_payment(pending_booking)
        Payout.objects.create(mentor=mentor, amount_cents=2000, currency="USD", status=PayoutStatus.PAID)

        client = client_for(mentor.user)
        summary = client.get("/api/v1/me/mentor/earnings/summary/").json()
        assert summary["available"]["amount_cents"] == 4250 - 2000
        assert summary["pending"]["amount_cents"] == 4250
        assert summary["paid_out"]["amount_cents"] == 2000
        assert summary["lifetime"]["amount_cents"] == 8500
        kinds = [e["kind"] for e in client.get("/api/v1/me/mentor/earnings/ledger/").json()["results"]]
        assert sorted(kinds) == ["earning", "earning", "payout"]
        assert client.get("/api/v1/me/mentor/payouts/").json()["count"] == 1

    def test_mentor_cannot_see_other_mentors_earnings(self, student, mentor):
        self._captured(student, mentor, completed=True)
        other = make_mentor(first_name="Other")
        assert (
            client_for(other.user)
            .get("/api/v1/me/mentor/earnings/summary/")
            .json()["lifetime"]["amount_cents"]
            == 0
        )

    def test_admin_stats(self, admin_user, student, mentor):
        self._captured(student, mentor, completed=True)
        stats = client_for(admin_user).get("/api/v1/admin/stats/").json()
        assert stats["users"]["student"] == 1
        assert stats["mentors_by_status"]["approved"] == 1
        assert stats["bookings_by_status"]["completed"] == 1
        assert stats["gross_booking_value"] == {"amount_cents": 5000, "currency": "USD"}
        assert stats["platform_fees"]["amount_cents"] == 750


class TestUserManagement:
    def test_suspend_and_reactivate(self, api, admin_user, mentor):
        mentor_client = client_for(mentor.user)
        admin = client_for(admin_user)
        url = f"/api/v1/admin/users/{mentor.user.pk}/"
        assert admin.post(f"{url}suspend/", {}, format="json").status_code == 400  # reason required
        assert (
            admin.post(f"{url}suspend/", {"reason": "Fake profile"}, format="json").json()["is_active"]
            is False
        )

        assert mentor_client.get("/api/v1/auth/me/").status_code == 401  # existing session stops working
        login = api.post(
            "/api/v1/auth/login/", {"email": mentor.user.email, "password": PASSWORD}, format="json"
        )
        assert error_code(login) == "invalid_credentials"
        assert api.get(f"/api/v1/mentors/{mentor.slug}/").status_code == 404
        assert AuditLogEntry.objects.filter(action="user.suspended", target_id=str(mentor.user.pk)).exists()

        admin.post(f"{url}reactivate/")
        assert api.get(f"/api/v1/mentors/{mentor.slug}/").status_code == 200

    def test_cannot_suspend_self_or_other_admins(self, admin_user):
        other_admin = User.objects.create_superuser(
            email="root2@example.com", password=PASSWORD, first_name="R", last_name="T"
        )
        admin = client_for(admin_user)
        assert (
            admin.post(
                f"/api/v1/admin/users/{admin_user.pk}/suspend/", {"reason": "x"}, format="json"
            ).status_code
            == 403
        )
        assert (
            admin.post(
                f"/api/v1/admin/users/{other_admin.pk}/suspend/", {"reason": "x"}, format="json"
            ).status_code
            == 403
        )

    def test_search_users(self, admin_user, student, mentor):
        results = client_for(admin_user).get("/api/v1/admin/users/?role=mentor").json()["results"]
        assert [u["id"] for u in results] == [str(mentor.user.pk)]


class TestModeration:
    @pytest.fixture
    def review(self, student):
        mentor = make_mentor(price_cents=0)
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.COMPLETED)
        booking.refresh_from_db()
        return create_review(booking=booking, student=student, rating=1, comment="Spam link here")

    def test_report_and_resolve_by_hiding_review(self, api, admin_user, other_student, review):
        reporter = client_for(other_student)
        payload = {"target_type": "review", "target_id": str(review.pk), "reason": "spam"}
        created = reporter.post("/api/v1/reports/", payload, format="json")
        assert created.status_code == 201
        assert error_code(reporter.post("/api/v1/reports/", payload, format="json")) == "already_exists"

        admin = client_for(admin_user)
        queue = admin.get("/api/v1/admin/reports/").json()["results"]
        assert queue[0]["reporter_display_name"] == "Sam Other"
        resolved = admin.post(
            f"/api/v1/admin/reports/{created.json()['id']}/resolve/",
            {"resolution": "actioned", "note": "Removed spam", "hide_review": True},
            format="json",
        )
        assert resolved.status_code == 200
        review.refresh_from_db()
        assert review.status == ReviewStatus.HIDDEN
        review.mentor.refresh_from_db()
        assert review.mentor.rating_count == 0
        assert api.get(f"/api/v1/mentors/{review.mentor.slug}/reviews/").json()["count"] == 0
        assert admin.get("/api/v1/admin/reports/?status=resolved").json()["count"] == 1

    def test_reports_cannot_probe_unrelated_users_or_bookings(self, student, other_student, mentor):
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        stranger = client_for(other_student)
        for target_type, target_id in [("user", student.pk), ("booking", booking.pk)]:
            response = stranger.post(
                "/api/v1/reports/",
                {"target_type": target_type, "target_id": str(target_id), "reason": "other"},
                format="json",
            )
            assert response.status_code == 404
        assert not Report.objects.exists()
        # A participant can report the booking.
        mine = client_for(student).post(
            "/api/v1/reports/",
            {"target_type": "booking", "target_id": str(booking.pk), "reason": "no_show"},
            format="json",
        )
        assert mine.status_code == 201


def test_health(api, db):
    assert api.get("/api/v1/health/").json() == {"status": "ok", "db": "ok"}


def test_openapi_schema_is_served(api, db):
    response = api.get("/api/v1/schema/")
    assert response.status_code == 200
    assert b"MentorBridge API" in response.content
