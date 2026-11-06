"""
Stripe adapter: Checkout with manual capture (authorise at checkout, capture when the mentor
accepts), refunds, and webhook verification with Stripe's signature scheme. Configure the webhook
endpoint in Stripe at https://<site>/api/v1/payments/webhooks/stripe/ (docs/PAYMENTS.md §5).
"""

import logging
from datetime import UTC, datetime

import stripe

from .base import (
    CaptureResult,
    CheckoutSession,
    EventKind,
    InvalidWebhook,
    ProviderError,
    ProviderEvent,
    RefundResult,
)

logger = logging.getLogger(__name__)

# Stripe event type → (normalised kind, object family)
EVENT_MAP = {
    "checkout.session.completed": EventKind.CHECKOUT_COMPLETED,
    "checkout.session.expired": EventKind.CHECKOUT_EXPIRED,
    "payment_intent.amount_capturable_updated": EventKind.PAYMENT_AUTHORIZED,
    "payment_intent.succeeded": EventKind.PAYMENT_CAPTURED,
    "payment_intent.payment_failed": EventKind.PAYMENT_FAILED,
    "payment_intent.canceled": EventKind.PAYMENT_CANCELLED,
    "refund.updated": None,  # depends on the refund's status
    "refund.failed": EventKind.REFUND_FAILED,
    "charge.dispute.created": EventKind.DISPUTE_OPENED,
    "charge.dispute.closed": None,  # won or lost
}


