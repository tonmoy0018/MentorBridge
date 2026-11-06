import threading
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.utils import timezone

from apps.bookings import services
from apps.bookings.models import Booking, BookingEvent, BookingStatus, RefundOutcome
from apps.common.exceptions import Conflict
from apps.payments.models import Payment, RefundStatus

from .conftest import captured_payment, client_for, error_code, make_mentor, make_user, open_slots, service_of

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("payments_enabled")]

BOOKINGS = "/api/v1/bookings/"


def book(client, mentor, start, *, service=None, **extra):
    service = service or service_of(mentor)
    payload = {"service_id": str(service.pk), "start_at": start.isoformat(), **extra}
    return client.post(BOOKINGS, payload, format="json")


def shift_to(booking: Booking, start):
    """Move a booking in time (tests only), keeping its length and buffer."""
    length = booking.end_at - booking.start_at
    buffer = booking.blocked_until - booking.end_at
    Booking.objects.filter(pk=booking.pk).update(
        start_at=start, end_at=start + length, blocked_until=start + length + buffer
    )
    booking.refresh_from_db()
    return booking


class TestCreateBooking:
    def test_free_service_creates_request(self, student):
        mentor = make_mentor(price_cents=0)
        start = open_slots(mentor)[0]
        response = book(client_for(student), mentor, start, student_note="Help with my CV")
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["status"] == "requested"
        assert body["respond_by"] is not None
        assert body["meeting_url"] is None  # hidden until confirmed
        assert body["price"] == {"amount_cents": 0, "currency": "USD"}
        assert body["events"][0]["to_status"] == "requested"

    def test_auto_accept_confirms_and_reveals_meeting_link(self, student):
        mentor = make_mentor(price_cents=0, auto_accept=True)
        body = book(client_for(student), mentor, open_slots(mentor)[0]).json()
        assert body["status"] == "confirmed"
        assert body["meeting_url"] == "https://meet.example.com/room"

    def test_paid_service_is_held_pending_payment_at_the_server_price(self, student, mentor):
        response = book(
            client_for(student), mentor, open_slots(mentor)[0], price_cents=1, price={"amount_cents": 1}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending_payment"
        assert body["hold_expires_at"] is not None
        assert body["price"]["amount_cents"] == 5000  # client-sent prices are ignored

        # Later price changes don't touch existing bookings.
        service = service_of(mentor)
        service.price_cents = 9999
        service.save()
        assert Booking.objects.get(pk=body["id"]).price_cents == 5000

    @pytest.mark.parametrize("offset", [timedelta(minutes=7), timedelta(seconds=30)])
    def test_start_must_be_an_offered_slot(self, student, mentor, offset):
        response = book(client_for(student), mentor, open_slots(mentor)[0] + offset)
        assert response.status_code == 409
        assert error_code(response) == "slot_unavailable"

    def test_minimum_notice_enforced(self, student, mentor):
        soon = (timezone.now() + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        assert error_code(book(client_for(student), mentor, soon)) == "slot_unavailable"

    def test_inactive_service_and_unapproved_mentor(self, student, mentor):
        start = open_slots(mentor)[0]
        service = service_of(mentor)
        service.is_active = False
        service.save()
        assert error_code(book(client_for(student), mentor, start)) == "service_unavailable"

        draft = make_mentor(first_name="Draft", approved=False)
        assert book(client_for(student), draft, start).status_code == 404

    def test_mentor_not_accepting_bookings(self, student, mentor):
        start = open_slots(mentor)[0]
        mentor.is_accepting_bookings = False
        mentor.save()
        assert error_code(book(client_for(student), mentor, start)) == "not_accepting_bookings"

    def test_only_students_can_book(self, mentor):
        other_mentor = make_mentor(first_name="Other")
        assert book(client_for(other_mentor.user), mentor, open_slots(mentor)[0]).status_code == 403

    def test_anonymous_cannot_book(self, api, mentor):
        assert book(api, mentor, open_slots(mentor)[0]).status_code == 401


class TestConflictPrevention:
    def test_same_slot_cannot_be_booked_twice(self, student, other_student, mentor):
        start = open_slots(mentor)[0]
        assert book(client_for(student), mentor, start).status_code == 201
        second = book(client_for(other_student), mentor, start)
        assert second.status_code == 409
        assert error_code(second) == "slot_unavailable"
        assert start not in open_slots(mentor)

    def test_buffer_is_respected(self, student, other_student, mentor):
        # 60-minute sessions, 15-minute buffer: the next start at +60 is blocked, +90 is free.
        start = open_slots(mentor)[0]
        assert book(client_for(student), mentor, start).status_code == 201
        assert book(client_for(other_student), mentor, start + timedelta(minutes=60)).status_code == 409
        assert book(client_for(other_student), mentor, start + timedelta(minutes=90)).status_code == 201

    def test_student_cannot_double_book_themselves(self, student, mentor):
        other = make_mentor(first_name="Other")
        start = open_slots(mentor)[0]
        assert book(client_for(student), mentor, start).status_code == 201
        response = book(client_for(student), other, start + timedelta(minutes=30))
        assert response.status_code == 409
        assert error_code(response) == "student_busy"

    def test_database_rejects_overlaps_even_without_the_service_layer(self, student, other_student, mentor):
        start = open_slots(mentor)[0]
        services.create_booking(student=student, service_id=service_of(mentor).pk, start_at=start)
        first = Booking.objects.get()
        with pytest.raises(IntegrityError), transaction.atomic():
            Booking.objects.create(
                student=other_student,
                mentor=mentor,
                service=first.service,
                service_title="x",
                duration_minutes=60,
                price_cents=0,
                currency="USD",
                start_at=start + timedelta(minutes=30),
                end_at=start + timedelta(minutes=90),
                blocked_until=start + timedelta(minutes=105),
                status=BookingStatus.REQUESTED,
            )

    def test_cancelled_bookings_free_the_slot(self, student, other_student, mentor):
        start = open_slots(mentor)[0]
        booking_id = book(client_for(student), mentor, start).json()["id"]
        client_for(student).post(f"{BOOKINGS}{booking_id}/cancel/", {}, format="json")
        assert book(client_for(other_student), mentor, start).status_code == 201


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_for_one_slot_produce_exactly_one_booking():
    mentor = make_mentor(price_cents=0)
    students = [make_user(first_name=f"S{i}") for i in range(4)]
    start = open_slots(mentor)[0]
    service_id = service_of(mentor).pk
    barrier = threading.Barrier(len(students))
    outcomes: list[str] = []

    def attempt(student):
        try:
            barrier.wait()
            services.create_booking(student=student, service_id=service_id, start_at=start)
            outcomes.append("created")
        except Conflict as exc:
            outcomes.append(exc.error_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(s,)) for s in students]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["created"] + ["slot_unavailable"] * 3
    assert Booking.objects.filter(mentor=mentor).count() == 1


class TestMentorActions:
    @pytest.fixture
    def request_booking(self, student):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        return mentor, Booking.objects.get(pk=booking_id)

    def test_accept(self, student, request_booking):
        mentor, booking = request_booking
        assert client_for(student).post(f"{BOOKINGS}{booking.pk}/accept/").status_code == 403
        response = client_for(mentor.user).post(f"{BOOKINGS}{booking.pk}/accept/")
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"
        assert response.json()["meeting_url"] == "https://meet.example.com/room"
        again = client_for(mentor.user).post(f"{BOOKINGS}{booking.pk}/accept/")
        assert error_code(again) == "invalid_state"
        assert list(BookingEvent.objects.filter(booking=booking).values_list("to_status", flat=True)) == [
            "requested",
            "confirmed",
        ]

    def test_other_mentor_cannot_see_or_act(self, request_booking):
        _, booking = request_booking
        stranger = make_mentor(first_name="Stranger")
        assert client_for(stranger.user).post(f"{BOOKINGS}{booking.pk}/accept/").status_code == 404
        assert client_for(stranger.user).get(f"{BOOKINGS}{booking.pk}/").status_code == 404

    def test_decline_requires_reason(self, request_booking):
        mentor, booking = request_booking
        client = client_for(mentor.user)
        assert client.post(f"{BOOKINGS}{booking.pk}/decline/", {}, format="json").status_code == 400
        response = client.post(f"{BOOKINGS}{booking.pk}/decline/", {"reason": "Fully booked"}, format="json")
        assert response.json()["status"] == "declined"
        assert response.json()["cancellation_reason"] == "Fully booked"

    def test_complete_only_after_start(self, request_booking):
        mentor, booking = request_booking
        client = client_for(mentor.user)
        client.post(f"{BOOKINGS}{booking.pk}/accept/")
        assert error_code(client.post(f"{BOOKINGS}{booking.pk}/complete/")) == "invalid_state"
        shift_to(booking, timezone.now() - timedelta(hours=2))
        assert client.post(f"{BOOKINGS}{booking.pk}/complete/").json()["status"] == "completed"

    def test_paid_request_cannot_be_accepted_without_authorised_payment(self, student, mentor):
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        Booking.objects.filter(pk=booking_id).update(status=BookingStatus.REQUESTED)
        response = client_for(mentor.user).post(f"{BOOKINGS}{booking_id}/accept/")
        assert response.status_code == 409
        assert error_code(response) == "payment_required"
        assert Booking.objects.get(pk=booking_id).status == BookingStatus.REQUESTED


class TestCancellationPolicy:
    def test_student_cancels_request_without_charge(self, student, mentor):
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        body = (
            client_for(student)
            .post(f"{BOOKINGS}{booking_id}/cancel/", {"reason": "Clash"}, format="json")
            .json()
        )
        assert body["status"] == "cancelled"
        assert body["refund_outcome"] == RefundOutcome.NOT_CHARGED

    def _confirmed_paid(self, student, mentor, start, captured=True):
        booking = services.create_booking(student=student, service_id=service_of(mentor).pk, start_at=start)
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.CONFIRMED)  # as if paid + accepted
        if captured:
            captured_payment(booking)
        return booking

    def test_student_cancels_confirmed_with_notice_gets_full_refund(self, student, mentor):
        booking = self._confirmed_paid(student, mentor, open_slots(mentor, days=7)[-1])
        body = client_for(student).post(f"{BOOKINGS}{booking.pk}/cancel/", {}, format="json").json()
        assert body["refund_outcome"] == RefundOutcome.FULL_REFUND
        # Executing the refund through the provider is covered in test_payments.py.
        assert Payment.objects.get(booking=booking).refunded_amount_cents == 0

    def test_student_late_cancellation_gets_no_refund(self, student):
        mentor = make_mentor(min_notice=1)
        booking = self._confirmed_paid(student, mentor, open_slots(mentor)[0])
        assert booking.start_at - timezone.now() < timedelta(hours=24)
        body = client_for(student).post(f"{BOOKINGS}{booking.pk}/cancel/", {}, format="json").json()
        assert body["refund_outcome"] == RefundOutcome.NO_REFUND
        assert Payment.objects.get(booking=booking).refund_status == RefundStatus.NONE

    def test_mentor_cancellation_needs_reason_and_refunds_in_full(self, student):
        mentor = make_mentor(min_notice=1)
        booking = self._confirmed_paid(student, mentor, open_slots(mentor)[0])
        client = client_for(mentor.user)
        assert client.post(f"{BOOKINGS}{booking.pk}/cancel/", {}, format="json").status_code == 400
        body = client.post(f"{BOOKINGS}{booking.pk}/cancel/", {"reason": "Ill"}, format="json").json()
        assert body["refund_outcome"] == RefundOutcome.FULL_REFUND

    def test_mentor_must_decline_rather_than_cancel_requests(self, student):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        response = client_for(mentor.user).post(
            f"{BOOKINGS}{booking_id}/cancel/", {"reason": "x"}, format="json"
        )
        assert error_code(response) == "invalid_state"

    def test_cannot_cancel_after_start_or_when_closed(self, student):
        mentor = make_mentor(price_cents=0, auto_accept=True)
        booking = Booking.objects.get(
            pk=book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        )
        shift_to(booking, timezone.now() - timedelta(minutes=10))
        assert (
            error_code(client_for(student).post(f"{BOOKINGS}{booking.pk}/cancel/", {}, format="json"))
            == "invalid_state"
        )

    def test_other_student_cannot_cancel(self, student, other_student, mentor):
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        assert (
            client_for(other_student).post(f"{BOOKINGS}{booking_id}/cancel/", {}, format="json").status_code
            == 404
        )


