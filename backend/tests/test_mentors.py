import uuid
from datetime import datetime, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.mentors.models import AvailabilityRule, VerificationRequest, VerificationStatus
from apps.taxonomy.models import Category, Language, Profession, Skill
from apps.users.models import Role

from .conftest import client_for, error_code, make_mentor, make_user, open_slots, service_of

pytestmark = pytest.mark.django_db

PROFILE = "/api/v1/me/mentor/profile/"


def ids(model, **filters):
    return list(model.objects.filter(**filters).values_list("pk", flat=True))


class TestMentorProfile:
    def test_new_mentor_can_complete_profile(self):
        user = make_user(Role.MENTOR, first_name="Ana", last_name="Lima")
        from apps.mentors.services import create_mentor_profile

        create_mentor_profile(user)
        payload = {
            "headline": "Product designer helping juniors",
            "bio": "I design products for a living and love helping people break into design." * 2,
            "current_title": "Lead Designer",
            "profession_id": Profession.objects.get(slug="product-designer").pk,
            "industry_ids": ids(Category, slug__in=["design", "technology"]),
            "skill_ids": ids(Skill, slug__in=["ux-design", "portfolio-review"]),
            "language_codes": ["en", "pt"],
            "country": "BR",
            "city": "São Paulo",
            "timezone": "America/Sao_Paulo",
            "years_experience": 9,
            "linkedin_url": "https://www.linkedin.com/in/someone",
            "meeting_url": "https://meet.example.com/ana",
        }
        response = client_for(user).patch(PROFILE, payload, format="json")
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["country"] == "BR"
        assert sorted(body["language_codes"]) == ["en", "pt"]
        assert len(body["industry_ids"]) == 2
        assert body["verification_status"] == "draft"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("linkedin_url", "https://evil.example.com/in/x"),
            ("linkedin_url", "http://www.linkedin.com/in/x"),
            ("meeting_url", "http://meet.example.com"),
            ("timezone", "Nowhere/City"),
            ("years_experience", 99),
            ("buffer_minutes", 500),
        ],
    )
    def test_invalid_values_rejected(self, mentor, field, value):
        response = client_for(mentor.user).patch(PROFILE, {field: value}, format="json")
        assert response.status_code == 400
        assert field in response.json()["error"]["details"]["fields"]

    def test_at_most_three_industries(self, mentor):
        response = client_for(mentor.user).patch(PROFILE, {"industry_ids": ids(Category)[:4]}, format="json")
        assert response.status_code == 400

    def test_mentor_cannot_verify_themselves(self):
        mentor = make_mentor(approved=False)
        client = client_for(mentor.user)
        client.patch(PROFILE, {"verification_status": "approved", "rating_avg": "5.00"}, format="json")
        mentor.refresh_from_db()
        assert mentor.verification_status == VerificationStatus.DRAFT
        assert mentor.rating_avg is None
        # …and can't reach the admin approval endpoint.
        request = VerificationRequest.objects.create(mentor=mentor, submitted_at=mentor.created_at)
        response = client.post(f"/api/v1/admin/verification-requests/{request.pk}/approve/")
        assert response.status_code == 403

    def test_changing_timezone_moves_weekly_hours_with_it(self, mentor):
        client_for(mentor.user).patch(PROFILE, {"timezone": "Asia/Tokyo"}, format="json")
        assert set(AvailabilityRule.objects.filter(mentor=mentor).values_list("timezone", flat=True)) == {
            "Asia/Tokyo"
        }


