# MentorBridge — API Specification

Status: **implemented and integrated with the web app** (2026-10-27).

The frontend's hand-written types (`frontend/src/lib/api/types.ts`) are checked against types generated from this schema (`frontend/src/lib/api/generated.ts`, via `make gen-api`) at compile time, in `frontend/src/lib/api/contract-check.ts`. If either side drifts, `pnpm typecheck` fails.

The machine-readable contract is the OpenAPI 3 schema, which is generated from the code by drf-spectacular. It's available in three places:
- `docs/openapi.yaml`: an exported copy that's committed to the repo.
- `GET /api/v1/schema/`: the live schema.
- `GET /api/v1/docs/`: interactive Swagger UI.

In production the live schema and Swagger UI are staff-only. This document explains conventions and rules that a schema can't express. Regenerate the export with `make schema`.

## 1. Conventions

| Topic | Convention |
|---|---|
| Base path | `/api/v1/`. The web app calls it on its own origin, and Next.js proxies it to Django |
| Format | JSON, `snake_case`; multipart only for avatar upload |
| IDs | UUID strings. Mentors can also be addressed by `slug` wherever a path says `{id}` under `/mentors/` and `/me/student/saved-mentors/` |
| Time | ISO 8601 in UTC with `Z` (`2026-11-03T09:00:00Z`); dates `YYYY-MM-DD`. Weekly availability uses `HH:MM` wall-clock times in the mentor's IANA time zone |
| Money | `{"amount_cents": 4500, "currency": "USD"}`: integer minor units, one platform currency. Writes use `price_cents` |
| Pagination | `?page=N&page_size=M` → `{"count", "next", "previous", "results"}`. Default 20, max 50. Bookings: default 50, max 100. Reviews: default 10. Short reference lists (categories, taxonomy, weekly rules) are plain arrays |
| Filtering | Query parameters per endpoint (below). Invalid filter values return `400` |
| Versioning | URL prefix. Breaking changes go to `/api/v2/` |

## 2. Authentication, CSRF and CORS

- **Session cookie.** `POST /auth/login/` (or `/auth/register/`) sets an HttpOnly `sessionid` cookie with `SameSite=Lax`, which is also `Secure` in production. There are no tokens in browser storage.
- **CSRF.**
  - Every unsafe request (`POST`, `PUT`, `PATCH`, `DELETE`) must send `X-CSRFToken` with the value of the `csrftoken` cookie. Call `GET /auth/csrf/` once to get that cookie.
  - CSRF is enforced on the anonymous auth endpoints too (login, register, password reset, email verification), which prevents login CSRF.
  - `DJANGO_CSRF_TRUSTED_ORIGINS` must list the public web origin.
- **CORS.** None by default, because the web app is same-origin. Add `CORS_ALLOWED_ORIGINS` only for a deliberate cross-origin client.
- **Suspension.** A suspended user (`is_active=false`) can't log in, and their existing sessions stop authenticating on the next request.

### Access levels used below

| Level | Meaning |
|---|---|
| Public | Anyone |
| Auth | Any logged-in user |
| Student / Mentor | Logged-in user with that role |
| Admin | `role=admin` **and** `is_staff` |
| Participant | The booking's student, or its mentor |

A resource that exists but isn't yours returns **404, not 403**, so IDs can't be probed. A role mismatch on an endpoint returns 403.

## 3. Errors