class TestListingAndExpiry:
    def test_users_only_see_their_own_bookings(self, student, other_student, mentor):
        slots = open_slots(mentor)
        mine = book(client_for(student), mentor, slots[0]).json()["id"]
        theirs = book(client_for(other_student), mentor, slots[4]).json()["id"]
        assert [b["id"] for b in client_for(student).get(BOOKINGS).json()["results"]] == [mine]
        assert client_for(student).get(f"{BOOKINGS}{theirs}/").status_code == 404
        mentor_view = {b["id"] for b in client_for(mentor.user).get(BOOKINGS).json()["results"]}
        assert mentor_view == {mine, theirs}

    def test_scope_filters(self, student, mentor):
        booking = Booking.objects.get(
            pk=book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        )
        client = client_for(student)
        assert client.get(f"{BOOKINGS}?scope=upcoming").json()["count"] == 1
        assert client.get(f"{BOOKINGS}?scope=past").json()["count"] == 0
        Booking.objects.filter(pk=booking.pk).update(status=BookingStatus.EXPIRED)
        assert client.get(f"{BOOKINGS}?scope=upcoming").json()["count"] == 0
        assert client.get(f"{BOOKINGS}?status=expired").json()["count"] == 1

    def test_expiry_command(self, student, mentor):
        slots = open_slots(mentor)
        held = services.create_booking(student=student, service_id=service_of(mentor).pk, start_at=slots[0])
        past_grace = timezone.now() - timedelta(minutes=10)
        Booking.objects.filter(pk=held.pk).update(hold_expires_at=past_grace)

        free_mentor = make_mentor(first_name="Free", price_cents=0)
        requested = services.create_booking(
            student=student, service_id=service_of(free_mentor).pk, start_at=open_slots(free_mentor)[6]
        )
        Booking.objects.filter(pk=requested.pk).update(respond_by=timezone.now() - timedelta(minutes=1))

        call_command("expire_bookings")
        assert Booking.objects.get(pk=held.pk).status == BookingStatus.EXPIRED
        assert Booking.objects.get(pk=requested.pk).status == BookingStatus.EXPIRED
        assert slots[0] in open_slots(mentor)  # the slot is free again
