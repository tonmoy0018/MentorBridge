# Payments

How MentorBridge takes payment for sessions, splits commission, handles refunds and disputes, and what is and isn't operational.

> **Status (2026-11-06): implemented and tested against a mocked provider and Stripe's official mock server. Live payments and payouts are not operational.**
> - No provider has been chosen, because the business's country of registration is still unknown (§1).
> - The Stripe adapter has never been run against a real Stripe account (test or live).
> - Payouts to mentors are manual records only (§8).
> - With `PAYMENT_PROVIDER` empty (the default), paid sessions can't be booked at all.

## 1. Choosing a provider

### What the business needs

| Need | Why |
|---|---|
| The provider must accept businesses registered in **our** country | Decides everything else; unknown today ([PRD open question #2](PRODUCT_REQUIREMENTS.md)) |
| Card payments from students in many countries, in the platform currency (`PLATFORM_CURRENCY`, USD by default) | Students and mentors are international |
| **Authorise now, capture later** | We charge only when the mentor accepts (ADR-7) |
| Partial and full refunds through the API | Cancellation policy, admin refunds |
| Signed server-to-server notifications (webhooks) | Payment state must never come from the browser |
| A commission split, or at least a clean record of it | 15% default commission |
| Mentor payouts, ideally to many countries | Mentors are paid their share |

### What the providers' own documentation says

Checked on the providers' official pages during this milestone. Re-check before deciding: availability changes.

| Provider | Business countries | Auth + later capture | Split / commission | Payouts to mentors | Notes |
|---|---|---|---|---|---|
| **Stripe** (Checkout + Connect) | ~46 countries. **Not available for businesses in Bangladesh.** India is listed as "preview" (contact sales). | Yes (`capture_method=manual`); an online card authorisation is held for about 7 days | Connect: application fees | Connect cross-border payouts only where the platform and connected accounts are in the US, UK, EEA, Canada or Switzerland | Checkout sessions must expire 30 min – 24 h after creation |
| **PayPal** (multiparty / Commerce Platform) | Many countries | Yes (authorise / capture) | "Partner fee" on multiparty payments | To PayPal accounts | Partner onboarding/approval required |
| **Razorpay** (Route) | India, Malaysia | Yes | Route: split transfers to linked accounts | To linked accounts in-country | Domestic focus |
| **SSLCommerz** | Bangladesh | Not confirmed | Not confirmed (split payments not verified in public docs) | Not confirmed | IPN notification + Order Validation API for verification |

Nothing here was assumed to work beyond what those pages state. Anything marked "not confirmed" needs the provider's sales or support team.

### Decision

- **Undecided.** The deciding fact, the business's country of registration, is unknown. The development machine's time zone (GMT+6) is not evidence of anything.
- What was built is a **provider abstraction** (§2) plus **one adapter (Stripe)**, because Stripe has a public sandbox, a documented signature scheme and an official API mock. That let the whole workflow be built and tested without real accounts.
- If the business turns out to be in a country Stripe doesn't serve (e.g. Bangladesh), the same workflow gets a different adapter. The rest of the app doesn't change (§2).

**Needed from the business:** the country of registration, the provider it can open a merchant account with, and that provider's **sandbox/test credentials**.

## 2. Architecture

```
apps/payments/
  providers/base.py      PaymentProvider protocol, normalised ProviderEvent, errors
  providers/stripe.py    Stripe adapter (Checkout, capture, cancel, refund, webhook parsing)
  providers/__init__.py  get_provider(): picks the adapter from PAYMENT_PROVIDER
  commission.py          commission maths (§4)
  services.py            checkout, webhook processing, capture/release, refunds, disputes
  selectors.py           mentor earnings and ledger, derived from records
  models.py              Payment, Refund, WebhookEvent, Payout
```

- The rest of the app calls `services.py`; only `services.py` calls `get_provider()`.
- An adapter implements six operations: `create_checkout`, `expire_checkout`, `capture`, `cancel_authorization`, `refund` and `parse_webhook`. `parse_webhook` verifies the provider's signature and returns a normalised event (`payment_authorized`, `payment_failed`, `refund_succeeded`, `dispute_lost`, …).
- **No card data touches MentorBridge.** Students pay on the provider's hosted page. We store only opaque references (checkout session id, payment id, refund id), amounts and provider error codes. There are no card, CVC or payload fields (a test checks this).
- `WebhookEvent` stores the event id, type and object id, not the payload, which can contain customer details.

## 3. Workflow and state transitions

### The happy path

1. **Select a service and time.** `POST /bookings/` validates the slot and takes the price **from the service on the server**. A paid booking is created as `pending_payment` and holds the slot for `BOOKING_HOLD_MINUTES` (30).
2. **Create the payment request.** `POST /bookings/{id}/checkout/` creates a `Payment` (status `created`) and snapshots the amount and commission breakdown. It asks the provider for a hosted checkout with manual capture.
   - The provider's idempotency key is `checkout-<payment id>`.
   - Clicking again reuses the open checkout.
   - The hold is extended to the checkout's expiry (Stripe's minimum is 30 minutes, so at least 31).
3. **Provider checkout.** The student enters card details on the provider's page.
4. **Signed notification.** The provider calls `POST /api/v1/payments/webhooks/stripe/`. The signature is verified before anything else is read (§5).
5. **Verify and update.** For an authorisation, the event's amount **and** currency must match the Payment, and the event's live/test mode must match the Payment's. The Payment becomes `authorized` and the booking `requested`, with `respond_by` set; the mentor is emailed.
6. **Mentor accepts.** `POST /bookings/{id}/accept/` captures through the provider (idempotency key `capture-<payment id>`) and records the provider fee. The Payment becomes `captured`, the booking `confirmed`, and both parties are emailed. If the mentor has auto-accept on, step 6 happens inside step 5.
7. **Student confirmation.** The browser returns to `/dashboard/student/bookings?checkout=<booking id>`. **That return proves nothing.** The page only re-reads the booking and shows whatever status the backend has, which only a verified webhook can have changed.

### Payment states

```
created ──► authorized ──► captured
   │  ▲          │
   ▼  │          ▼
 failed ──────► cancelled  (also from created: checkout expired / replaced)
```

- `failed` means a declined attempt; the student can retry in the same checkout, so `failed → authorized` is allowed.
- Transitions are **monotonic** (`PAYMENT_TRANSITIONS`). A late or out-of-order event that would move a payment backwards is ignored, e.g. an "authorised" event after capture.
- Refund and dispute state are separate fields (`refund_status`, `dispute_status`) so they never overwrite the payment status.

### Booking states and how payment moves them

| Event | Booking | Payment |
|---|---|---|
| Paid booking created | `pending_payment` (slot held) | — |
| Checkout started | unchanged; hold extended | `created` |
| Card declined | unchanged (student can retry) | `failed`, `payment_failed` email |
| Authorised (webhook) | `requested` (or `confirmed` + capture if auto-accept) | `authorized` |
| Authorised but the booking is no longer pending (hold expired, cancelled) | unchanged | authorisation **released**, `payment_released` email |
| Authorised on a checkout we already cancelled | unchanged | authorisation **released** |
| Amount/currency mismatch | unchanged | authorisation **released** (`amount_mismatch`) |
| Checkout expired (webhook) or hold lapsed (scheduler, after `PAYMENT_WEBHOOK_GRACE_MINUTES`) | `expired` | `cancelled`; open checkout expired at the provider |
| Mentor accepts | `confirmed` | `captured`. A failed capture → 502, request stays open |
| Mentor declines, request expires, or student cancels before acceptance | `declined` / `expired` / `cancelled` | authorisation released → `cancelled` |
| Authorisation lapses (~7 days) or is cancelled at the provider | `expired` if still pending/requested | `cancelled` |
| Cancellation after capture | `cancelled` | refund per policy (§7) |
| Provider reports a capture we didn't record (our accept transaction was lost after the capture succeeded) | `requested` → `confirmed` | `captured` |
| Same, but the booking already closed (declined/expired/cancelled) | unchanged | `captured`, then refunded in full automatically (reason `system`) |
| Mentor retries accept after such a capture | `confirmed` | already `captured`: treated as success |

## 4. Commission and accounting

All amounts are integer minor units (cents). Commission is configured in basis points:

```
commission   = round_half_up(gross × commission_bps / 10 000)
mentor share = gross − commission
```

| Example | Gross | Rate | Commission | Mentor share |
|---|---|---|---|---|
| Brief example | $40.00 | 1500 bps (15%) | $6.00 | $34.00 |
| Rounding | $9.99 | 15% | $1.50 (1.4985 → 1.50) | $8.49 |
| Default service | $50.00 | 15% | $7.50 | $42.50 |

- **Where the rate comes from.** The default is `PLATFORM_FEE_BPS` (1500). An admin can set a per-mentor override (`MentorProfile.commission_bps`, Django admin only). The rate in force is **snapshotted on the Payment** when checkout starts, so later changes never alter existing payments. The mentor sees their rate on the Earnings page.
- **Per transaction.** Every Payment stores `amount_cents`, `commission_bps`, `platform_fee_cents` (commission), `mentor_share_cents` and, once captured, `provider_fee_cents`. A database constraint enforces `platform_fee + mentor_share = amount`.

### Accounting rules

| Situation | Rule |
|---|---|
| **Revenue** | Only **captured, live-mode** payments count. Platform revenue = commission − commission reversed by refunds. |
| **Test-mode payments** | `livemode = false` (from a `sk_test_` key). Shown with a "Test mode" label and in a separate `test` block of the admin stats. **Never counted as revenue.** |
| **Refunds** | A Refund row reverses commission and mentor share **in proportion** to the gross amount. The last refund absorbs rounding, so the totals reverse exactly. A database constraint enforces `commission_reversed + mentor_share_reversed = amount`. |
| **Cancellations** | Before capture nothing was charged: the authorisation is released and no refund is needed. After capture, the cancellation policy applies (§7). |
| **Disputes / chargebacks** | `dispute_status` tracks open, won or lost. A **lost** dispute is recorded as a Refund (reason `dispute_lost`) that reverses commission and mentor share like a refund, and is audit-logged. Provider dispute fees are not modelled. |
| **Provider fees** | Recorded from the provider's balance transaction when it's in the payment currency. **Borne by the platform** and never deducted from the mentor share. Not refunded by Stripe on refunds; not modelled further. |
| **Failed payments** | No money moved, so there are no accounting entries. The Payment stays `failed` or `cancelled` with the provider's decline code only. |
| **Taxes (VAT/GST, withholding)** | **Not calculated.** Prices are treated as tax-inclusive gross amounts. Tax treatment depends on the business's country and needs an accountant; it's an open item. |
| **Currency** | One platform currency. Amount and currency are checked on every provider event. |

**Mentor earnings** (`selectors.py`) are derived only from records: mentor share minus mentor share reversed by succeeded refunds, minus payouts. Earnings are *pending* until the session is completed, then *available*.

## 5. Webhook verification

Endpoint: `POST /api/v1/payments/webhooks/{provider}/`. It returns 404 unless payments are enabled and `{provider}` is the configured one.

1. **Signature first.** Stripe's `Stripe-Signature` header is verified with `stripe.Webhook.construct_event` against `STRIPE_WEBHOOK_SECRET`. That's HMAC-SHA256 over `timestamp.payload`, with a **5-minute timestamp tolerance** against replays. A missing, wrong, tampered or stale signature → **400 `invalid_signature`**, and nothing is read or stored.
2. **Idempotency.** The event id is inserted into `WebhookEvent` (unique on provider + event id) under a row lock. A redelivered event finds the processed row and returns `{"outcome": "duplicate"}` without changing anything. Each email has its own dedupe key as well (§NOTIFICATIONS).
3. **Matching.** The payment is found by our `payment_id` metadata, the provider payment reference, or the checkout reference. An event for an unknown payment is acknowledged and ignored.
4. **Checks.** Live/test mode must match the payment. Amount and currency must match for authorisations and captures. Status changes must be allowed transitions.
5. **One transaction.** The event record and every state change commit together. If processing fails, nothing is recorded, the endpoint returns 500, and the provider retries.

Server-to-server API responses (capture, refund) are authenticated with our secret key and trusted directly. Their matching webhooks then arrive as no-ops.

### Stripe setup (when credentials exist)

1. In the Stripe dashboard (test mode first), add a webhook endpoint `https://<site>/api/v1/payments/webhooks/stripe/` subscribed to these events:
   - `checkout.session.completed`, `checkout.session.expired`
   - `payment_intent.amount_capturable_updated`, `payment_intent.succeeded`, `payment_intent.payment_failed`, `payment_intent.canceled`
   - `refund.updated`, `refund.failed`
   - `charge.dispute.created`, `charge.dispute.closed`
2. Put the endpoint's signing secret in `STRIPE_WEBHOOK_SECRET`, and a **test** secret key (`sk_test_…`, or a restricted `rk_test_…`) in `STRIPE_SECRET_KEY`.
3. Locally: run `stripe listen --forward-to localhost:8000/api/v1/payments/webhooks/stripe/` and use the `whsec_…` it prints.

## 6. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PAYMENT_PROVIDER` | empty | Empty = payments off (paid bookings refused with 503). `stripe` = the Stripe adapter. Anything else stops startup. |
| `STRIPE_SECRET_KEY` | empty | Required with `stripe`; must start `sk_test_`, `sk_live_`, `rk_test_` or `rk_live_`. A live key makes payments **real**. |
| `STRIPE_WEBHOOK_SECRET` | empty | Required with `stripe`; must start `whsec_`. |
| `STRIPE_API_BASE` | empty | **Tests only**: points the adapter at stripe-mock. Production settings refuse to start with it set. |
| `PLATFORM_FEE_BPS` | 1500 | Default commission (15%). |
| `PLATFORM_CURRENCY` | USD | Platform currency. |
| `BOOKING_HOLD_MINUTES` | 30 | Slot hold while paying. Must allow Stripe's 30-minute checkout minimum. |
| `PAYMENT_WEBHOOK_GRACE_MINUTES` | 5 | Extra time before an unpaid hold expires, for late webhooks. |
| `MENTOR_RESPONSE_HOURS` | 48 | Mentor response window (1–120; must stay under the ~7-day authorisation lifetime). |
| `FREE_CANCELLATION_HOURS` | 24 | Refund cut-off for student cancellations. |

Secrets come only from the environment (`.env`, git-ignored, or the host's secret store). `GET /config/` exposes `payments_enabled` and `payments_livemode` to the web app. The UI shows a "Test mode" notice whenever payments are in sandbox mode.

## 7. Refunds and cancellations

| Who cancels | When | Outcome |
|---|---|---|
| Student | Before the mentor accepts | Authorisation released; not charged |
| Student | ≥ `FREE_CANCELLATION_HOURS` before the session | Full refund |
| Student | Later | No refund |
| Mentor | Any time before the session | Full refund |
| Admin | Any active booking (`POST /admin/bookings/{id}/cancel/`, reason required) | Full refund if `refund: true` (default), otherwise none; audit-logged |

**How a refund runs:**
1. A `Refund` row is committed as `pending`, and the student gets a `refund_initiated` email.
2. The provider is called **after** that commit, with idempotency key `refund-<refund id>`, so a retry can never refund twice.
3. The refund completes from the provider's response or its `refund.updated` / `refund.failed` webhook: `refund_succeeded` / `refund_failed` email; a failure is audit-logged.
4. If the provider is unreachable, the refund is marked failed, the cancellation still stands, and an admin can retry from **Admin → Payments**.

- **Admin refunds.** `POST /admin/payments/{id}/refund/` takes `amount_cents` (optional; omit for everything still refundable) and a required `note`. Pending and succeeded refunds count against the refundable amount, so over-refunding returns 409 `refund_too_large`.
- **Refunds made in the provider dashboard** arrive as webhooks and are recorded too.
- **Automatic refunds** (reason `system`) cover money captured for a booking that can't go ahead (§3).
- A lost dispute only reverses money not already being refunded, so totals can never exceed the payment.

## 8. Payouts

**There are no automatic payouts.** Automatic payouts need the provider's connected-account product (e.g. Stripe Connect), which depends on the provider decision (§1). Stripe's cross-border payouts would also only cover mentors in the US, UK, EEA, Canada and Switzerland.

Until then, `Payout` rows are **manual records** that staff create in Django admin after paying a mentor outside the platform. Mentors see them on their Earnings page. No code moves money to mentors.

## 9. Testing: what has and hasn't been verified

| Verified (2026-11-06) | How |
|---|---|
| The whole workflow (§3), commission maths, refunds, disputes, earnings, test-mode exclusion from revenue | `backend/tests/test_payments.py`: 50 tests. The provider's **API responses are mocked** (`FakeStripe`, clearly labelled). **Webhooks are really signed** (HMAC-SHA256) and verified by the real `stripe` library. |
| Invalid, missing, stale and tampered signatures; duplicate events; amount, currency and mode mismatches; late authorisations released | Same file |
| Every admin endpoint refuses students, mentors and anonymous callers | `backend/tests/test_admin_ops.py` (discovers every `/api/v1/admin/` route) |
| The adapter's requests are valid for Stripe's API | `make test-stripe-mock` against `stripe/stripe-mock:v0.206.0` (Stripe's official OpenAPI-validating mock). It checks request shapes only: no real Stripe. |
| Payments-off behaviour in the browser | Playwright E2E (payments disabled) |

**Not verified:**
- Anything against a real Stripe account, test or live. No credentials exist.
- The browser redirect to and from a real hosted checkout.
- Real webhook delivery and retries.
- Provider fees and currency behaviour on real charges.
- Payouts.

**Do not describe live payments or payouts as working until those have been tested.**

### Going-live checklist

1. Decide the provider from the business's country (§1); implement a new adapter if it isn't Stripe.
2. Run the full flow in the provider's **sandbox** with real test keys: pay, decline, expire, accept/capture, cancel/refund, dispute (Stripe's test cards cover these).
3. Confirm webhook delivery and signature verification against the real endpoint.
4. Decide tax treatment with an accountant.
5. Decide and implement payouts (connected accounts) or document the manual process.
6. Only then switch to live keys.
