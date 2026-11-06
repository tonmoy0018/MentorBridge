"""Behaviour the web app relies on: payment availability, admin flag, review state, config."""

import pytest

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingStatus
from apps.users.models import Role, User

from .conftest import client_for, error_code, make_mentor, make_user, open_slots, service_of

pytestmark = pytest.mark.django_db


def test_paid_sessions_are_refused_while_payments_are_disabled(student, mentor):
    start = open_slots(mentor)[0]
    response = client_for(student).post(
        "/api/v1/bookings/",
        {"service_id": str(service_of(mentor).pk), "start_at": start.isoformat()},
        format="json",
    )
    assert response.status_code == 503
    assert error_code(response) == "payments_unavailable"
    assert not Booking.objects.exists()
    assert start in open_slots(mentor)  # nothing was held


def test_free_sessions_still_book_while_payments_are_disabled(student):
    mentor = make_mentor(price_cents=0)
    response = client_for(student).post(
        "/api/v1/bookings/",
        {"service_id": str(service_of(mentor).pk), "start_at": open_slots(mentor)[0].isoformat()},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["status"] == "requested"


def test_public_config(api, db):
    assert api.get("/api/v1/config/").json() == {
        "payments_enabled": False,
        "payments_livemode": False,
        "currency": "USD",
        "booking_hold_minutes": 30,
        "mentor_response_hours": 48,
        "free_cancellation_hours": 24,
        "require_verified_email": False,
    }


def test_is_admin_requires_admin_role_and_staff(student, admin_user):
    assert client_for(student).get("/api/v1/auth/me/").json()["is_admin"] is False
    assert client_for(admin_user).get("/api/v1/auth/me/").json()["is_admin"] is True
    not_staff = make_user(Role.ADMIN)
    User.objects.filter(pk=not_staff.pk).update(is_staff=False)
    not_staff.refresh_from_db()
    assert client_for(not_staff).get("/api/v1/auth/me/").json()["is_admin"] is False


def test_has_review_reflects_review_state(student):
    mentor = make_mentor(price_cents=0)
    booking = booking_services.create_booking(
        student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
    )
    Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.COMPLETED)
    client = client_for(student)
    assert client.get(f"/api/v1/bookings/{booking.pk}/").json()["has_review"] is False
    client.post(f"/api/v1/bookings/{booking.pk}/review/", {"rating": 5}, format="json")
    listed = client.get("/api/v1/bookings/").json()["results"][0]
    assert listed["has_review"] is True