class TestVerificationWorkflow:
    def test_meeting_link_is_required_for_verification(self):
        mentor = make_mentor(approved=False)
        mentor.meeting_url = ""
        mentor.save()
        response = client_for(mentor.user).post("/api/v1/me/mentor/verification/", {}, format="json")
        assert response.status_code == 400
        assert "meeting link" in response.json()["error"]["message"]

    def test_incomplete_profile_cannot_be_submitted(self):
        user = make_user(Role.MENTOR)
        from apps.mentors.services import create_mentor_profile

        create_mentor_profile(user)
        response = client_for(user).post("/api/v1/me/mentor/verification/", {}, format="json")
        assert response.status_code == 400
        assert "Complete your profile" in response.json()["error"]["message"]

    def test_submit_approve_flow(self, admin_user, django_capture_on_commit_callbacks):
        mentor = make_mentor(approved=False)
        client = client_for(mentor.user)
        response = client.post(
            "/api/v1/me/mentor/verification/", {"evidence_note": "See LinkedIn."}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["verification_status"] == "pending"
        assert (
            error_code(client.post("/api/v1/me/mentor/verification/", {}, format="json")) == "already_exists"
        )

        # Not public until approved.
        assert client_for(admin_user).get(f"/api/v1/mentors/{mentor.slug}/").status_code == 404

        request = VerificationRequest.objects.get(mentor=mentor)
        admin = client_for(admin_user)
        queue = admin.get("/api/v1/admin/verification-requests/").json()
        assert [r["id"] for r in queue["results"]] == [str(request.pk)]
        with django_capture_on_commit_callbacks(execute=True):
            approved = admin.post(f"/api/v1/admin/verification-requests/{request.pk}/approve/")
        assert approved.status_code == 200
        assert len(mail.outbox) == 1

        public = admin.get(f"/api/v1/mentors/{mentor.slug}/").json()
        assert public["is_verified"] is True
        again = admin.post(f"/api/v1/admin/verification-requests/{request.pk}/approve/")
        assert error_code(again) == "invalid_state"

    def test_reject_requires_reason_and_is_visible_to_mentor(self, admin_user):
        mentor = make_mentor(approved=False)
        client_for(mentor.user).post("/api/v1/me/mentor/verification/", {}, format="json")
        request = VerificationRequest.objects.get(mentor=mentor)
        admin = client_for(admin_user)
        assert (
            admin.post(
                f"/api/v1/admin/verification-requests/{request.pk}/reject/", {}, format="json"
            ).status_code
            == 400
        )
        admin.post(
            f"/api/v1/admin/verification-requests/{request.pk}/reject/",
            {"reason": "Please add your current role."},
            format="json",
        )
        own = client_for(mentor.user).get(PROFILE).json()
        assert own["verification_status"] == "rejected"
        assert own["verification_decision_reason"] == "Please add your current role."


class TestDiscovery:
    @pytest.fixture
    def catalogue(self, db):
        alice = make_mentor(
            first_name="Alice",
            price_cents=3000,
            country="GB",
            categories=("technology",),
            skills=("python", "sql"),
            languages=("en",),
            headline="Data engineer and SQL nerd",
        )
        bruno = make_mentor(
            first_name="Bruno",
            price_cents=9000,
            country="BR",
            categories=("finance",),
            skills=("valuation",),
            languages=("pt", "en"),
            headline="Investment banker",
        )
        carla = make_mentor(
            first_name="Carla",
            price_cents=0,
            country="DE",
            categories=("design",),
            skills=("ux-design",),
            languages=("de",),
            weekly_hours=False,
            headline="Designer",
        )
        draft = make_mentor(first_name="Dora", approved=False)
        suspended = make_mentor(first_name="Eve")
        suspended.user.is_active = False
        suspended.user.save()
        return {"alice": alice, "bruno": bruno, "carla": carla, "draft": draft, "suspended": suspended}

    def names(self, api, query=""):
        response = api.get(f"/api/v1/mentors/{query}")
        assert response.status_code == 200, response.json()
        return [m["display_name"].split()[0] for m in response.json()["results"]]

    def test_only_approved_active_mentors_are_listed(self, api, catalogue):
        assert sorted(self.names(api)) == ["Alice", "Bruno", "Carla"]

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("?industry=finance", ["Bruno"]),
            ("?skill=sql", ["Alice"]),
            ("?country=de", ["Carla"]),
            ("?language=pt", ["Bruno"]),
            ("?price_min=1000&price_max=5000", ["Alice"]),
            ("?q=banker", ["Bruno"]),
            ("?q=data sql", ["Alice"]),
            ("?industry=finance&industry=design", ["Bruno", "Carla"]),
        ],
    )
    def test_filters(self, api, catalogue, query, expected):
        assert sorted(self.names(api, query)) == expected

    def test_ordering_by_price(self, api, catalogue):
        assert self.names(api, "?ordering=min_price_cents") == ["Carla", "Alice", "Bruno"]
        assert self.names(api, "?ordering=-min_price_cents") == ["Bruno", "Alice", "Carla"]

    def test_availability_filter_and_next_available(self, api, catalogue):
        assert sorted(self.names(api, "?available_within_days=7")) == ["Alice", "Bruno"]
        results = api.get("/api/v1/mentors/?q=Carla").json()["results"]
        assert results[0]["next_available_at"] is None

    def test_invalid_query_is_a_validation_error(self, api, catalogue):
        response = api.get("/api/v1/mentors/?ordering=password")
        assert response.status_code == 400

    def test_summary_shape(self, api, catalogue):
        alice = next(
            m for m in api.get("/api/v1/mentors/").json()["results"] if m["slug"] == catalogue["alice"].slug
        )
        assert alice["starting_price"] == {"amount_cents": 3000, "currency": "USD"}
        assert alice["is_verified"] is True
        assert alice["rating_avg"] is None and alice["rating_count"] == 0
        assert alice["industries"][0]["slug"] == "technology"
        assert alice["next_available_at"].endswith("Z")

    def test_detail_by_slug_or_uuid(self, api, catalogue):
        alice = catalogue["alice"]
        by_slug = api.get(f"/api/v1/mentors/{alice.slug}/")
        assert by_slug.status_code == 200
        assert by_slug.json()["services"][0]["price"]["amount_cents"] == 3000
        assert api.get(f"/api/v1/mentors/{alice.pk}/").status_code == 200
        assert api.get(f"/api/v1/mentors/{catalogue['draft'].slug}/").status_code == 404
        assert api.get(f"/api/v1/mentors/{uuid.uuid4()}/").status_code == 404

    def test_categories_without_counts(self, api, db):
        categories = api.get("/api/v1/categories/").json()
        assert categories[0].keys() == {"id", "name", "slug", "description", "is_active"}

    def test_categories_with_counts(self, api, catalogue):
        categories = {c["slug"]: c for c in api.get("/api/v1/categories/?with_counts=true").json()}
        assert categories["technology"]["mentor_count"] == 1  # draft and suspended mentors don't count
        assert api.get("/api/v1/categories/finance/").json()["mentor_count"] == 1
        assert api.get("/api/v1/categories/nope/").status_code == 404

    def test_taxonomy_endpoints(self, api, db):
        assert any(c["code"] == "GB" for c in api.get("/api/v1/taxonomy/countries/").json())
        assert any(language["code"] == "en" for language in api.get("/api/v1/taxonomy/languages/").json())
        assert api.get("/api/v1/taxonomy/skills/?q=pyth").json()[0]["slug"] == "python"
        assert Language.objects.count() > 10