def _get(obj, key, default=None):
    try:
        value = obj[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


class StripeProvider:
    name = "stripe"

    def __init__(self, *, secret_key: str, webhook_secret: str, api_base: str = ""):
        if not secret_key or not webhook_secret:
            raise ProviderError("not_configured", "Stripe keys are not configured.")
        self._webhook_secret = webhook_secret
        self.livemode = secret_key.startswith(("sk_live_", "rk_live_"))
        kwargs = {"max_network_retries": 2}
        if api_base:  # only used to point at stripe-mock in tests
            kwargs["base_addresses"] = {"api": api_base}
        self._client = stripe.StripeClient(secret_key, **kwargs)

    # --- API calls --------------------------------------------------------------------------

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except stripe.StripeError as exc:
            code = getattr(exc, "code", None) or type(exc).__name__
            logger.warning("Stripe API error: %s", code)
            raise ProviderError(str(code)) from exc

    def create_checkout(self, *, payment, booking, success_url, cancel_url, expires_at) -> CheckoutSession:
        metadata = {"payment_id": str(payment.pk), "booking_id": str(booking.pk)}
        session = self._call(
            self._client.v1.checkout.sessions.create,
            params={
                "mode": "payment",
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": payment.currency.lower(),
                            "unit_amount": payment.amount_cents,
                            "product_data": {"name": booking.service_title[:250]},
                        },
                    }
                ],
                "payment_intent_data": {
                    "capture_method": "manual",
                    "metadata": metadata,
                    "description": f"MentorBridge booking {booking.pk}",
                },
                "metadata": metadata,
                "client_reference_id": str(booking.pk),
                "success_url": success_url,
                "cancel_url": cancel_url,
                "expires_at": int(expires_at.timestamp()),
            },
            options={"idempotency_key": f"checkout-{payment.pk}"},
        )
        return CheckoutSession(
            reference=session.id,
            url=session.url,
            expires_at=datetime.fromtimestamp(session.expires_at, tz=UTC),
        )

    def expire_checkout(self, payment) -> None:
        if payment.checkout_reference:
            self._call(self._client.v1.checkout.sessions.expire, payment.checkout_reference)

    def capture(self, payment) -> CaptureResult:
        intent = self._call(
            self._client.v1.payment_intents.capture,
            payment.provider_reference,
            params={"expand": ["latest_charge.balance_transaction"]},
            options={"idempotency_key": f"capture-{payment.pk}"},
        )
        fee = None
        transaction = _get(_get(intent, "latest_charge"), "balance_transaction")
        # Only record the fee when it's in the payment's currency (no FX conversion here).
        if (
            isinstance(_get(transaction, "fee"), int)
            and str(_get(transaction, "currency", "")).upper() == payment.currency
        ):
            fee = transaction["fee"]
        return CaptureResult(provider_fee_cents=fee)

    def cancel_authorization(self, payment) -> None:
        self._call(
            self._client.v1.payment_intents.cancel,
            payment.provider_reference,
            options={"idempotency_key": f"cancel-{payment.pk}"},
        )

    def refund(self, refund) -> RefundResult:
        payment = refund.payment
        result = self._call(
            self._client.v1.refunds.create,
            params={
                "payment_intent": payment.provider_reference,
                "amount": refund.amount_cents,
                "metadata": {"refund_id": str(refund.pk), "payment_id": str(payment.pk)},
            },
            options={"idempotency_key": f"refund-{refund.pk}"},
        )
        status = _get(result, "status", "pending")
        return RefundResult(
            reference=result.id,
            succeeded=status == "succeeded",
            failed=status in ("failed", "canceled"),
            failure_code=_get(result, "failure_reason", "") or "",
        )

    # --- webhooks ---------------------------------------------------------------------------

    def parse_webhook(self, body: bytes, headers) -> ProviderEvent:
        signature = headers.get("Stripe-Signature")
        if not signature:
            raise InvalidWebhook("missing signature")
        try:
            event = stripe.Webhook.construct_event(body, signature, self._webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise InvalidWebhook(type(exc).__name__) from exc

        event_type = event["type"]
        obj = event["data"]["object"]
        metadata = _get(obj, "metadata", {}) or {}
        kind = EVENT_MAP.get(event_type, EventKind.IGNORED)
        base = {
            "event_id": event["id"],
            "raw_type": event_type,
            "livemode": bool(_get(event, "livemode", False)),
            "object_reference": _get(obj, "id", ""),
            "payment_id": _get(metadata, "payment_id"),
            "currency": (_get(obj, "currency", "") or "").upper() or None,
        }

        if event_type.startswith("checkout.session."):
            return ProviderEvent(
                kind=kind,
                checkout_reference=_get(obj, "id"),
                provider_payment_reference=_get(obj, "payment_intent"),
                amount_cents=_get(obj, "amount_total"),
                **base,
            )
        if event_type.startswith("payment_intent."):
            amount = {
                EventKind.PAYMENT_AUTHORIZED: _get(obj, "amount_capturable"),
                EventKind.PAYMENT_CAPTURED: _get(obj, "amount_received"),
            }.get(kind, _get(obj, "amount"))
            error = _get(obj, "last_payment_error", {}) or {}
            return ProviderEvent(
                kind=kind,
                provider_payment_reference=_get(obj, "id"),
                amount_cents=amount,
                failure_code=_get(error, "decline_code") or _get(error, "code") or "",
                **base,
            )
        if event_type.startswith("refund."):
            status = _get(obj, "status")
            if kind is None:
                kind = {
                    "succeeded": EventKind.REFUND_SUCCEEDED,
                    "failed": EventKind.REFUND_FAILED,
                    "canceled": EventKind.REFUND_FAILED,
                }.get(status, EventKind.IGNORED)
            return ProviderEvent(
                kind=kind,
                provider_payment_reference=_get(obj, "payment_intent"),
                refund_id=_get(metadata, "refund_id"),
                refund_reference=_get(obj, "id"),
                amount_cents=_get(obj, "amount"),
                failure_code=_get(obj, "failure_reason", "") or "",
                **base,
            )
        if event_type.startswith("charge.dispute."):
            if kind is None:
                kind = {"won": EventKind.DISPUTE_WON, "lost": EventKind.DISPUTE_LOST}.get(
                    _get(obj, "status"), EventKind.IGNORED
                )
            return ProviderEvent(
                kind=kind,
                provider_payment_reference=_get(obj, "payment_intent"),
                amount_cents=_get(obj, "amount"),
                **base,
            )
        return ProviderEvent(kind=EventKind.IGNORED, **base)
