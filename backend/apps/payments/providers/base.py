from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ProviderError(Exception):
    """The provider rejected a request or couldn't be reached. `code` is safe to store and show."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class InvalidWebhook(Exception):
    """A notification failed authentication (bad or missing signature, stale timestamp, bad body)."""


class EventKind(StrEnum):
    CHECKOUT_COMPLETED = "checkout_completed"
    CHECKOUT_EXPIRED = "checkout_expired"
    PAYMENT_AUTHORIZED = "payment_authorized"
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_CANCELLED = "payment_cancelled"
    REFUND_SUCCEEDED = "refund_succeeded"
    REFUND_FAILED = "refund_failed"
    DISPUTE_OPENED = "dispute_opened"
    DISPUTE_WON = "dispute_won"
    DISPUTE_LOST = "dispute_lost"
    IGNORED = "ignored"


@dataclass(frozen=True)
class ProviderEvent:
    """A verified provider notification, normalised to what MentorBridge needs."""

    event_id: str
    raw_type: str
    kind: EventKind
    livemode: bool
    payment_id: str | None = None  # our Payment UUID, from metadata we set at checkout
    provider_payment_reference: str | None = None
    checkout_reference: str | None = None
    amount_cents: int | None = None
    currency: str | None = None
    refund_id: str | None = None  # our Refund UUID, from metadata
    refund_reference: str | None = None
    failure_code: str = ""
    object_reference: str = ""
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CheckoutSession:
    reference: str
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class CaptureResult:
    provider_fee_cents: int | None


@dataclass(frozen=True)
class RefundResult:
    reference: str
    succeeded: bool  # True if the provider already reports success
    failed: bool = False
    failure_code: str = ""


class PaymentProvider(Protocol):
    name: str
    livemode: bool

    def create_checkout(
        self, *, payment, booking, success_url: str, cancel_url: str, expires_at: datetime
    ) -> CheckoutSession: ...

    def expire_checkout(self, payment) -> None: ...

    def capture(self, payment) -> CaptureResult: ...

    def cancel_authorization(self, payment) -> None: ...

    def refund(self, refund) -> RefundResult: ...

    def parse_webhook(self, body: bytes, headers) -> ProviderEvent: ...