```json
{ "error": { "code": "slot_unavailable", "message": "That time is no longer available. Please choose another.", "details": {} } }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | Invalid input. Per-field messages are in `details.fields` (`non_field_errors` for the rest) |
| 400 | `invalid_credentials` | Wrong email/password or suspended account (one generic error) |
| 400 | `invalid_token` | Password-reset or email-verification token invalid, expired or already used |
| 400 | `invalid_signature` | Payment webhook whose signature is missing, wrong, stale or doesn't match the body |
| 401 | `not_authenticated` | No valid session |
| 403 | `permission_denied` | Wrong role, or an action reserved for the other participant |
| 403 | `csrf_failed` | Missing or invalid CSRF token |
| 403 | `email_not_verified` | Booking when `REQUIRE_VERIFIED_EMAIL=true` and the email isn't verified |
| 404 | `not_found` | Doesn't exist, or isn't visible to you |
| 405 | `method_not_allowed` | The route doesn't support that method |
| 409 | `slot_unavailable` | Start time isn't an open slot, or was just taken (also raised by the DB constraint) |
| 409 | `student_busy` | The student already has an overlapping booking |
| 409 | `invalid_state` | Transition not allowed from the current status |
| 409 | `service_unavailable` / `not_accepting_bookings` | Service hidden / mentor paused bookings |
| 409 | `payment_required` | Mentor accepts a paid request that has no authorised payment |
| 409 | `too_many_pending` | The student already has 5 unconfirmed bookings (held for payment or awaiting a mentor), or 2 with this mentor |
| 409 | `hold_expired` / `already_paid` | Checkout for a booking whose hold lapsed / that is already paid |
| 409 | `not_refundable` / `refund_too_large` | Refunding an uncaptured payment / more than is still refundable |
| 409 | `already_exists` | Duplicate review, pending verification, open report |
| 409 | `not_eligible` | Review for a booking that isn't completed |
| 409 | `service_in_use` | Deleting a service that has bookings (hide it instead) |
| 429 | `throttled` | Rate limit; `Retry-After` header and `details.retry_after_seconds` |
| 502 | `payment_provider_error` | The payment provider failed or rejected a checkout or capture; nothing was changed. Retry |
| 503 | `payments_unavailable` | Booking a paid service, or starting checkout, while payments are off (`PAYMENT_PROVIDER` empty) |
| 500 | `server_error` | Unexpected; details are logged with the request's `X-Request-ID`, never returned |

### Rate limits (per client IP unless noted)

| Scope | Limit | Endpoints |
|---|---|---|
| `auth_login` | 10/min | login |
| `auth_login_email` | 5/min **per target email** | login |
| `auth_register` | 5/hour | register |
| `password_reset` / `password_reset_confirm` | 5/hour / 10/hour | reset request / confirm |
| `password_change` | 5/hour | password change |
| `email_verify` | 10/hour | verify / resend |
| `booking_create` | 20/hour | `POST /bookings/` |
| `review_create`, `report_create` | 20/hour, 10/hour | reviews, reports |
| `anon` / `user` | 120/min / 600/min | everything else |

The client IP comes from `X-Forwarded-For`, trusting `NUM_PROXIES` proxies (default 1). In production that's Caddy, which overwrites client-supplied values; Next.js forwards the visitor's header on server-side calls. The per-account login limit folds case and look-alike characters (`ſ`, `ı`) the way the account lookup does. The Django admin login is limited separately: 10 failures per IP and 5 per account per 15 minutes.

---

## 4. Auth & account — `/auth/`

| Method | Path | Access | Body → Response |
|---|---|---|---|
| GET | `/auth/csrf/` | Public | → 204, sets `csrftoken` |
| POST | `/auth/register/` | Public | `{email, password, first_name, last_name, role: student\|mentor, timezone}` → 201 `CurrentUser`, logged in. Creates the student/mentor profile and sends a verification email |
| POST | `/auth/login/` | Public | `{email, password}` → 200 `CurrentUser` |
| POST | `/auth/logout/` | Public | → 204 |
| GET | `/auth/me/` | Auth | → `CurrentUser` `{id, email, first_name, last_name, role, timezone, email_verified, is_admin}`. `is_admin` is true only for `role=admin` **and** staff, the same rule as the admin endpoints. The web app gates its admin area on it |
| PATCH | `/auth/me/` | Auth | `{first_name?, last_name?, timezone?}` → `CurrentUser`. The role isn't writable |
| POST | `/auth/password/change/` | Auth | `{current_password, new_password}` → 204. Other sessions are logged out |
| POST | `/auth/password/reset/` | Public | `{email}` → 204, always (no enumeration). Emails `FRONTEND_URL/reset-password?uid&token` |
| POST | `/auth/password/reset/confirm/` | Public | `{uid, token, new_password}` → 204. The token is single-use and lasts 1h |
| POST | `/auth/email/verify/` | Public | `{uid, token}` → 204. Single-use, 72h |
| POST | `/auth/email/verify/resend/` | Auth | → 204 |

Emails (verification, reset, verification decisions) are sent after the database change commits. If the mail server fails, the error is logged and the request still succeeds; users can ask for the email again.

Passwords are checked by Django's validators: at least 8 characters, not common, not all numeric, and not similar to the user's details.

## 5. Categories & taxonomy (Public)

| Method | Path | Notes |
|---|---|---|
| GET | `/categories/` | Active categories `[{id, name, slug, description, is_active}]`. `?with_counts=true` adds `mentor_count` (approved, active mentors) |
| GET | `/categories/{slug}/` | One category, with `mentor_count` |
| GET | `/taxonomy/professions/` | `?industry=<category slug>` |
| GET | `/taxonomy/skills/` | `?q=` |
| GET | `/taxonomy/languages/` | `[{code, name}]` (ISO 639-1) |
| GET | `/taxonomy/countries/` | `[{code, name}]` (ISO 3166-1) |

## 6. Mentors (Public)

| Method | Path | Notes |
|---|---|---|
| GET | `/mentors/` | Search. Only `verification_status=approved` mentors whose account is active |
| GET | `/mentors/{id}/` | Public profile: summary fields plus `bio, timezone, experiences, services` (active only) |
| GET | `/mentors/{id}/availability/` | `?service=<uuid>&from=YYYY-MM-DD&to=YYYY-MM-DD` (UTC dates, inclusive, ≤31 days) → `{mentor_timezone, service_id, duration_minutes, slots: [UTC start times]}` |
| GET | `/mentors/{id}/reviews/` | Published reviews, paginated, newest first |

**`GET /mentors/` filters:**

| Parameter | Description |
|---|---|
| `q` | Matches name, headline, title, company, profession, skills and categories. Every term must match |
| `industry` | Category slug. Repeatable; matches any |
| `profession` | Profession slug |
| `skill` | Skill slug. Repeatable; matches any |
| `country` | ISO 3166-1 alpha-2 code |
| `language` | ISO 639-1 code |
| `price_min`, `price_max` | Cents, compared with the mentor's cheapest active service |
| `available_within_days` | 1–60 |
| `ordering` | `relevance` (default: most reviewed, then earliest verified), `min_price_cents`, `-min_price_cents`, `-rating_avg`, `-years_experience` |

**Summary fields:**
- Identity and profile: `id, slug, display_name, headline, avatar_url, current_title, current_company, profession, industries[], skills[], country, city, languages[], years_experience`.
- Trust and price: `is_verified, rating_avg` (decimal string or null), `rating_count, starting_price` (Money or null), `next_available_at` (UTC or null).

`is_verified` is derived only from the admin verification workflow. Ratings come only from published reviews of completed bookings.

## 7. Mentor self-service — `/me/mentor/` (Mentor)

| Method | Path | Notes |
|---|---|---|
| GET / PATCH | `/me/mentor/profile/` | Own profile. Writable fields: `headline, bio, current_title, current_company, profession_id, industry_ids (≤3), skill_ids (≤10), language_codes, country, city, timezone, years_experience (0–60), linkedin_url (https://*.linkedin.com), meeting_url (https), is_accepting_bookings, auto_accept, min_notice_hours (0–336), booking_horizon_days (1–180), buffer_minutes (0–120)`. `verification_status`, ratings and the slug are read-only, and unknown fields are ignored. Changing `timezone` keeps weekly hours at the same wall-clock times in the new zone |
| POST / DELETE | `/me/mentor/profile/avatar/` | Multipart `avatar`: JPEG, PNG or WebP; ≤2 MB; ≤4000×4000. The image content is verified and the file name randomised |
| GET / POST | `/me/mentor/experiences/` | `{kind: work\|education, title, organization, start_date, end_date?, description?}` |
| GET / PATCH / DELETE | `/me/mentor/experiences/{id}/` | |
| GET / POST | `/me/mentor/services/` | List includes hidden services. Create: `{title, description, duration_minutes ∈ 15,30,45,60,90,120,180, price_cents (0–1,000,000), currency? (=platform), is_active?}` |
| GET / PATCH / DELETE | `/me/mentor/services/{id}/` | Changes apply to new bookings only. DELETE → 409 `service_in_use` if it has bookings |
| GET / PUT | `/me/mentor/availability/rules/` | Weekly hours `[{weekday 0=Mon..6, start_time "HH:MM", end_time}]`. PUT replaces all of them atomically, and ranges on one weekday must not overlap |
| GET / POST | `/me/mentor/availability/exceptions/` | Dated changes `{start_at, end_at, status: available\|unavailable, note?}` (≤31 days each) |
| DELETE | `/me/mentor/availability/exceptions/{id}/` | |
| GET / POST | `/me/mentor/verification/` | POST `{evidence_note?}` submits for review. It requires a complete profile: headline, bio ≥50 characters, title, profession, country, a default meeting link, and at least one industry, skill and language. 409 if already pending or approved |
| GET | `/me/mentor/earnings/summary/` | `{pending, available, paid_out, lifetime}` (Money), derived from captured payments after the platform fee and refunds, and from paid payouts |
| GET | `/me/mentor/earnings/ledger/` | Paginated `{id, kind: earning\|refund_reversal\|payout, amount, description, booking_id, created_at, available_at}` |
| GET | `/me/mentor/payouts/` | Paginated payouts |

## 8. Student self-service — `/me/student/` (Student)

| Method | Path | Notes |
|---|---|---|
| GET / PATCH | `/me/student/profile/` | `{headline, education, bio, country, interest_ids (≤10 categories)}` |
| GET | `/me/student/saved-mentors/` | Paginated mentor summaries (still-listed mentors only) |
| PUT / DELETE | `/me/student/saved-mentors/{id}/` | Idempotent save/remove → 204. Unlisted mentors can't be saved (404) |
| GET / POST | `/me/student/goals/` | `{title, description?, status: not_started\|in_progress\|achieved\|archived, target_date?}`. `achieved_at` is set automatically |
| GET / PATCH / DELETE | `/me/student/goals/{id}/` | Own goals only |

## 9. Bookings — `/bookings/`

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/bookings/` | Student / Mentor | Your bookings. `?scope=upcoming\|past\|all` (default `all`), `?status=` (repeatable) |
| POST | `/bookings/` | Student | `{service_id, start_at, student_note?}` → 201. Price, duration and title come from the service on the server; any price sent by the client is ignored. A paid service is created as `pending_payment`, holding the slot for `booking_hold_minutes`. **While `payments_enabled` is false (see `/config/`), paid services return 503 `payments_unavailable` and nothing is held** |
| GET | `/bookings/{id}/` | Participant | Includes the `events` audit trail |
| POST | `/bookings/{id}/cancel/` | Participant | `{reason?}`. Mentors must give a reason. Policy below |
| POST | `/bookings/{id}/accept/` | Mentor of booking | `requested → confirmed`; reveals `meeting_url`. For a paid booking the authorised payment is **captured** first; a provider failure returns 502 `payment_provider_error` and leaves the request open |
| POST | `/bookings/{id}/decline/` | Mentor of booking | `{reason}` (required): `requested → declined`; releases the card authorisation |
| POST | `/bookings/{id}/complete/` | Mentor of booking | `confirmed → completed`, only after the start time |
| POST | `/bookings/{id}/checkout/` | Student of booking | For `pending_payment` bookings → `{payment_id, checkout_url, expires_at, livemode}`. Repeated calls return the same open checkout. 409 `invalid_state` / `hold_expired` / `already_paid`; 502 `payment_provider_error`; 503 `payments_unavailable` while payments are off. **The browser's return from checkout changes nothing**; see [PAYMENTS.md §3](PAYMENTS.md#3-workflow-and-state-transitions) |
| POST | `/bookings/{id}/review/` | Student of booking | `{rating 1–5, comment?}`, only when `completed`, once |

**Booking response fields:**
- Session: `id, status, start_at, end_at, service_title, duration_minutes, price, student_note, meeting_url`.
- People: `mentor {id, slug, display_name, headline, avatar_url}` and `student {id, display_name, avatar_url}`.
- Lifecycle: `hold_expires_at, respond_by, confirmed_at, completed_at, cancelled_at, cancellation_reason, refund_outcome, has_review, created_at`.

`meeting_url` is null unless the booking is `confirmed`. It's the link recorded at acceptance, or the mentor's current default link if none was recorded. No email addresses or other contact details are exposed.

### Lifecycle and integrity

```
pending_payment ─(verified provider webhook)→ requested ─accept (capture)→ confirmed ─complete→ completed
      │                                              │  └─decline→ declined   └─cancel→ cancelled
      ├─ hold lapses (30 min + grace) → expired      ├─ respond_by / start passes → expired
      └─ cancel → cancelled                          └─ cancel → cancelled
free service: created directly as requested (or confirmed when the mentor auto-accepts)
```

- Allowed transitions are listed in one table (`apps/bookings/models.py::TRANSITIONS`), and each change writes a `BookingEvent`.
- **Conflict prevention.** Creation runs in one transaction:
  1. Lock the mentor row, which serialises concurrent requests for that mentor.
  2. Expire stale holds.
  3. Re-check that the start time is one of the slots the availability engine offers.
  4. Insert the booking.

  PostgreSQL exclusion constraints then reject any overlap among active bookings (`pending_payment`, `requested`, `confirmed`), whatever the code path:
  - for the same mentor, over `[start_at, end_at + buffer)`;
  - for the same student, over `[start_at, end_at)`.
- **Time.** Everything is stored as `timestamptz` in UTC. Weekly hours are expanded per date in the mentor's IANA zone, so daylight-saving changes are handled.

### Cancellation policy (`refund_outcome`)

| Who | Booking state | Outcome |
|---|---|---|
| Student | `pending_payment` / `requested` | `not_charged` (`""` for free services) |
| Student | `confirmed`, ≥ `FREE_CANCELLATION_HOURS` (24h) before start | `full_refund` |
| Student | `confirmed`, < 24h before start | `no_refund` |
| Mentor | `confirmed` (reason required) | `full_refund` |
| Mentor | `requested` | 409. Decline instead |
| Anyone | after start, or a closed booking | 409 `invalid_state` |

Before capture, cancelling releases the card authorisation. A `full_refund` on a captured payment creates a refund through the provider after the cancellation commits. The payment's `refund_status` is `pending` until the provider confirms it ([PAYMENTS.md §7](PAYMENTS.md#7-refunds-and-cancellations)).

### Payment webhooks

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/payments/webhooks/{provider}/` | The provider (signature) | No session or CSRF. 404 unless `{provider}` is the configured one. The signature is verified first: 400 `invalid_signature` changes nothing. Each provider event id is processed once (`{"received": true, "outcome": "duplicate"}` on redelivery). See [PAYMENTS.md §5](PAYMENTS.md#5-webhook-verification) |

## 10. Reviews & reports

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/bookings/{id}/review/` | Student of booking | See §9. Updates the mentor's `rating_avg` / `rating_count` |
| GET | `/mentors/{id}/reviews/` | Public | `{id, rating, comment, created_at, reviewer_display_name ("Jordan L."), service_title}` |
| POST | `/reports/` | Student / Mentor | `{target_type: review\|mentor_profile\|booking\|user, target_id, reason: spam\|inappropriate\|misleading\|harassment\|no_show\|other, details?}`. You can report bookings you took part in, and users you've had a booking with; anything else returns 404. One open report per reporter per target |

## 11. Admin — `/admin/` (Admin)

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/stats/` | `?from=&to=` (YYYY-MM-DD, UTC, inclusive; default the last 30 days; 400 if invalid). Returns `{users{…}, mentors_by_status{…}, bookings_by_status{…}, gross_booking_value, platform_fees, refunds, period{from, to, new_users, bookings_created, sessions_completed, live{…}, test{…}}}`. Top-level money is all-time **live** only: `platform_fees` = net platform revenue (commission minus refunded commission). `period.live`/`period.test` = `{gross_booking_value, platform_commission, refunds, net_platform_revenue, provider_fees, captured_payments}`. Test-mode payments are never revenue |
| GET | `/admin/users/` | `?q=&role=&is_active=` → `{id, email, display_name, role, is_active, date_joined, last_login}` |
| GET | `/admin/users/{id}/` | |
| POST | `/admin/users/{id}/suspend/` | `{reason}` (required). Can't target yourself or other admins. Audit-logged |
| POST | `/admin/users/{id}/reactivate/` | Audit-logged |
| GET | `/admin/verification-requests/` | `?status=pending\|approved\|rejected\|withdrawn` (default `pending`, oldest first) |
| POST | `/admin/verification-requests/{id}/approve/` | Publishes the mentor and sets `verified_at`. Emails the mentor. Audit-logged |
| POST | `/admin/verification-requests/{id}/reject/` | `{reason}` (required; shown to the mentor). Audit-logged |
| GET | `/admin/bookings/`, `/admin/bookings/{id}/` | `?status=&mentor=<profile uuid>&student=<user uuid>` |
| POST | `/admin/bookings/{id}/cancel/` | `{reason, refund=true}`. Cancels any active booking; releases an authorisation, or refunds a captured payment in full if `refund`. Emails both parties. 409 for closed bookings. Audit-logged |
| GET | `/admin/payments/`, `/admin/payments/{id}/` | `?status=&livemode=`. `{amount, commission_bps, platform_fee, mentor_share, provider_fee, refunded, refundable, status, refund_status, dispute_status, provider, provider_reference, livemode, failure_code, …}`. Payment status can't be set through any API |
| POST | `/admin/payments/{id}/refund/` | `{amount_cents?, note}` → 201 refund. Omit `amount_cents` for everything still refundable. 409 `not_refundable` (not captured) / `refund_too_large`. Audit-logged |
| GET | `/admin/refunds/` | `{amount, commission_reversed, mentor_share_reversed, reason: student_cancellation\|mentor_cancellation\|admin\|dispute_lost\|system, status: pending\|succeeded\|failed, provider_reference, failure_code, note, initiated_by_name, …}` |
| GET | `/admin/reviews/` | `?status=published\|hidden&mentor=<slug>` |
| POST | `/admin/reviews/{id}/hide/` | `{reason}` (required). Recalculates the mentor's rating. Audit-logged |
| POST | `/admin/reviews/{id}/publish/` | Restores a hidden review. Audit-logged |
| GET | `/admin/audit-log/` | `?action=<prefix>&target_type=`. Read-only |
| GET | `/admin/notifications/` | `?status=&template=`. Email delivery status; no addresses or content |
| GET | `/admin/reports/` | `?status=open` (default: open + in review), `resolved`, or an exact status |
| POST | `/admin/reports/{id}/resolve/` | `{resolution: actioned\|dismissed, note, hide_review?}`. `hide_review` hides the reported review and recalculates the rating. Audit-logged |

**Permissions.** Every `/admin/` endpoint requires an authenticated user with role `admin`: anonymous callers get 401, students and mentors 403, for every method. A test discovers every route under `/api/v1/admin/` and checks this. Administrative actions, refund failures and disputes are written to `common_auditlogentry`. It's readable at `GET /admin/audit-log/` and read-only in Django admin at `/django-admin/`.

## 12. Operations

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/health/` | Public | `{"status": "ok", "db": "ok"}`, or 503 `degraded` |
| GET | `/config/` | Public | `{payments_enabled, payments_livemode, currency, booking_hold_minutes, mentor_response_hours, free_cancellation_hours, require_verified_email}`. Lets clients explain the rules before a user acts |
| GET | `/schema/`, `/docs/` | Public in dev, staff in prod | OpenAPI 3 YAML / Swagger UI |

Every response carries `X-Request-ID` (an incoming safe value is reused), which also appears in the server logs.
