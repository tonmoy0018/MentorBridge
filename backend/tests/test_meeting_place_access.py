"""Who can see the exact place of an in-person session, and that admin access is audit-logged."""

import pytest

from apps.bookings.models import Booking, BookingStatus
from apps.common.models import AuditLogEntry
from apps.mentors.models import MentorService

from .conftest import client_for, error_code, make_mentor, make_user, open_slots, service_of
from .test_bookings import BOOKINGS, book
from .test_seminars import register, schedule

pytestmark = pytest.mark.django_db

PLACE = "Café Nero, 12 King St"


def in_person_booking(student, *, status=BookingStatus.CONFIRMED):
    mentor = make_mentor(price_cents=0)
    MentorService.objects.filter(pk=service_of(mentor).pk).update(
        in_person=True, in_person_area="Soho, London"
    )
    booking_id = book(client_for(student), mentor, open_slots(mentor)[0], format="in_person").json()["id"]
    client_for(mentor.user).post(f"{BOOKINGS}{booking_id}/accept/", {"meeting_place": PLACE}, format="json")
    Booking.objects.filter(pk=booking_id).update(status=status)
    return Booking.objects.get(pk=booking_id)


def reveal(admin, path, reason="Safety report from the student"):
    return client_for(admin).post(path, {"reason": reason}, format="json")


class TestAdminReveal:
    @pytest.mark.parametrize(
        "status", [BookingStatus.CONFIRMED, BookingStatus.COMPLETED, BookingStatus.CANCELLED]
    )
    def test_any_status_with_reason_and_audit(self, student, admin_user, status):
        booking = in_person_booking(student, status=status)
        response = reveal(admin_user, f"/api/v1/admin/bookings/{booking.pk}/meeting-place/")
        assert response.status_code == 200
        assert response.json() == {
            "format": "in_person",
            "in_person_area": "Soho, London",
            "meeting_place": PLACE,
        }
        entry = AuditLogEntry.objects.get(action="booking.meeting_place_viewed")
        assert entry.actor == admin_user and entry.target_id == str(booking.pk)
        assert entry.metadata == {"reason": "Safety report from the student"}
        assert PLACE not in str(entry.metadata)

    def test_reason_required(self, student, admin_user):
        booking = in_person_booking(student)
        response = reveal(admin_user, f"/api/v1/admin/bookings/{booking.pk}/meeting-place/", reason=" ")
        assert response.status_code == 400
        assert not AuditLogEntry.objects.filter(action="booking.meeting_place_viewed").exists()

    def test_online_sessions_have_no_place(self, student, admin_user):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        response = reveal(admin_user, f"/api/v1/admin/bookings/{booking_id}/meeting-place/")
        assert response.status_code == 409 and error_code(response) == "invalid_state"

    def test_only_admins(self, student):
        booking = in_person_booking(student)
        url = f"/api/v1/admin/bookings/{booking.pk}/meeting-place/"
        assert client_for(student).post(url, {"reason": "x"}, format="json").status_code == 403
        assert client_for(booking.mentor.user).post(url, {"reason": "x"}, format="json").status_code == 403

    def test_seminar_place(self, student, admin_user):
        seminar = schedule(
            make_mentor(), format="in_person", in_person_area="Soho, London", meeting_place=PLACE
        )
        response = reveal(admin_user, f"/api/v1/admin/seminars/{seminar.pk}/meeting-place/")
        assert response.json()["meeting_place"] == PLACE
        assert AuditLogEntry.objects.filter(action="seminar.meeting_place_viewed").count() == 1
        # A seat's booking reveals its seminar's place.
        seat_id = register(student, seminar).json()["id"]
        response = reveal(admin_user, f"/api/v1/admin/bookings/{seat_id}/meeting-place/")
        assert response.json()["meeting_place"] == PLACE


class TestNoUnauditedExposure:
    def test_admin_lists_and_detail_never_include_the_place(self, student, admin_user):
        booking = in_person_booking(student)
        client = client_for(admin_user)
        listed = client.get("/api/v1/admin/bookings/").json()["results"]
        assert listed[0]["meeting_place"] is None
        assert client.get(f"/api/v1/admin/bookings/{booking.pk}/").json()["meeting_place"] is None
        schedule(
            make_mentor(first_name="Sem"), format="in_person", in_person_area="Soho", meeting_place=PLACE
        )
        assert PLACE not in str(client.get("/api/v1/admin/seminars/").json())

    def test_participants_still_see_it(self, student):
        booking = in_person_booking(student)
        assert client_for(student).get(f"{BOOKINGS}{booking.pk}/").json()["meeting_place"] == PLACE
        assert (
            client_for(booking.mentor.user).get(f"{BOOKINGS}{booking.pk}/").json()["meeting_place"] == PLACE
        )
        assert client_for(make_user()).get(f"{BOOKINGS}{booking.pk}/").status_code == 404