class TestServicesAndAvailability:
    def test_service_crud(self, mentor):
        client = client_for(mentor.user)
        created = client.post(
            "/api/v1/me/mentor/services/",
            {
                "title": "Mock interview",
                "description": "A realistic mock interview.",
                "duration_minutes": 45,
                "price_cents": 7500,
            },
            format="json",
        )
        assert created.status_code == 201
        assert created.json()["price"] == {"amount_cents": 7500, "currency": "USD"}
        service_id = created.json()["id"]
        updated = client.patch(
            f"/api/v1/me/mentor/services/{service_id}/", {"is_active": False}, format="json"
        )
        assert updated.json()["is_active"] is False
        listed = client.get("/api/v1/me/mentor/services/").json()["results"]
        assert {s["id"] for s in listed} >= {service_id}
        public = client.get(f"/api/v1/mentors/{mentor.slug}/").json()
        assert service_id not in {s["id"] for s in public["services"]}
        assert client.delete(f"/api/v1/me/mentor/services/{service_id}/").status_code == 204

    @pytest.mark.parametrize(
        "payload",
        [
            {"duration_minutes": 50},
            {"price_cents": -100},
            {"price_cents": 999_999_999},
            {"currency": "EUR"},
            {"title": ""},
        ],
    )
    def test_service_validation(self, mentor, payload):
        base = {
            "title": "Chat",
            "description": "A useful conversation.",
            "duration_minutes": 30,
            "price_cents": 1000,
        }
        response = client_for(mentor.user).post(
            "/api/v1/me/mentor/services/", {**base, **payload}, format="json"
        )
        assert response.status_code == 400

    def test_cannot_touch_another_mentors_service(self, mentor):
        other = make_mentor(first_name="Other")
        client = client_for(mentor.user)
        url = f"/api/v1/me/mentor/services/{service_of(other).pk}/"
        assert client.patch(url, {"price_cents": 1}, format="json").status_code == 404
        assert client.delete(url).status_code == 404
        assert service_of(other).price_cents == 5000

    def test_weekly_rules_replace_and_validate(self, mentor):
        client = client_for(mentor.user)
        url = "/api/v1/me/mentor/availability/rules/"
        overlapping = [
            {"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
            {"weekday": 0, "start_time": "11:00", "end_time": "13:00"},
        ]
        assert client.put(url, overlapping, format="json").status_code == 400
        assert (
            client.put(
                url, [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}], format="json"
            ).status_code
            == 400
        )
        valid = [{"weekday": 1, "start_time": "09:00", "end_time": "12:00"}]
        assert client.put(url, valid, format="json").json() == valid
        assert client.get(url).json() == valid

    def test_public_availability_endpoint(self, api, mentor):
        now = timezone.now()
        today = now.date()
        query = f"service={service_of(mentor).pk}&from={today}&to={today + timedelta(days=3)}"
        response = api.get(f"/api/v1/mentors/{mentor.slug}/availability/?{query}")
        assert response.status_code == 200
        body = response.json()
        assert body["duration_minutes"] == 60
        assert body["slots"], "expected open slots"
        first = datetime.fromisoformat(body["slots"][0])
        assert body["slots"][0].endswith("Z")
        assert first >= now + timedelta(hours=24)  # minimum notice

    def test_availability_range_is_limited(self, api, mentor):
        response = api.get(
            f"/api/v1/mentors/{mentor.slug}/availability/?service={service_of(mentor).pk}&from=2026-01-01&to=2026-06-01"
        )
        assert response.status_code == 400

    def test_unavailable_exception_removes_slots(self, mentor):
        slots = open_slots(mentor)
        first = slots[0]
        response = client_for(mentor.user).post(
            "/api/v1/me/mentor/availability/exceptions/",
            {
                "start_at": first.isoformat(),
                "end_at": (first.replace(hour=23, minute=59)).isoformat(),
                "status": "unavailable",
            },
            format="json",
        )
        assert response.status_code == 201
        assert first not in open_slots(mentor)
