"""Session formats (online / in person) and session packages."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus, RefundOutcome
from apps.mentors.models import MentorService
from apps.packages.models import MentorPackage, PackagePurchase, PurchaseStatus
from apps.payments.models import Payment, PaymentStatus

from .conftest import client_for, error_code, make_mentor, make_user, open_slots, service_of
from .test_bookings import BOOKINGS, book, shift_to

pytestmark = pytest.mark.django_db

MY_SERVICES = "/api/v1/me/mentor/services/"
MY_PACKAGES = "/api/v1/me/mentor/packages/"
MY_PURCHASES = "/api/v1/me/student/packages/"


def offer_in_person(service, *, extra_cents=0, online=True, area="Central London"):
    MentorService.objects.filter(pk=service.pk).update(
        in_person=True, online=online, in_person_extra_cents=extra_cents, in_person_area=area
    )
    service.refresh_from_db()
    return service


def make_package(mentor, *, sessions=3, discount=0, validity_days=30, service=None):
    service = service or service_of(mentor)
    return MentorPackage.objects.create(
        mentor=mentor,
        service=service,
        session_count=sessions,
        discount_percent=discount,
        validity_days=validity_days,
    )


def buy(student, package, fmt=None):
    body = {"format": fmt} if fmt else {}
    return client_for(student).post(f"/api/v1/packages/{package.pk}/purchase/", body, format="json")


def purchase(student, package, fmt=None):
    response = buy(student, package, fmt)
    assert response.status_code == 201, response.json()
    return PackagePurchase.objects.get(pk=response.json()["purchase"]["id"])


def paid_bundle(student, package, fmt=None):
    """Buy a paid bundle and confirm its payment the way the provider does (signed webhook)."""
    from .test_payments import authorize

    bought = purchase(student, package, fmt)
    assert authorize(Payment.objects.get(package_purchase=bought)) == "captured_package_active"
    bought.refresh_from_db()
    return bought


def book_with(student, mentor, purchase_, start):
    return book(client_for(student), mentor, start, package_purchase_id=str(purchase_.pk))


def remaining(student, purchase_):
    rows = client_for(student).get(MY_PURCHASES).json()
    return next(r for r in rows if r["id"] == str(purchase_.pk))["sessions_remaining"]


# --- session formats --------------------------------------------------------------------------


class TestServiceFormats:
    def payload(self, **extra):
        return {
            "title": "Mock interview",
            "description": "A realistic practice interview.",
            "duration_minutes": 60,
            "price_cents": 4000,
            **extra,
        }

    def test_in_person_needs_an_area(self):
        client = client_for(make_mentor().user)
        response = client.post(MY_SERVICES, self.payload(in_person=True), format="json")
        assert response.status_code == 400
        assert "in_person_area" in response.json()["error"]["details"]["fields"]

    def test_needs_at_least_one_format(self):
        client = client_for(make_mentor().user)
        response = client.post(MY_SERVICES, self.payload(online=False), format="json")
        assert response.status_code == 400

    def test_create_in_person_with_extra(self):
        client = client_for(make_mentor().user)
        response = client.post(
            MY_SERVICES,
            self.payload(in_person=True, in_person_extra_cents=1500, in_person_area="  Gulshan, Dhaka "),
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["online"] and body["in_person"]
        assert body["in_person_extra"]["amount_cents"] == 1500
        assert body["in_person_area"] == "Gulshan, Dhaka"

    def test_search_flags_and_filters_in_person(self):
        in_person = make_mentor(first_name="Ina")
        offer_in_person(service_of(in_person))
        make_mentor(first_name="Ola")
        rows = client_for(make_user()).get("/api/v1/mentors/", {"in_person": "true"}).json()["results"]
        assert [r["display_name"].split()[0] for r in rows] == ["Ina"]
        assert rows[0]["offers_in_person"] is True

    def test_starting_price_of_in_person_only_service_includes_extra(self):
        mentor = make_mentor(price_cents=3000)
        offer_in_person(service_of(mentor), extra_cents=1000, online=False)
        row = client_for(make_user()).get("/api/v1/mentors/").json()["results"][0]
        assert row["starting_price"]["amount_cents"] == 4000


class TestInPersonBooking:
    def test_free_in_person_booking_and_meeting_place_privacy(self, student, after_commit):
        mentor = make_mentor(price_cents=0)
        offer_in_person(service_of(mentor))
        response = book(client_for(student), mentor, open_slots(mentor)[0], format="in_person")
        assert response.status_code == 201
        body = response.json()
        assert body["format"] == "in_person" and body["in_person_area"] == "Central London"
        assert body["status"] == BookingStatus.REQUESTED
        booking_id = body["id"]

        place = "Café Nero, 12 King St (by the window)"
        with after_commit():
            accepted = client_for(mentor.user).post(
                f"{BOOKINGS}{booking_id}/accept/", {"meeting_place": place}, format="json"
            )
        assert accepted.status_code == 200 and accepted.json()["meeting_place"] == place
        assert client_for(student).get(f"{BOOKINGS}{booking_id}/").json()["meeting_place"] == place
        # Emails mention the format and area, never the exact place.
        assert mail.outbox
        assert all(place not in m.body for m in mail.outbox)
        assert any("In person (Central London)" in m.body for m in mail.outbox)

    def test_student_only_sees_place_once_confirmed(self, student):
        mentor = make_mentor(price_cents=0)
        offer_in_person(service_of(mentor))
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0], format="in_person").json()["id"]
        response = client_for(mentor.user).post(
            f"{BOOKINGS}{booking_id}/meeting-place/", {"meeting_place": "Library entrance"}, format="json"
        )
        assert response.json()["meeting_place"] == "Library entrance"  # the mentor sees it
        assert client_for(student).get(f"{BOOKINGS}{booking_id}/").json()["meeting_place"] is None

    def test_meeting_place_rules(self, student):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        url = f"{BOOKINGS}{booking_id}/meeting-place/"
        assert client_for(student).post(url, {"meeting_place": "Here"}, format="json").status_code == 403
        response = client_for(mentor.user).post(url, {"meeting_place": "Here"}, format="json")
        assert response.status_code == 409  # online session

    def test_format_not_offered(self, student):
        mentor = make_mentor(price_cents=0)
        response = book(client_for(student), mentor, open_slots(mentor)[0], format="in_person")
        assert response.status_code == 409 and error_code(response) == "format_unavailable"

    def test_in_person_extra_makes_a_free_session_paid(self, student):
        mentor = make_mentor(price_cents=0)
        offer_in_person(service_of(mentor), extra_cents=2000)
        response = book(client_for(student), mentor, open_slots(mentor)[0], format="in_person")
        assert response.status_code == 503 and error_code(response) == "payments_unavailable"
        assert book(client_for(student), mentor, open_slots(mentor)[0]).status_code == 201  # online: free

    def test_in_person_price_includes_extra(self, student, payments_enabled):
        mentor = make_mentor(price_cents=3000)
        offer_in_person(service_of(mentor), extra_cents=2000)
        response = book(client_for(student), mentor, open_slots(mentor)[0], format="in_person")
        assert response.status_code == 201
        assert response.json()["price"]["amount_cents"] == 5000
        assert response.json()["status"] == BookingStatus.PENDING_PAYMENT


# --- packages: mentor side --------------------------------------------------------------------


class TestMentorBundles:
    def payload(self, service, **extra):
        return {
            "service_id": str(service.pk),
            "session_count": 4,
            "discount_percent": 10,
            "validity_days": 45,
            **extra,
        }

    def test_create_and_price_each_format(self):
        mentor = make_mentor(price_cents=5000)
        offer_in_person(service_of(mentor), extra_cents=1000)
        response = client_for(mentor.user).post(MY_PACKAGES, self.payload(service_of(mentor)), format="json")
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["title"] == f"4 × {service_of(mentor).title}"
        assert body["regular_prices"]["online"]["amount_cents"] == 20000
        assert body["prices"]["online"]["amount_cents"] == 18000  # 10% off
        assert body["prices"]["in_person"]["amount_cents"] == 21600  # 4 × $60, 10% off
        profile = client_for(make_user()).get(f"/api/v1/mentors/{mentor.slug}/").json()
        assert [p["session_count"] for p in profile["packages"]] == [4]

    def test_formats_follow_the_service(self):
        mentor = make_mentor(price_cents=5000)
        body = (
            client_for(mentor.user).post(MY_PACKAGES, self.payload(service_of(mentor)), format="json").json()
        )
        assert body["prices"]["in_person"] is None

    def test_one_option_per_size_and_discount_limit(self):
        mentor = make_mentor()
        client = client_for(mentor.user)
        assert client.post(MY_PACKAGES, self.payload(service_of(mentor)), format="json").status_code == 201
        again = client.post(MY_PACKAGES, self.payload(service_of(mentor)), format="json")
        assert again.status_code == 400 and "session_count" in again.json()["error"]["details"]["fields"]
        too_much = client.post(
            MY_PACKAGES, self.payload(service_of(mentor), session_count=6, discount_percent=60), format="json"
        )
        assert too_much.status_code == 400

    def test_hidden_options_are_not_public(self):
        mentor = make_mentor()
        make_package(mentor)
        MentorPackage.objects.update(is_active=False)
        assert client_for(make_user()).get(f"/api/v1/mentors/{mentor.slug}/").json()["packages"] == []

    def test_only_own_services(self):
        mentor, other = make_mentor(), make_mentor(first_name="Other")
        response = client_for(mentor.user).post(MY_PACKAGES, self.payload(service_of(other)), format="json")
        assert response.status_code == 400

    def test_students_cannot_manage_options(self, student):
        assert client_for(student).get(MY_PACKAGES).status_code == 403

    def test_options_protect_their_service(self, student):
        mentor = make_mentor(price_cents=0)
        service = service_of(mentor)
        package = make_package(mentor)
        client = client_for(mentor.user)
        assert client.delete(f"{MY_SERVICES}{service.pk}/").status_code == 409
        response = client.patch(f"{MY_SERVICES}{service.pk}/", {"duration_minutes": 30}, format="json")
        assert response.status_code == 400
        purchase(student, package)
        assert client.delete(f"{MY_PACKAGES}{package.pk}/").status_code == 409


class TestPurchase:
    def test_paid_bundles_need_payments(self, student):
        package = make_package(make_mentor(price_cents=5000))
        response = buy(student, package)
        assert response.status_code == 503 and error_code(response) == "payments_unavailable"
        assert not PackagePurchase.objects.exists()

    def test_zero_price_bundle_is_active_at_once(self, student):
        package = make_package(make_mentor(price_cents=0), sessions=2, validity_days=14)
        bought = purchase(student, package)
        assert bought.status == PurchaseStatus.ACTIVE and bought.session_count == 2
        assert abs(bought.expires_at - (timezone.now() + timedelta(days=14))) < timedelta(minutes=1)
        again = buy(student, package)
        assert again.status_code == 409 and error_code(again) == "package_already_held"
        assert remaining(student, bought) == 2

    def test_format_must_be_offered(self, student):
        package = make_package(make_mentor(price_cents=0))
        response = buy(student, package, "in_person")
        assert response.status_code == 409 and error_code(response) == "format_unavailable"

    def test_mentors_cannot_buy_and_hidden_options_404(self, student):
        mentor = make_mentor()
        package = make_package(mentor)
        assert client_for(mentor.user).post(f"/api/v1/packages/{package.pk}/purchase/").status_code == 403
        MentorPackage.objects.update(is_active=False)
        assert buy(student, package).status_code == 404


class TestBundlePayments:
    """A paid bundle is usable only after the provider confirms payment (signed webhooks)."""

    def start(self, student, *, discount=10, fmt=None):
        mentor = make_mentor(price_cents=5000)
        if fmt == "in_person":
            offer_in_person(service_of(mentor), extra_cents=1000)
        package = make_package(mentor, sessions=4, discount=discount)
        response = buy(student, package, fmt)
        assert response.status_code == 201, response.json()
        body = response.json()
        bought = PackagePurchase.objects.get(pk=body["purchase"]["id"])
        return mentor, bought, body["checkout_url"], Payment.objects.get(package_purchase=bought)

    def test_pending_until_paid_then_active(self, student, payments_enabled, fake_stripe):
        from .test_payments import authorize

        mentor, bought, url, payment = self.start(student)
        assert url.startswith("https://") and bought.status == PurchaseStatus.PENDING_PAYMENT
        assert payment.amount_cents == 18000 and bought.expires_at is None
        # Not usable yet.
        response = book_with(student, mentor, bought, open_slots(mentor)[0])
        assert response.status_code == 409 and error_code(response) == "package_not_active"
        # The provider confirms: charged at once and active.
        assert authorize(payment) == "captured_package_active"
        bought.refresh_from_db()
        payment.refresh_from_db()
        assert bought.status == PurchaseStatus.ACTIVE and bought.expires_at is not None
        assert payment.status == PaymentStatus.CAPTURED and "capture" in fake_stripe.names()
        assert book_with(student, mentor, bought, open_slots(mentor)[0]).status_code == 201

    def test_in_person_bundle_price(self, student, payments_enabled, fake_stripe):
        _, bought, _, payment = self.start(student, fmt="in_person")
        assert bought.format == "in_person" and payment.amount_cents == 21600

    def test_repeat_request_reuses_the_checkout(self, student, payments_enabled, fake_stripe):
        _, bought, url, _ = self.start(student)
        again = buy(student, bought.package).json()
        assert again["purchase"]["id"] == str(bought.pk) and again["checkout_url"] == url
        assert fake_stripe.names().count("checkout.create") == 1

    def test_expired_checkout_closes_it(self, student, payments_enabled, fake_stripe):
        from .test_payments import deliver

        _, bought, _, payment = self.start(student)
        obj = {
            "id": payment.checkout_reference,
            "object": "checkout.session",
            "metadata": {"payment_id": str(payment.pk)},
        }
        assert deliver("checkout.session.expired", obj) == "checkout_expired"
        bought.refresh_from_db()
        assert bought.status == PurchaseStatus.CANCELLED
        assert client_for(student).get(MY_PURCHASES).json() == []

    def test_late_payment_on_closed_purchase_is_released(self, student, payments_enabled, fake_stripe):
        from .test_payments import authorize

        _, bought, _, payment = self.start(student)
        PackagePurchase.objects.filter(pk=bought.pk).update(status=PurchaseStatus.CANCELLED)
        assert authorize(payment) == "released_late_payment"
        assert "capture" not in fake_stripe.names()

    def test_full_refund_ends_the_bundle_and_counts_in_earnings(
        self, student, admin_user, payments_enabled, fake_stripe, after_commit
    ):
        from .test_payments import authorize, refund_event

        mentor, bought, _, payment = self.start(student)
        authorize(payment)
        ledger = client_for(mentor.user).get("/api/v1/me/mentor/earnings/ledger/").json()
        assert any(e["kind"] == "earning" and bought.title in e["description"] for e in ledger["results"])
        with after_commit():
            response = client_for(admin_user).post(
                f"/api/v1/admin/payments/{payment.pk}/refund/", {"note": "Goodwill"}, format="json"
            )
        assert response.status_code in (200, 201), response.json()
        bought.refresh_from_db()
        assert bought.status == PurchaseStatus.ACTIVE  # not until the provider confirms the refund
        assert refund_event(payment.refunds.get(), "succeeded") == "refund_succeeded"
        bought.refresh_from_db()
        assert bought.status == PurchaseStatus.REFUNDED
        listed = client_for(admin_user).get("/api/v1/admin/payments/").json()["results"][0]
        assert listed["package_purchase_id"] == str(bought.pk) and listed["booking_id"] is None


class TestMinimumPrice:
    def test_services_and_seminars_need_a_price(self, settings):
        settings.MIN_SESSION_PRICE_CENTS = 100
        mentor = make_mentor()
        client = client_for(mentor.user)
        service = {"title": "Chat", "description": "A short career chat.", "duration_minutes": 30}
        response = client.post(MY_SERVICES, {**service, "price_cents": 0}, format="json")
        assert response.status_code == 400 and "price_cents" in response.json()["error"]["details"]["fields"]
        assert client.post(MY_SERVICES, {**service, "price_cents": 100}, format="json").status_code == 201
        seminar = {
            "service_id": str(service_of(mentor).pk),
            "start_at": (timezone.now() + timedelta(days=3)).isoformat(),
            "duration_minutes": 60,
            "capacity": 5,
        }
        seminars = "/api/v1/me/mentor/seminars/"
        assert client.post(seminars, {**seminar, "price_cents": 0}, format="json").status_code == 400
        assert client.post(seminars, {**seminar, "price_cents": 500}, format="json").status_code == 201
        config = client.get("/api/v1/config/").json()
        assert config["min_session_price"] == {"amount_cents": 100, "currency": "USD"}


class TestMeetingLink:
    def test_link_for_this_session(self, student):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        link = "https://zoom.example.com/j/123"
        response = client_for(mentor.user).post(
            f"{BOOKINGS}{booking_id}/accept/", {"meeting_url": link}, format="json"
        )
        assert response.json()["meeting_url"] == link
        assert client_for(student).get(f"{BOOKINGS}{booking_id}/").json()["meeting_url"] == link
        changed = "https://meet.example.com/abc-defg"
        response = client_for(mentor.user).post(
            f"{BOOKINGS}{booking_id}/meeting-link/", {"meeting_url": changed}, format="json"
        )
        assert response.json()["meeting_url"] == changed

    def test_default_link_when_none_given(self, student):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        response = client_for(mentor.user).post(f"{BOOKINGS}{booking_id}/accept/")
        assert response.json()["meeting_url"] == mentor.meeting_url

    def test_rules(self, student):
        mentor = make_mentor(price_cents=0)
        booking_id = book(client_for(student), mentor, open_slots(mentor)[0]).json()["id"]
        url = f"{BOOKINGS}{booking_id}/meeting-link/"
        assert (
            client_for(student).post(url, {"meeting_url": "https://x.example.com"}, format="json").status_code
            == 403
        )
        insecure = client_for(mentor.user).post(url, {"meeting_url": "http://x.example.com"}, format="json")
        assert insecure.status_code == 400
        offer_in_person(service_of(mentor))
        in_person = book(client_for(student), mentor, open_slots(mentor)[5], format="in_person").json()["id"]
        response = client_for(mentor.user).post(
            f"{BOOKINGS}{in_person}/meeting-link/", {"meeting_url": "https://x.example.com"}, format="json"
        )
        assert response.status_code == 409


class TestBookingWithPackage:
    def test_books_free_of_charge_and_uses_a_credit(self, student, payments_enabled, fake_stripe):
        mentor = make_mentor(price_cents=5000)
        bought = paid_bundle(student, make_package(mentor, sessions=2))
        response = book_with(student, mentor, bought, open_slots(mentor)[0])
        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["price"]["amount_cents"] == 0 and body["status"] == BookingStatus.REQUESTED
        assert body["package"] == {"id": str(bought.pk), "title": bought.title}
        assert remaining(student, bought) == 1

    def test_package_format_wins(self, student, payments_enabled, fake_stripe):
        mentor = make_mentor(price_cents=0)
        offer_in_person(service_of(mentor), extra_cents=2000)
        bought = paid_bundle(student, make_package(mentor), "in_person")
        body = book_with(student, mentor, bought, open_slots(mentor)[0]).json()
        assert body["format"] == "in_person" and body["price"]["amount_cents"] == 0

    def test_used_up(self, student):
        mentor = make_mentor(price_cents=0, buffer=0)
        bought = purchase(student, make_package(mentor, sessions=2))
        slots = open_slots(mentor)
        assert book_with(student, mentor, bought, slots[0]).status_code == 201
        assert book_with(student, mentor, bought, slots[3]).status_code == 201
        response = book_with(student, mentor, bought, slots[6])
        assert response.status_code == 409 and error_code(response) == "package_used_up"

    def test_expiry(self, student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor))
        PackagePurchase.objects.filter(pk=bought.pk).update(
            expires_at=timezone.now() + timedelta(days=1, hours=6)
        )
        late_slot = next(s for s in open_slots(mentor) if s > timezone.now() + timedelta(days=2))
        response = book_with(student, mentor, bought, late_slot)
        assert response.status_code == 409 and error_code(response) == "package_expires_first"
        PackagePurchase.objects.filter(pk=bought.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        response = book_with(student, mentor, bought, open_slots(mentor)[0])
        assert response.status_code == 409 and error_code(response) == "package_expired"

    def test_someone_elses_package_or_other_service(self, student, other_student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor))
        assert book_with(other_student, mentor, bought, open_slots(mentor)[0]).status_code == 404
        other_service = MentorService.objects.create(
            mentor=mentor,
            title="Other",
            description="Another service.",
            duration_minutes=30,
            price_cents=0,
            currency="USD",
        )
        response = book(
            client_for(student),
            mentor,
            open_slots(mentor)[0],
            service=other_service,
            package_purchase_id=str(bought.pk),
        )
        assert response.status_code == 409 and error_code(response) == "package_mismatch"

    def test_still_usable_when_service_is_hidden(self, student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor))
        MentorService.objects.update(is_active=False)
        assert book_with(student, mentor, bought, open_slots(mentor)[0]).status_code == 201


class TestCredits:
    def confirmed(self, student, mentor, bought, start):
        booking_id = book_with(student, mentor, bought, start).json()["id"]
        assert client_for(mentor.user).post(f"{BOOKINGS}{booking_id}/accept/").status_code == 200
        return Booking.objects.get(pk=booking_id)

    def test_decline_returns_the_credit(self, student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor, sessions=2))
        booking_id = book_with(student, mentor, bought, open_slots(mentor)[0]).json()["id"]
        client_for(mentor.user).post(f"{BOOKINGS}{booking_id}/decline/", {"reason": "Away"}, format="json")
        assert remaining(student, bought) == 2

    def test_early_cancellation_returns_the_credit(self, student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor, sessions=2))
        booking = self.confirmed(student, mentor, bought, open_slots(mentor, days=10)[-1])
        response = client_for(student).post(f"{BOOKINGS}{booking.pk}/cancel/")
        assert response.json()["refund_outcome"] == RefundOutcome.FULL_REFUND
        assert remaining(student, bought) == 2

    def test_late_cancellation_uses_the_credit(self, student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor, sessions=2))
        booking = self.confirmed(student, mentor, bought, open_slots(mentor)[0])
        shift_to(booking, timezone.now() + timedelta(hours=2))
        response = client_for(student).post(f"{BOOKINGS}{booking.pk}/cancel/")
        assert response.json()["refund_outcome"] == RefundOutcome.NO_REFUND
        assert remaining(student, bought) == 1

    def test_mentor_cancellation_returns_the_credit(self, student):
        mentor = make_mentor(price_cents=0)
        bought = purchase(student, make_package(mentor, sessions=2))
        booking = self.confirmed(student, mentor, bought, open_slots(mentor)[0])
        shift_to(booking, timezone.now() + timedelta(hours=2))
        client_for(mentor.user).post(f"{BOOKINGS}{booking.pk}/cancel/", {"reason": "Ill"}, format="json")
        assert remaining(student, bought) == 2
