"""
Shared fixtures. Tests run against PostgreSQL (the booking guarantees rely on exclusion
constraints, which SQLite doesn't support). pytest-django creates a separate test database.
"""

from datetime import time, timedelta
from types import SimpleNamespace

import pytest
import stripe
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.mentors.models import AvailabilityRule, MentorService, VerificationStatus
from apps.mentors.selectors import bookable_slots
from apps.mentors.services import create_mentor_profile
from apps.students.models import StudentProfile
from apps.taxonomy.models import Category, Language, Profession, Skill
from apps.users.models import Role, User

PASSWORD = "Correct-Horse-91"
WEBHOOK_SECRET = "whsec_mocked_for_tests"


@pytest.fixture(autouse=True)
def _isolated_cache():
    cache.clear()  # throttle counters live in the cache
    yield
    cache.clear()


@pytest.fixture
def payments_enabled(settings):
    """Behave as if a payment provider were integrated (M4), to test the paid-booking path."""
    settings.PAYMENTS_ENABLED = True


@pytest.fixture
def api() -> APIClient:
    return APIClient()


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


_counter = {"n": 0}


def make_user(role=Role.STUDENT, *, email=None, first_name="Test", last_name="User", **extra) -> User:
    _counter["n"] += 1
    email = email or f"user{_counter['n']}@example.com"
    user = User.objects.create_user(
        email=email, password=PASSWORD, first_name=first_name, last_name=last_name, role=role, **extra
    )
    if role == Role.STUDENT:
        StudentProfile.objects.create(user=user)
    return user


def make_mentor(
    *,
    approved=True,
    first_name="Mia",
    last_name="Mentor",
    price_cents=5000,
    duration=60,
    buffer=15,
    min_notice=24,
    auto_accept=False,
    country="GB",
    categories=("technology",),
    skills=("python",),
    languages=("en",),
    weekly_hours=True,
    headline="Senior engineer helping juniors grow",
):
    user = make_user(Role.MENTOR, first_name=first_name, last_name=last_name)
    mentor = create_mentor_profile(user)
    mentor.headline = headline
    mentor.bio = "I have worked in the industry for many years and enjoy mentoring early-career people."
    mentor.current_title = "Senior Engineer"
    mentor.current_company = "Example Co"
    mentor.profession = Profession.objects.get(slug="software-engineer")
    mentor.country = country
    mentor.timezone = "UTC"
    mentor.buffer_minutes = buffer
    mentor.min_notice_hours = min_notice
    mentor.auto_accept = auto_accept
    mentor.meeting_url = "https://meet.example.com/room"
    if approved:
        mentor.verification_status = VerificationStatus.APPROVED
        mentor.verified_at = timezone.now()
    mentor.save()
    mentor.categories.set(Category.objects.filter(slug__in=categories))
    mentor.skills.set(Skill.objects.filter(slug__in=skills))
    mentor.languages.set(Language.objects.filter(code__in=languages))
    MentorService.objects.create(
        mentor=mentor,
        title="Career chat",
        description="A conversation about your career goals.",
        duration_minutes=duration,
        price_cents=price_cents,
        currency="USD",
    )
    if weekly_hours:
        AvailabilityRule.objects.bulk_create(
            AvailabilityRule(
                mentor=mentor, weekday=d, start_time=time(0, 0), end_time=time(23, 59), timezone="UTC"
            )
            for d in range(7)
        )
    return mentor


def captured_payment(booking, *, amount_cents=5000, commission_bps=1500, livemode=True, **extra):
    """TEST DATA: a captured payment row as the provider integration would record it."""
    from apps.payments.commission import breakdown
    from apps.payments.models import Payment, PaymentStatus

    split = breakdown(amount_cents, commission_bps)
    return Payment.objects.create(
        booking=booking,
        provider="stripe",
        livemode=livemode,
        amount_cents=amount_cents,
        currency="USD",
        commission_bps=commission_bps,
        platform_fee_cents=split.commission_cents,
        mentor_share_cents=split.mentor_share_cents,
        status=PaymentStatus.CAPTURED,
        **extra,
    )


def service_of(mentor) -> MentorService:
    return mentor.services.first()


def open_slots(mentor, service=None, days=7):
    service = service or service_of(mentor)
    now = timezone.now()
    return bookable_slots(
        mentor,
        duration_minutes=service.duration_minutes,
        window_start=now,
        window_end=now + timedelta(days=days),
    )


def error_code(response) -> str:
    return response.json()["error"]["code"]


@pytest.fixture
def student(db):
    return make_user(Role.STUDENT, first_name="Jordan", last_name="Lee")


@pytest.fixture
def other_student(db):
    return make_user(Role.STUDENT, first_name="Sam", last_name="Other")


@pytest.fixture
def mentor(db):
    return make_mentor()


@pytest.fixture
def admin_user(db):
    _counter["n"] += 1
    return User.objects.create_superuser(
        email=f"admin{_counter['n']}@example.com", password=PASSWORD, first_name="Ada", last_name="Admin"
    )


# --- mocked payment provider ------------------------------------------------------------------------------


class Obj(dict):
    """A Stripe-shaped response object: item and attribute access."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class FakeStripe:
    """MOCKED Stripe API client. Records every call and returns canned, Stripe-shaped responses."""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.failures: dict[str, Exception] = {}
        self.refund_status = "pending"
        self.capture_fee = 175
        self._n = 0
        ns = SimpleNamespace
        self.v1 = ns(
            checkout=ns(
                sessions=ns(
                    create=self._wrap("checkout.create", self._create_session),
                    expire=self._wrap("checkout.expire", lambda ref, **_: Obj(id=ref, status="expired")),
                )
            ),
            payment_intents=ns(
                capture=self._wrap("capture", self._capture),
                cancel=self._wrap("cancel", lambda ref, **_: Obj(id=ref, status="canceled")),
            ),
            refunds=ns(create=self._wrap("refund", self._refund)),
        )

    def _wrap(self, name, fn):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name in self.failures:
                raise self.failures[name]
            return fn(*args, **kwargs)

        return call

    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]

    def last(self, name):
        return next((args, kwargs) for n, args, kwargs in reversed(self.calls) if n == name)

    def _create_session(self, *, params, options):
        self._n += 1
        ref = f"cs_test_mock{self._n}"
        return Obj(id=ref, url=f"https://checkout.stripe.test/c/pay/{ref}", expires_at=params["expires_at"])

    def _capture(self, ref, *, params, options):
        balance = Obj(fee=self.capture_fee, currency="usd")
        return Obj(id=ref, status="succeeded", latest_charge=Obj(id="ch_mock", balance_transaction=balance))

    def _refund(self, *, params, options):
        self._n += 1
        return Obj(id=f"re_test_mock{self._n}", status=self.refund_status, failure_reason=None)


@pytest.fixture
def fake_stripe(settings, monkeypatch) -> FakeStripe:
    settings.PAYMENT_PROVIDER = "stripe"
    settings.STRIPE_SECRET_KEY = "sk_test_mocked_not_a_real_key"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    settings.STRIPE_API_BASE = ""
    settings.PAYMENTS_ENABLED = True
    fake = FakeStripe()
    monkeypatch.setattr(stripe, "StripeClient", lambda *args, **kwargs: fake)
    return fake


@pytest.fixture
def after_commit(django_capture_on_commit_callbacks):
    """Run on-commit work (emails, post-cancellation refunds) as it would run after a real commit."""
    return lambda: django_capture_on_commit_callbacks(execute=True)
