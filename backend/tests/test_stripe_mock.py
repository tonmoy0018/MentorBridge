"""
Contract check of the Stripe adapter against stripe-mock (Stripe's official mock server, which
validates every request against Stripe's OpenAPI spec and returns canned fixture objects).

MOCKED PROVIDER: nothing here talks to Stripe and no money moves. It proves only that the request
parameters the adapter sends are valid for Stripe's API and that the responses parse. Skipped
unless STRIPE_MOCK_URL is set; `make test-stripe-mock` starts stripe-mock and runs it.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from apps.payments.providers.base import CaptureResult, CheckoutSession, RefundResult
from apps.payments.providers.stripe import StripeProvider

STRIPE_MOCK_URL = os.environ.get("STRIPE_MOCK_URL", "")

pytestmark = pytest.mark.skipif(
    not STRIPE_MOCK_URL, reason="STRIPE_MOCK_URL not set (stripe-mock not running)"
)


@pytest.fixture
def provider():
    return StripeProvider(secret_key="sk_test_123", webhook_secret="whsec_unused", api_base=STRIPE_MOCK_URL)


@pytest.fixture
def payment():
    booking = SimpleNamespace(pk=uuid.uuid4(), service_title="Career chat")
    return SimpleNamespace(
        pk=uuid.uuid4(),
        booking=booking,
        amount_cents=5000,
        currency="USD",
        provider_reference="pi_123",
        checkout_reference="cs_test_123",
    )


def test_checkout_request_is_valid(provider, payment):
    session = provider.create_checkout(
        payment=payment,
        booking=payment.booking,
        success_url="https://example.test/ok",
        cancel_url="https://example.test/cancel",
        expires_at=datetime.now(UTC) + timedelta(minutes=31),
    )
    assert isinstance(session, CheckoutSession) and session.reference


def test_expire_capture_cancel_and_refund_requests_are_valid(provider, payment):
    provider.expire_checkout(payment)
    assert isinstance(provider.capture(payment), CaptureResult)
    provider.cancel_authorization(payment)
    result = provider.refund(SimpleNamespace(pk=uuid.uuid4(), payment=payment, amount_cents=1000))
    assert isinstance(result, RefundResult) and result.reference
