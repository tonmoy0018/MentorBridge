"""Group seminars: scheduling, seats, registration, cancellation and completion."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus, RefundOutcome
from apps.seminars.models import Seminar, SeminarStatus

from .conftest import client_for, error_code, make_mentor, make_user, open_slots, service_of
from .test_bookings import BOOKINGS, book

pytestmark = pytest.mark.django_db

MY_SEMINARS = "/api/v1/me/mentor/seminars/"


def at(days=3, hour=18):
    start = (timezone.now() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return start


def schedule(mentor, *, start=None, capacity=3, price_cents=0, **extra):
    payload = {
        "service_id": str(service_of(mentor).pk),
        "start_at": (start or at()).isoformat(),
        "duration_minutes": 90,
        "capacity": capacity,
        "price_cents": price_cents,
        **extra,
    }
    response = client_for(mentor.user).post(MY_SEMINARS, payload, format="json")
    assert response.status_code == 201, response.json()
    return Seminar.objects.get(pk=response.json()["id"])


def register(student, seminar):
    return client_for(student).post(f"/api/v1/seminars/{seminar.pk}/register/")


class TestScheduling:
    def test_schedule_and_show_publicly(self):
        mentor = make_mentor(price_cents=0)
        seminar = schedule(mentor, title="Group career Q&A")
        assert seminar.end_at - seminar.start_at == timedelta(minutes=90)
        profile = client_for(make_user()).get(f"/api/v1/mentors/{mentor.slug}/").json()
        assert [(s["title"], s["seats_left"]) for s in profile["seminars"]] == [("Group career Q&A", 3)]
        assert "attendees" not in profile["seminars"][0] and "meeting_place" not in profile["seminars"][0]

    def test_title_defaults_to_the_service(self):
        mentor = make_mentor()
        assert schedule(mentor).title == service_of(mentor).title

    def test_seminar_blocks_one_to_one_slots(self):
        mentor = make_mentor(price_cents=0, buffer=15)
        seminar = schedule(mentor)
        slots = open_slots(mentor, days=5)
        blocked_until = seminar.end_at + timedelta(minutes=15)
        assert not any(seminar.start_at - timedelta(minutes=60) < s < blocked_until for s in slots)

    def test_cannot_overlap_a_booking_or_another_seminar(self, student):
        mentor = make_mentor(price_cents=0)
        start = open_slots(mentor, days=5)[10]
        assert book(client_for(student), mentor, start).status_code == 201
        payload = {
            "service_id": str(service_of(mentor).pk),
            "start_at": start.isoformat(),
            "duration_minutes": 60,
            "capacity": 5,
            "price_cents": 0,
        }
        response = client_for(mentor.user).post(MY_SEMINARS, payload, format="json")
        assert response.status_code == 409 and error_code(response) == "mentor_busy"

        seminar = schedule(mentor, start=at(days=4))
        payload["start_at"] = (seminar.start_at + timedelta(minutes=30)).isoformat()
        response = client_for(mentor.user).post(MY_SEMINARS, payload, format="json")
        assert response.status_code == 409 and error_code(response) == "mentor_busy"

    def test_validation(self):
        mentor = make_mentor()
        client = client_for(mentor.user)
        base = {
            "service_id": str(service_of(mentor).pk),
            "duration_minutes": 60,
            "capacity": 5,
            "price_cents": 0,
        }
        past = client.post(MY_SEMINARS, {**base, "start_at": timezone.now().isoformat()}, format="json")
        assert past.status_code == 400
        no_area = client.post(
            MY_SEMINARS, {**base, "start_at": at().isoformat(), "format": "in_person"}, format="json"
        )
        assert no_area.status_code == 400 and "in_person_area" in no_area.json()["error"]["details"]["fields"]
        other = make_mentor(first_name="Other")
        theirs = client.post(
            MY_SEMINARS,
            {**base, "start_at": at().isoformat(), "service_id": str(service_of(other).pk)},
            format="json",
        )
        assert theirs.status_code == 400

    def test_students_cannot_schedule(self, student):
        assert client_for(student).get(MY_SEMINARS).status_code == 403


class TestRegistration:
    def test_free_seat_is_confirmed_and_hidden_from_mentor_bookings(self, student, after_commit):
        mentor = make_mentor()
        seminar = schedule(mentor, price_cents=0)
        with after_commit():
            response = register(student, seminar)
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == BookingStatus.CONFIRMED and body["seminar"]["id"] == str(seminar.pk)
        assert body["meeting_url"] == mentor.meeting_url
        # One email, to the student only.
        assert [m.to for m in mail.outbox] == [[student.email]]
        assert "group seminar" in mail.outbox[0].body
        assert client_for(mentor.user).get(BOOKINGS).json()["count"] == 0
        listed = client_for(mentor.user).get(MY_SEMINARS).json()[0]
        assert listed["seats_taken"] == 1 and listed["attendees"][0]["display_name"] == student.full_name

    def test_seats_run_out_and_no_double_registration(self, student, other_student):
        seminar = schedule(make_mentor(), capacity=2)
        assert register(student, seminar).status_code == 201
        again = register(student, seminar)
        assert again.status_code == 409 and error_code(again) == "already_registered"
        assert register(other_student, seminar).status_code == 201
        full = register(make_user(), seminar)
        assert full.status_code == 409 and error_code(full) == "seminar_full"

    def test_cancelling_frees_the_seat(self, student, other_student):
        seminar = schedule(make_mentor(), capacity=2)
        booking_id = register(student, seminar).json()["id"]
        register(other_student, seminar)
        assert client_for(student).post(f"{BOOKINGS}{booking_id}/cancel/").status_code == 200
        assert register(make_user(), seminar).status_code == 201

    def test_student_cannot_be_in_two_places(self, student):
        mentor = make_mentor(price_cents=0)
        other = make_mentor(first_name="Other", price_cents=0)
        seminar = schedule(mentor)
        same_time = next(s for s in open_slots(other, days=5) if s == seminar.start_at)
        assert book(client_for(student), other, same_time).status_code == 201
        response = register(student, seminar)
        assert response.status_code == 409 and error_code(response) == "student_busy"

    def test_paid_seats_need_payments(self, student):
        seminar = schedule(make_mentor(), price_cents=2500)
        response = register(student, seminar)
        assert response.status_code == 503 and error_code(response) == "payments_unavailable"
        assert not Booking.objects.exists()

    def test_paid_seat_is_held_then_confirmed_by_payment(self, student, payments_enabled, fake_stripe):
        from .test_payments import authorize, checkout

        seminar = schedule(make_mentor(), price_cents=2500)
        response = register(student, seminar)
        assert response.json()["status"] == BookingStatus.PENDING_PAYMENT
        booking = Booking.objects.get(pk=response.json()["id"])
        payment = checkout(student, booking)
        assert authorize(payment) == "authorized"
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED  # no mentor answer for seminar seats
        assert any("capture" in name for name in fake_stripe.names())

    def test_closed_after_start_or_cancel(self, student):
        mentor = make_mentor()
        seminar = schedule(mentor)
        Seminar.objects.filter(pk=seminar.pk).update(start_at=timezone.now() - timedelta(minutes=5))
        response = register(student, seminar)
        assert response.status_code == 409 and error_code(response) == "seminar_closed"

    def test_meeting_place_only_for_registered_students(self, student):
        mentor = make_mentor()
        seminar = schedule(
            mentor, format="in_person", in_person_area="Soho, London", meeting_place="Room 4, 1 Main St"
        )
        body = register(student, seminar).json()
        assert body["format"] == "in_person" and body["meeting_place"] == "Room 4, 1 Main St"
        public = client_for(make_user()).get(f"/api/v1/mentors/{mentor.slug}/").json()["seminars"][0]
        assert public["in_person_area"] == "Soho, London"
        assert "Room 4" not in str(public)


class TestMentorActions:
    def test_cancel_seminar_cancels_every_seat_and_tells_each_student(
        self, student, other_student, after_commit
    ):
        mentor = make_mentor()
        seminar = schedule(mentor)
        register(student, seminar)
        register(other_student, seminar)
        mail.outbox.clear()
        with after_commit():
            response = client_for(mentor.user).post(
                f"{MY_SEMINARS}{seminar.pk}/cancel/", {"reason": "I'm unwell"}, format="json"
            )
        assert response.status_code == 200 and response.json()["status"] == SeminarStatus.CANCELLED
        seats = Booking.objects.filter(seminar=seminar)
        assert {b.status for b in seats} == {BookingStatus.CANCELLED}
        assert sorted(m.to[0] for m in mail.outbox) == sorted([student.email, other_student.email])
        assert all("I'm unwell" in m.body for m in mail.outbox)
        # The time is free again for one-to-one bookings.
        assert any(seminar.start_at <= s < seminar.end_at for s in open_slots(mentor, days=5))

    def test_paid_seats_are_refunded_in_full(self, student):
        mentor = make_mentor()
        seminar = schedule(mentor, price_cents=0)
        booking = Booking.objects.get(pk=register(student, seminar).json()["id"])
        Booking.objects.filter(pk=booking.pk).update(price_cents=2500)  # as if paid
        client_for(mentor.user).post(
            f"{MY_SEMINARS}{seminar.pk}/cancel/", {"reason": "Venue closed"}, format="json"
        )
        booking.refresh_from_db()
        assert booking.refund_outcome == RefundOutcome.FULL_REFUND

    def test_mentor_cannot_cancel_a_single_seat(self, student):
        mentor = make_mentor()
        seminar = schedule(mentor)
        booking = Booking.objects.get(pk=register(student, seminar).json()["id"])
        from apps.bookings.services import cancel_booking
        from apps.common.exceptions import Conflict

        with pytest.raises(Conflict):
            cancel_booking(booking, actor=mentor.user, reason="No")

    def test_complete_lets_students_review(self, student):
        mentor = make_mentor()
        seminar = schedule(mentor)
        booking_id = register(student, seminar).json()["id"]
        early = client_for(mentor.user).post(f"{MY_SEMINARS}{seminar.pk}/complete/")
        assert early.status_code == 409
        Seminar.objects.filter(pk=seminar.pk).update(start_at=timezone.now() - timedelta(hours=2))
        assert client_for(mentor.user).post(f"{MY_SEMINARS}{seminar.pk}/complete/").status_code == 200
        assert Booking.objects.get(pk=booking_id).status == BookingStatus.COMPLETED

    def test_terms_locked_once_students_register(self, student):
        mentor = make_mentor()
        seminar = schedule(mentor, capacity=3)
        url = f"{MY_SEMINARS}{seminar.pk}/"
        client = client_for(mentor.user)
        assert client.patch(url, {"price_cents": 1000}, format="json").status_code == 200  # nobody yet
        client.patch(url, {"price_cents": 0}, format="json")
        register(student, seminar)
        response = client.patch(url, {"start_at": at(days=5).isoformat()}, format="json")
        assert response.status_code == 409 and error_code(response) == "seminar_has_registrations"
        register(make_user(), seminar)
        register(make_user(), seminar)  # 3 of 3 seats taken
        assert client.patch(url, {"capacity": 2}, format="json").status_code == 400
        assert client.patch(url, {"title": "New title", "capacity": 10}, format="json").status_code == 200

    def test_admin_can_cancel(self, student, admin_user):
        seminar = schedule(make_mentor())
        register(student, seminar)
        response = client_for(admin_user).post(
            f"/api/v1/admin/seminars/{seminar.pk}/cancel/", {"reason": "Policy breach"}, format="json"
        )
        assert response.status_code == 200
        assert Booking.objects.get(seminar=seminar).status == BookingStatus.CANCELLED
