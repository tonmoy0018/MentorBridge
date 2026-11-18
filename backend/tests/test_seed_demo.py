"""The local demo seed: dev-only, additive, idempotent, and uses the real verification workflow."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.bookings.models import Booking
from apps.mentors.models import MentorProfile, MentorService, VerificationStatus
from apps.packages.models import MentorPackage
from apps.payments.models import Payment
from apps.reviews.models import Review
from apps.seminars.models import Seminar
from apps.users.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "Demo-Seed-Test-Pass-42"


def seed(**kwargs):
    out = StringIO()
    call_command("seed_demo", password=PASSWORD, stdout=out, **kwargs)
    return out.getvalue()


def test_refuses_without_debug():
    with override_settings(DEBUG=False), pytest.raises(CommandError, match="DEBUG"):
        seed()
    assert not User.objects.exists()


@override_settings(DEBUG=True)
def test_creates_labelled_demo_accounts(client):
    seed()
    users = User.objects.all()
    assert users.count() == 8
    assert all(u.email.endswith("@example.com") and "(Demo)" in u.last_name for u in users)
    assert all(u.email_verified for u in users)

    statuses = sorted(MentorProfile.objects.values_list("verification_status", flat=True))
    assert statuses == [VerificationStatus.APPROVED] * 4 + [VerificationStatus.PENDING]
    # No free sessions: everything has a price that meets the production minimum.
    assert not MentorService.objects.filter(price_cents__lt=100).exists()
    assert not Seminar.objects.filter(price_cents__lt=100).exists()
    # In-person options, multi-session bundles and upcoming group seminars.
    assert MentorService.objects.filter(in_person=True).count() == 4
    assert (
        MentorPackage.objects.count() == 4
        and MentorPackage.objects.filter(discount_percent__gt=0).count() == 4
    )
    assert Seminar.objects.count() == 3
    # No fabricated activity.
    assert not Booking.objects.exists() and not Payment.objects.exists() and not Review.objects.exists()

    assert client.login(email="demo.student@example.com", password=PASSWORD)
    listed = client.get("/api/v1/mentors/").json()
    assert listed["count"] == 4


@override_settings(DEBUG=True)
def test_idempotent_and_leaves_existing_accounts_alone():
    seed()
    student = User.objects.get(email="demo.student@example.com")
    student.first_name = "Changed"
    student.save()

    MentorPackage.objects.filter(service__title="Portfolio review").delete()
    out = seed()
    assert User.objects.count() == 8
    assert "+1 offerings" in out  # only the missing package is re-added
    assert "already existed" in out and "Password for newly created" not in out
    student.refresh_from_db()
    assert student.first_name == "Changed"
