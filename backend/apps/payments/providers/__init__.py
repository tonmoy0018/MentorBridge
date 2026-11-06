"""
Payment provider abstraction. The rest of the app talks to `get_provider()` only, so a different
provider (chosen per business country, see docs/PAYMENTS.md §1) can be added as another adapter.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import (
    CaptureResult,
    CheckoutSession,
    EventKind,
    InvalidWebhook,
    PaymentProvider,
    ProviderError,
    ProviderEvent,
)

__all__ = [
    "CaptureResult",
    "CheckoutSession",
    "EventKind",
    "InvalidWebhook",
    "PaymentProvider",
    "ProviderError",
    "ProviderEvent",
    "get_provider",
]


def get_provider() -> PaymentProvider:
    name = settings.PAYMENT_PROVIDER
    if name == "stripe":
        from .stripe import StripeProvider

        return StripeProvider(
            secret_key=settings.STRIPE_SECRET_KEY,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
            api_base=settings.STRIPE_API_BASE,
        )
    raise ImproperlyConfigured("No payment provider is configured (PAYMENT_PROVIDER is empty).")
