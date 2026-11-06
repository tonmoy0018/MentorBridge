from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingStatus
from apps.reviews.models import Review
from apps.students.models import SavedMentor

from .conftest import client_for, error_code, make_mentor, open_slots, service_of

pytestmark = pytest.mark.django_db


def completed_booking(student, mentor) -> Booking:
    booking = booking_services.create_booking(
        student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
    )
    past = timezone.now() - timedelta(days=1)
    Booking.objects.filter(pk=booking.pk).update(
        status=BookingStatus.COMPLETED,
        start_at=past,
        end_at=past + timedelta(hours=1),
        blocked_until=past + timedelta(hours=1),
    )
    booking.refresh_from_db()
    return booking


class TestReviews:
    def test_student_reviews_completed_session(self, api, student):
        mentor = make_mentor(price_cents=0)
        booking = completed_booking(student, mentor)
        response = client_for(student).post(
            f"/api/v1/bookings/{booking.pk}/review/", {"rating": 4, "comment": "Very helpful."}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["reviewer_display_name"] == "Jordan L."

        mentor.refresh_from_db()
        assert str(mentor.rating_avg) == "4.00" and mentor.rating_count == 1
        public = api.get(f"/api/v1/mentors/{mentor.slug}/reviews/").json()
        assert public["count"] == 1
        assert public["results"][0]["service_title"] == "Career chat"
        assert api.get(f"/api/v1/mentors/{mentor.slug}/").json()["rating_avg"] == "4.00"

    def test_cannot_review_before_completion(self, student):
        mentor = make_mentor(price_cents=0)
        booking = booking_services.create_booking(
            student=student, service_id=service_of(mentor).pk, start_at=open_slots(mentor)[0]
        )
        response = client_for(student).post(
            f"/api/v1/bookings/{booking.pk}/review/", {"rating": 5}, format="json"
        )
        assert response.status_code == 409
        assert error_code(response) == "not_eligible"

    def test_cannot_review_someone_elses_session(self, student, other_student):
        booking = completed_booking(student, make_mentor(price_cents=0))
        response = client_for(other_student).post(
            f"/api/v1/bookings/{booking.pk}/review/", {"rating": 5}, format="json"
        )
        assert response.status_code == 404
        assert not Review.objects.exists()

    def test_one_review_per_booking(self, student):
        booking = completed_booking(student, make_mentor(price_cents=0))
        client = client_for(student)
        assert (
            client.post(f"/api/v1/bookings/{booking.pk}/review/", {"rating": 5}, format="json").status_code
            == 201
        )
        again = client.post(f"/api/v1/bookings/{booking.pk}/review/", {"rating": 1}, format="json")
        assert error_code(again) == "already_exists"

    @pytest.mark.parametrize("rating", [0, 6, "five"])
    def test_rating_validation(self, student, rating):
        booking = completed_booking(student, make_mentor(price_cents=0))
        response = client_for(student).post(
            f"/api/v1/bookings/{booking.pk}/review/", {"rating": rating}, format="json"
        )
        assert response.status_code == 400

    def test_mentors_cannot_write_reviews(self, student):
        mentor = make_mentor(price_cents=0)
        booking = completed_booking(student, mentor)
        assert (
            client_for(mentor.user)
            .post(f"/api/v1/bookings/{booking.pk}/review/", {"rating": 5}, format="json")
            .status_code
            == 403
        )


class TestSavedMentors:
    URL = "/api/v1/me/student/saved-mentors/"

    def test_save_list_remove_idempotently(self, student, mentor):
        client = client_for(student)
        assert client.put(f"{self.URL}{mentor.slug}/").status_code == 204
        assert client.put(f"{self.URL}{mentor.pk}/").status_code == 204  # by UUID too; still one row
        assert SavedMentor.objects.filter(student=student).count() == 1
        listed = client.get(self.URL).json()
        assert [m["slug"] for m in listed["results"]] == [mentor.slug]
        assert client.delete(f"{self.URL}{mentor.slug}/").status_code == 204
        assert client.delete(f"{self.URL}{mentor.slug}/").status_code == 204
        assert client.get(self.URL).json()["count"] == 0

    def test_unlisted_mentors_cannot_be_saved(self, student):
        draft = make_mentor(approved=False)
        assert client_for(student).put(f"{self.URL}{draft.slug}/").status_code == 404

    def test_only_students(self, api, mentor):
        assert api.get(self.URL).status_code == 401
        assert client_for(mentor.user).put(f"{self.URL}{mentor.slug}/").status_code == 403

    def test_saved_list_hides_mentors_who_become_unlisted(self, student, mentor):
        client = client_for(student)
        client.put(f"{self.URL}{mentor.slug}/")
        mentor.user.is_active = False
        mentor.user.save()
        assert client.get(self.URL).json()["count"] == 0


class TestGoals:
    URL = "/api/v1/me/student/goals/"

    def test_goal_crud_is_private(self, student, other_student):
        client = client_for(student)
        created = client.post(
            self.URL, {"title": "Land an internship", "status": "in_progress"}, format="json"
        )
        assert created.status_code == 201
        goal_id = created.json()["id"]
        achieved = client.patch(f"{self.URL}{goal_id}/", {"status": "achieved"}, format="json").json()
        assert achieved["achieved_at"] is not None
        other = client_for(other_student)
        assert other.get(f"{self.URL}{goal_id}/").status_code == 404
        assert other.delete(f"{self.URL}{goal_id}/").status_code == 404
        assert client.delete(f"{self.URL}{goal_id}/").status_code == 204

    def test_goal_validation(self, student):
        assert client_for(student).post(self.URL, {"title": "   "}, format="json").status_code == 400
        assert (
            client_for(student).post(self.URL, {"title": "x", "status": "done"}, format="json").status_code
            == 400
        )

    def test_student_profile(self, student):
        response = client_for(student).patch(
            "/api/v1/me/student/profile/",
            {"education": "BSc Economics", "bio": "Aspiring analyst"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["education"] == "BSc Economics"
